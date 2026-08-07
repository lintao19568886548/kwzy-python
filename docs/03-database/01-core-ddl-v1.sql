-- =============================================================================
-- kwzy-python 核心库表 DDL v1
-- 数据库: MySQL 8.0+ / 也可迁移至 PostgreSQL（需微调语法）
-- 多租户: 默认共享库 + tenant_id；所有业务表含 tenant_id
-- 字符集: utf8mb4
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- 0. SaaS 租户
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  code            VARCHAR(64)  NOT NULL COMMENT '租户编码',
  name            VARCHAR(128) NOT NULL COMMENT '租户名称',
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE|DISABLED|PROVISIONING',
  db_strategy     VARCHAR(32)  NOT NULL DEFAULT 'SHARED' COMMENT 'SHARED|DEDICATED',
  dedicated_secret_ref VARCHAR(128) NULL COMMENT '独立库连接密钥引用（Vault/配置中心），禁止明文DSN',
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_tenants_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SaaS租户';

-- ---------------------------------------------------------------------------
-- 1. 身份与权限
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  username        VARCHAR(64)  NOT NULL,
  password_hash   VARCHAR(255) NOT NULL,
  real_name       VARCHAR(64)  NOT NULL DEFAULT '',
  phone           VARCHAR(32)  NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE|DISABLED',
  home_path       VARCHAR(128) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_users_tenant_username (tenant_id, username),
  KEY idx_users_tenant_phone (tenant_id, phone),
  CONSTRAINT fk_users_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户';

