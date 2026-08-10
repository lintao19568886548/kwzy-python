-- Party DDL 草案 v1.4（预检：party_addresses；主档无 address / 无 park_id）
-- 设计 only。生产权威：PostgreSQL 16（ADR-003d）。
-- 禁止本阶段执行 migration。

-- parties：无 park_id、无 address、无证件列
CREATE TABLE IF NOT EXISTS parties (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_type      VARCHAR(32)  NOT NULL DEFAULT 'ORGANIZATION',
  name            VARCHAR(128) NOT NULL,
  contact_name    VARCHAR(64)  NULL,
  contact_phone   VARCHAR(32)  NULL,
  credit_code     VARCHAR(64)  NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
  risk_status     VARCHAR(32)  NOT NULL DEFAULT 'NORMAL',
  blacklist_reason      VARCHAR(512) NULL,
  blacklisted_at        TIMESTAMPTZ  NULL,
  blacklisted_by        BIGINT       NULL,
  blacklist_removed_at  TIMESTAMPTZ  NULL,
  blacklist_removed_by  BIGINT       NULL,
  remark          VARCHAR(255) NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL,
  CONSTRAINT uk_parties_tenant_credit UNIQUE (tenant_id, credit_code)
);
CREATE INDEX IF NOT EXISTS idx_parties_tenant_status ON parties (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_parties_tenant_risk ON parties (tenant_id, risk_status);
CREATE INDEX IF NOT EXISTS idx_parties_tenant_name ON parties (tenant_id, name);

CREATE TABLE IF NOT EXISTS party_roles (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL REFERENCES parties(id),
  role_code       VARCHAR(32)  NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
  started_at      TIMESTAMPTZ  NULL,
  ended_at        TIMESTAMPTZ  NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL,
  CONSTRAINT uk_party_role_code UNIQUE (tenant_id, party_id, role_code)
);

CREATE TABLE IF NOT EXISTS party_park_relations (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL REFERENCES parties(id),
  park_id         BIGINT       NOT NULL REFERENCES parks(id),
  party_role_id   BIGINT       NOT NULL REFERENCES party_roles(id),
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
  started_at      TIMESTAMPTZ  NULL,
  ended_at        TIMESTAMPTZ  NULL,
  deleted_at      TIMESTAMPTZ  NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_ppr_active
  ON party_park_relations (tenant_id, party_id, park_id, party_role_id)
  WHERE status = 'ACTIVE' AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS party_risk_events (
  id                   BIGSERIAL PRIMARY KEY,
  tenant_id            BIGINT       NOT NULL,
  party_id             BIGINT       NOT NULL REFERENCES parties(id),
  event_type           VARCHAR(32)  NOT NULL,
  previous_risk_status VARCHAR(32)  NOT NULL,
  new_risk_status      VARCHAR(32)  NOT NULL,
  reason               VARCHAR(512) NOT NULL,
  operator_user_id     BIGINT       NULL,
  request_id           VARCHAR(64)  NULL,
  source               VARCHAR(32)  NULL,
  occurred_at          TIMESTAMPTZ  NOT NULL,
  created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pre_party ON party_risk_events (tenant_id, party_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS party_contacts (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL REFERENCES parties(id),
  name            VARCHAR(64)  NULL,
  phone           VARCHAR(32)  NULL,
  email           VARCHAR(128) NULL,
  role_label      VARCHAR(64)  NULL,
  is_primary      BOOLEAN      NOT NULL DEFAULT FALSE,
  linked_person_party_id BIGINT NULL,
  is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
  deleted_at      TIMESTAMPTZ  NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL
);

-- ---------------------------------------------------------------------------
-- party_addresses（ADR-003g；主档无 address 列）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_addresses (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL REFERENCES parties(id),
  address_type    VARCHAR(32)  NOT NULL
    -- REGISTERED|OFFICE|MAILING|BILLING|OTHER
  ,
  country_code    VARCHAR(8)   NULL,
  province        VARCHAR(64)  NULL,
  city            VARCHAR(64)  NULL,
  district        VARCHAR(64)  NULL,
  street          VARCHAR(128) NULL,
  detail          VARCHAR(255) NULL,
  postal_code     VARCHAR(32)  NULL,
  is_primary      BOOLEAN      NOT NULL DEFAULT FALSE,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL,
  deleted_at      TIMESTAMPTZ  NULL
);
CREATE INDEX IF NOT EXISTS idx_party_addr_party
  ON party_addresses (tenant_id, party_id, deleted_at);

-- 同 party + type 仅一条有效 primary（PG 部分唯一）
CREATE UNIQUE INDEX IF NOT EXISTS uk_party_addr_primary
  ON party_addresses (tenant_id, party_id, address_type)
  WHERE is_primary = TRUE AND deleted_at IS NULL AND status = 'ACTIVE';

-- 说明：PERSON 地址 API 首版关闭写入（应用层）；表可建以备未来 PII 控制后开放。
