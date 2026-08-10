-- Party DDL 草案 v1.3（终局：PostgreSQL 16 权威 + party_risk_events）
-- 设计 only：非已执行 migration。
--
-- 方言策略（ADR-003d）：
--   * 生产权威：PostgreSQL 16
--   * SQLite：本地开发/单元测试兼容；非生产；非约束唯一验证环境
--   * 非 MySQL 生产目标
--   * 行为冲突时以 PostgreSQL 16 为准
--
-- 下列 DDL 以 PostgreSQL 16 语法为权威示例；
-- SQLite 实现期由 Alembic 做有限兼容（类型/部分索引能力裁剪说明见注释）。

-- ---------------------------------------------------------------------------
-- parties
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parties (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_type      VARCHAR(32)  NOT NULL DEFAULT 'ORGANIZATION',
  name            VARCHAR(128) NOT NULL,
  contact_name    VARCHAR(64)  NULL,
  contact_phone   VARCHAR(32)  NULL,
  credit_code     VARCHAR(64)  NULL,  -- normalized; empty -> NULL
  address         VARCHAR(255) NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|INACTIVE|ARCHIVED
  risk_status     VARCHAR(32)  NOT NULL DEFAULT 'NORMAL',  -- NORMAL|BLACKLISTED
  -- 当前风险便捷字段（非历史）；完整历史见 party_risk_events
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
CREATE INDEX IF NOT EXISTS idx_parties_tenant_phone ON parties (tenant_id, contact_phone);

-- 首版不包含任何证件号列（ADR-003c）

-- ---------------------------------------------------------------------------
-- party_roles
-- ---------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_party_roles_party ON party_roles (tenant_id, party_id);

-- ---------------------------------------------------------------------------
-- party_park_relations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_park_relations (
  id              BIGSERIAL PRIMARY KEY,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL REFERENCES parties(id),
  park_id         BIGINT       NOT NULL REFERENCES parks(id),
  party_role_id   BIGINT       NOT NULL REFERENCES party_roles(id),
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|ENDED
  started_at      TIMESTAMPTZ  NULL,
  ended_at        TIMESTAMPTZ  NULL,
  deleted_at      TIMESTAMPTZ  NULL,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ  NULL
);

CREATE INDEX IF NOT EXISTS idx_ppr_tenant_party ON party_park_relations (tenant_id, party_id);
CREATE INDEX IF NOT EXISTS idx_ppr_tenant_park ON party_park_relations (tenant_id, park_id);
CREATE INDEX IF NOT EXISTS idx_ppr_role ON party_park_relations (tenant_id, party_role_id);

-- PostgreSQL 16 权威：ACTIVE 且未软删的部分唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS uk_ppr_active
  ON party_park_relations (tenant_id, party_id, park_id, party_role_id)
  WHERE status = 'ACTIVE' AND deleted_at IS NULL;

-- SQLite 开发兼容：同样支持 partial unique index（单测可用）
-- 但生产约束正确性必须以 PostgreSQL 集成测试验证。
--
-- 若未来其它方言不支持部分索引：禁止仅依赖 Application；
-- 须 active_guard 可空列 + UNIQUE 等 DB 最终保证（非当前生产路径）。

-- ---------------------------------------------------------------------------
-- party_risk_events（不可变业务风险历史，首版必建）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_risk_events (
  id                   BIGSERIAL PRIMARY KEY,
  tenant_id            BIGINT       NOT NULL,
  party_id             BIGINT       NOT NULL REFERENCES parties(id),
  event_type           VARCHAR(32)  NOT NULL,  -- BLACKLISTED|BLACKLIST_REMOVED
  previous_risk_status VARCHAR(32)  NOT NULL,
  new_risk_status      VARCHAR(32)  NOT NULL,
  reason               VARCHAR(512) NOT NULL,
  operator_user_id     BIGINT       NULL,
  request_id           VARCHAR(64)  NULL,
  source               VARCHAR(32)  NULL,  -- API|ADAPTER|SYSTEM
  occurred_at          TIMESTAMPTZ  NOT NULL,
  created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pre_party ON party_risk_events (tenant_id, party_id, occurred_at DESC);

-- 应用层禁止对 party_risk_events 执行 UPDATE/DELETE（可用 DB 权限/触发器加固，实现期可选）

-- ---------------------------------------------------------------------------
-- party_contacts
-- ---------------------------------------------------------------------------
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

CREATE INDEX IF NOT EXISTS idx_party_contacts_party
  ON party_contacts (tenant_id, party_id, is_deleted);

-- credit_code：PostgreSQL UNIQUE 允许多个 NULL；应用须把空串规范为 NULL。