CREATE TABLE IF NOT EXISTS roles (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  code            VARCHAR(64)  NOT NULL,
  name            VARCHAR(64)  NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE',
  remark          VARCHAR(255) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_roles_tenant_code (tenant_id, code),
  CONSTRAINT fk_roles_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

CREATE TABLE IF NOT EXISTS permissions (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  code            VARCHAR(128) NOT NULL COMMENT '如 bill:issue',
  name            VARCHAR(128) NOT NULL,
  module          VARCHAR(64)  NOT NULL DEFAULT '',
  UNIQUE KEY uk_permissions_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限码字典';

CREATE TABLE IF NOT EXISTS role_permissions (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  role_id         BIGINT NOT NULL,
  permission_id   BIGINT NOT NULL,
  UNIQUE KEY uk_role_perm (role_id, permission_id),
  CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id),
  CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_roles (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  user_id         BIGINT NOT NULL,
  role_id         BIGINT NOT NULL,
  UNIQUE KEY uk_user_role (user_id, role_id),
  CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_park_scopes (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  user_id         BIGINT NOT NULL,
  park_id         BIGINT NOT NULL,
  UNIQUE KEY uk_user_park (user_id, park_id),
  KEY idx_ups_tenant_park (tenant_id, park_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户园区数据范围';

CREATE TABLE IF NOT EXISTS role_park_scopes (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  role_id         BIGINT NOT NULL,
  park_id         BIGINT NOT NULL,
  UNIQUE KEY uk_role_park (role_id, park_id),
  KEY idx_rps_tenant_park (tenant_id, park_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色园区数据范围';

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT       NOT NULL,
  token_hash      VARCHAR(128) NOT NULL,
  expires_at      DATETIME(3)  NOT NULL,
  revoked_at      DATETIME(3)  NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_rt_hash (token_hash),
  KEY idx_rt_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------------
-- 2. 园区与空间
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parks (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  name            VARCHAR(128) NOT NULL,
  address         VARCHAR(255) NOT NULL DEFAULT '',
  area            DECIMAL(12,2) NOT NULL DEFAULT 0,
  contact         VARCHAR(64)  NULL,
  manager         VARCHAR(64)  NULL,
  description     TEXT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE|INACTIVE',
  is_deleted      TINYINT(1)   NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_parks_tenant_status (tenant_id, status),
  CONSTRAINT fk_parks_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='园区';

CREATE TABLE IF NOT EXISTS buildings (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  name            VARCHAR(128) NOT NULL,
  building_type   VARCHAR(32)  NOT NULL DEFAULT 'FACTORY' COMMENT 'FACTORY|DORMITORY|MIXED|OTHER',
  address         VARCHAR(255) NOT NULL DEFAULT '',
  description     TEXT NULL,
  is_deleted      TINYINT(1)   NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_buildings_park (tenant_id, park_id),
  CONSTRAINT fk_buildings_park FOREIGN KEY (park_id) REFERENCES parks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='楼栋/厂房';

CREATE TABLE IF NOT EXISTS units (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  building_id     BIGINT       NOT NULL,
  code            VARCHAR(64)  NOT NULL COMMENT '单元编码',
  name            VARCHAR(128) NOT NULL,
  rentable_area   DECIMAL(12,2) NOT NULL DEFAULT 0,
  used_area       DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '投影=有效合同占用面积之和，非手工主数据',
  base_rent_price DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT '挂牌参考价',
  status          VARCHAR(32)  NOT NULL DEFAULT 'VACANT'
    COMMENT 'DRAFT|VACANT|RESERVED|OCCUPIED|MAINTENANCE|RETIRED',
  attributes_json JSON NULL COMMENT '层高/承重/消防/电梯等',
  is_deleted      TINYINT(1)   NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_units_building_code (building_id, code),
  KEY idx_units_park_status (tenant_id, park_id, status),
  CONSTRAINT fk_units_building FOREIGN KEY (building_id) REFERENCES buildings(id),
  CONSTRAINT fk_units_park FOREIGN KEY (park_id) REFERENCES parks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可租单元';

-- ---------------------------------------------------------------------------
-- 3. 入驻方与合同
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parties (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  name            VARCHAR(128) NOT NULL,
  contact_name    VARCHAR(64)  NULL,
  contact_phone   VARCHAR(32)  NOT NULL,
  credit_code     VARCHAR(64)  NULL COMMENT '统一社会信用代码',
  address         VARCHAR(255) NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'ACTIVE' COMMENT 'ACTIVE|BLACKLIST|ARCHIVED',
  remark          VARCHAR(255) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_parties_tenant_park (tenant_id, park_id),
  KEY idx_parties_phone (tenant_id, contact_phone),
  CONSTRAINT fk_parties_park FOREIGN KEY (park_id) REFERENCES parks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入驻方主体';

CREATE TABLE IF NOT EXISTS lease_contracts (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL,
  contract_no     VARCHAR(64)  NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'DRAFT'
    COMMENT 'DRAFT|PENDING_ACTIVE|ACTIVE|EXPIRING|RENEWED|TERMINATED|BREACHED|CANCELLED',
  start_date      DATE         NOT NULL,
  end_date        DATE         NOT NULL,
  increase_date   DATE         NULL,
  increase_rate   DECIMAL(8,4) NULL COMMENT '如 0.05=5%',
  deposit_amount  DECIMAL(14,2) NOT NULL DEFAULT 0,
  remark          VARCHAR(255) NULL,
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_lease_contract_no (tenant_id, contract_no),
  KEY idx_lease_party (tenant_id, party_id),
  KEY idx_lease_park_status (tenant_id, park_id, status),
  KEY idx_lease_end_date (tenant_id, end_date),
  CONSTRAINT fk_lease_party FOREIGN KEY (party_id) REFERENCES parties(id),
  CONSTRAINT fk_lease_park FOREIGN KEY (park_id) REFERENCES parks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租赁合同';

CREATE TABLE IF NOT EXISTS lease_contract_units (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  contract_id     BIGINT       NOT NULL,
  unit_id         BIGINT       NOT NULL,
  occupied_area   DECIMAL(12,2) NOT NULL DEFAULT 0,
  unit_rent_price DECIMAL(12,2) NOT NULL DEFAULT 0,
  UNIQUE KEY uk_lcu (contract_id, unit_id),
  KEY idx_lcu_unit (unit_id),
  CONSTRAINT fk_lcu_contract FOREIGN KEY (contract_id) REFERENCES lease_contracts(id),
  CONSTRAINT fk_lcu_unit FOREIGN KEY (unit_id) REFERENCES units(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='合同占用单元';

CREATE TABLE IF NOT EXISTS lease_terms (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  contract_id     BIGINT       NOT NULL,
  term_type       VARCHAR(32)  NOT NULL COMMENT 'INCREASE|RENT_FREE|OTHER',
  effective_date  DATE         NULL,
  end_date        DATE         NULL,
  rate            DECIMAL(8,4) NULL COMMENT '递增率等',
  amount          DECIMAL(14,2) NULL,
  description     VARCHAR(255) NULL,
  sort_order      INT          NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_lease_terms_contract (tenant_id, contract_id),
  CONSTRAINT fk_lease_terms_contract FOREIGN KEY (contract_id) REFERENCES lease_contracts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='合同条款行';

CREATE TABLE IF NOT EXISTS attachments (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  resource_type   VARCHAR(64)  NOT NULL COMMENT 'LEASE_CONTRACT|BILL|PARTY|LEAD|OTHER',
  resource_id     BIGINT       NOT NULL,
  file_name       VARCHAR(255) NOT NULL,
  content_type    VARCHAR(128) NULL,
  size_bytes      BIGINT       NULL,
  storage_key     VARCHAR(512) NOT NULL COMMENT '对象存储key或相对路径',
  checksum        VARCHAR(128) NULL,
  uploaded_by     BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_attachments_resource (tenant_id, resource_type, resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通用附件元数据';

-- ---------------------------------------------------------------------------
-- 4. 费项与账单
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fee_catalog (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NULL COMMENT 'NULL=系统预置',
  code            VARCHAR(32)  NOT NULL,
  name            VARCHAR(64)  NOT NULL,
  unit            VARCHAR(32)  NULL COMMENT 'm2/kwh/ton/...',
  is_active       TINYINT(1)   NOT NULL DEFAULT 1,
  sort_order      INT          NOT NULL DEFAULT 0,
  UNIQUE KEY uk_fee_code (tenant_id, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='费项字典';

CREATE TABLE IF NOT EXISTS bills (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL,
  contract_id     BIGINT       NULL,
  bill_no         VARCHAR(64)  NOT NULL,
  title           VARCHAR(128) NULL,
  project_name    VARCHAR(128) NULL,
  period_start    DATE         NOT NULL,
  period_end      DATE         NOT NULL,
  due_date        DATE         NULL,
  overdue_since   DATE         NULL COMMENT '首次逾期日；is_overdue由status+due_date+open_amount计算，status禁止OVERDUE',
  status          VARCHAR(32)  NOT NULL DEFAULT 'DRAFT'
    COMMENT 'DRAFT|ISSUED|PARTIALLY_PAID|PAID|VOID|DISCARDED（禁止OVERDUE）',
  total_amount    DECIMAL(14,2) NOT NULL DEFAULT 0,
  paid_amount     DECIMAL(14,2) NOT NULL DEFAULT 0,
  currency        VARCHAR(8)   NOT NULL DEFAULT 'CNY',
  source          VARCHAR(32)  NOT NULL DEFAULT 'MANUAL' COMMENT 'MANUAL|IMPORT|AI|METER',
  source_ref      VARCHAR(64)  NULL,
  remark          VARCHAR(255) NULL,
  issued_at       DATETIME(3)  NULL,
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_bills_no (tenant_id, bill_no),
  KEY idx_bills_party_period (tenant_id, party_id, period_start, period_end),
  KEY idx_bills_park_status (tenant_id, park_id, status),
  KEY idx_bills_due (tenant_id, due_date),
  KEY idx_bills_due_open (tenant_id, status, due_date),
  CONSTRAINT fk_bills_party FOREIGN KEY (party_id) REFERENCES parties(id),
  CONSTRAINT fk_bills_park FOREIGN KEY (park_id) REFERENCES parks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账单';

CREATE TABLE IF NOT EXISTS bill_lines (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  bill_id         BIGINT       NOT NULL,
  fee_code        VARCHAR(32)  NOT NULL,
  description     VARCHAR(255) NOT NULL DEFAULT '',
  quantity        DECIMAL(14,4) NOT NULL DEFAULT 0,
  unit_price      DECIMAL(14,6) NOT NULL DEFAULT 0,
  amount          DECIMAL(14,2) NOT NULL DEFAULT 0,
  meter_reading_from DECIMAL(14,4) NULL,
  meter_reading_to   DECIMAL(14,4) NULL,
  multiplier      DECIMAL(14,4) NULL DEFAULT 1,
  sort_order      INT          NOT NULL DEFAULT 0,
  meta_json       JSON NULL,
  KEY idx_bill_lines_bill (bill_id),
  CONSTRAINT fk_bill_lines_bill FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账单明细行';

-- ---------------------------------------------------------------------------
-- 5. 收款与催缴
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payments (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL,
  payment_no      VARCHAR(64)  NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  method          VARCHAR(32)  NOT NULL DEFAULT 'TRANSFER'
    COMMENT 'CASH|TRANSFER|WECHAT|ALIPAY|OTHER',
  paid_at         DATETIME(3)  NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'CONFIRMED' COMMENT 'CONFIRMED|REVERSED',
  operator_id     BIGINT       NULL,
  remark          VARCHAR(255) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_payments_no (tenant_id, payment_no),
  KEY idx_payments_party (tenant_id, party_id),
  CONSTRAINT fk_payments_party FOREIGN KEY (party_id) REFERENCES parties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收款单';

CREATE TABLE IF NOT EXISTS payment_allocations (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  payment_id      BIGINT       NOT NULL,
  bill_id         BIGINT       NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_pa_payment (payment_id),
  KEY idx_pa_bill (bill_id),
  CONSTRAINT fk_pa_payment FOREIGN KEY (payment_id) REFERENCES payments(id),
  CONSTRAINT fk_pa_bill FOREIGN KEY (bill_id) REFERENCES bills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='收款核销';

CREATE TABLE IF NOT EXISTS collection_cases (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL,
  bill_id         BIGINT       NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'OPEN'
    COMMENT 'OPEN|IN_PROGRESS|PROMISED|CLOSED|WRITTEN_OFF',
  level           VARCHAR(16)  NOT NULL DEFAULT 'L1' COMMENT 'L1|L2|L3',
  assignee_id     BIGINT       NULL,
  open_amount_snapshot DECIMAL(14,2) NULL COMMENT '建案时欠款快照',
  next_action_at  DATETIME(3)  NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_cc_bill (bill_id),
  KEY idx_cc_status (tenant_id, park_id, status),
  CONSTRAINT fk_cc_bill FOREIGN KEY (bill_id) REFERENCES bills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='催缴案件';

CREATE TABLE IF NOT EXISTS collection_records (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  case_id         BIGINT       NOT NULL,
  record_type     VARCHAR(32)  NOT NULL COMMENT 'SMS|CALL|VISIT|NOTE|SYSTEM',
  content         TEXT NULL,
  result          VARCHAR(64)  NULL,
  channel_ref     VARCHAR(128) NULL COMMENT '短信回执/外部通道ID',
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_cr_case (tenant_id, case_id),
  CONSTRAINT fk_cr_case FOREIGN KEY (case_id) REFERENCES collection_cases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='催缴记录（跟进闭环）';

-- ---------------------------------------------------------------------------
-- 6. 财务台账（简化）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ledger_entries (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  entry_no        VARCHAR(64)  NOT NULL,
  direction       VARCHAR(16)  NOT NULL COMMENT 'IN|OUT',
  category        VARCHAR(64)  NOT NULL,
  amount          DECIMAL(14,2) NOT NULL,
  occurred_at     DATETIME(3)  NOT NULL,
  ref_type        VARCHAR(32)  NULL COMMENT 'PAYMENT|BILL|PAYROLL|REIMBURSEMENT',
  ref_id          BIGINT       NULL,
  remark          VARCHAR(255) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_ledger_no (tenant_id, entry_no),
  KEY idx_ledger_park_time (tenant_id, park_id, occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务流水';

-- ---------------------------------------------------------------------------
-- 7. 招商线索（一期精简）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NOT NULL,
  name            VARCHAR(128) NOT NULL COMMENT '意向客户名',
  contact_phone   VARCHAR(32)  NOT NULL,
  agent_name      VARCHAR(64)  NULL,
  intent_level    VARCHAR(32)  NULL,
  intent_area     DECIMAL(12,2) NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'NEW'
    COMMENT 'NEW|CONTACTING|VISITING|NEGOTIATING|WON|LOST',
  owner_user_id   BIGINT       NULL,
  remark          VARCHAR(255) NULL,
  converted_party_id BIGINT    NULL,
  converted_contract_id BIGINT NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_leads_park_status (tenant_id, park_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='招商线索';

CREATE TABLE IF NOT EXISTS lead_activities (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  lead_id         BIGINT       NOT NULL,
  activity_type   VARCHAR(32)  NOT NULL COMMENT 'NOTE|CALL|VISIT|FEEDBACK',
  content         TEXT NULL,
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_la_lead (lead_id),
  CONSTRAINT fk_la_lead FOREIGN KEY (lead_id) REFERENCES leads(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='线索跟进';

-- ---------------------------------------------------------------------------
-- 8. AI / 导入任务（骨架）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_jobs (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NULL,
  job_type        VARCHAR(32)  NOT NULL COMMENT 'BILL_RECOGNIZE|CHAT|OTHER',
  status          VARCHAR(32)  NOT NULL DEFAULT 'PENDING'
    COMMENT 'PENDING|RUNNING|SUCCEEDED|FAILED|CANCELLED',
  input_meta      JSON NULL,
  result_meta     JSON NULL,
  error_message   VARCHAR(512) NULL,
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  finished_at     DATETIME(3)  NULL,
  KEY idx_ai_jobs_tenant_status (tenant_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI任务';

CREATE TABLE IF NOT EXISTS bill_import_jobs (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  park_id         BIGINT       NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'PENDING',
  file_name       VARCHAR(255) NULL,
  stats_json      JSON NULL,
  created_by      BIGINT       NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  finished_at     DATETIME(3)  NULL,
  KEY idx_bij_tenant (tenant_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账单导入任务';

-- ---------------------------------------------------------------------------
-- 9. 基础设施
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outbox_events (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  event_id        VARCHAR(64)  NOT NULL,
  event_type      VARCHAR(128) NOT NULL,
  aggregate_type  VARCHAR(64)  NULL,
  aggregate_id    VARCHAR(64)  NULL,
  payload         JSON         NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'NEW' COMMENT 'NEW|SENT|FAILED',
  retry_count     INT          NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  sent_at         DATETIME(3)  NULL,
  UNIQUE KEY uk_outbox_event_id (event_id),
  KEY idx_outbox_status (status, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件发件箱';

CREATE TABLE IF NOT EXISTS audit_logs (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT       NULL,
  request_id      VARCHAR(64)  NOT NULL DEFAULT '',
  action          VARCHAR(64)  NOT NULL,
  resource_type   VARCHAR(64)  NOT NULL,
  resource_id     VARCHAR(64)  NULL,
  park_id         BIGINT       NULL,
  detail_json     JSON NULL,
  client_ip       VARCHAR(64)  NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_audit_tenant_time (tenant_id, created_at),
  KEY idx_audit_resource (resource_type, resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审计日志';

-- ---------------------------------------------------------------------------
-- 10. 系统预置费项（tenant_id 为空表示全局模板，应用层复制到租户）
-- ---------------------------------------------------------------------------
INSERT INTO fee_catalog (tenant_id, code, name, unit, sort_order) VALUES
  (NULL, 'RENT', '厂房租金', 'm2', 10),
  (NULL, 'MANAGEMENT', '管理费', 'm2', 20),
  (NULL, 'SERVICE', '服务费', NULL, 30),
  (NULL, 'ELECTRIC', '电费', 'kWh', 40),
  (NULL, 'WATER', '水费', 'm3', 50),
  (NULL, 'TAX', '税费', NULL, 60),
  (NULL, 'OTHER', '其他', NULL, 99)
ON DUPLICATE KEY UPDATE name=VALUES(name);

SET FOREIGN_KEY_CHECKS = 1;
