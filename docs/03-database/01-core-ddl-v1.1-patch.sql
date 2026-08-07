-- =============================================================================
-- kwzy-python DDL v1.1 patch（阶段 05.1 · 架构评审 P0）
-- 在 01-core-ddl-v1.sql 基线之上执行；可重复执行需人工确认环境
-- =============================================================================
-- 变更摘要：
--   P0-1  Bill 去掉 OVERDUE 主状态，增加 overdue_since；列表用 is_overdue 计算
--   P0-2  lease_terms + attachments 对齐领域
--   P0-9  tenants.dedicated_dsn → dedicated_secret_ref
--   P0-4  party_contacts
--   其它  ai_job_items、number_sequences、idempotency_keys、page_access_proofs
--         bills.contract_id FK、inbox_consume_log、menus（可选导航）
-- =============================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- P0-9: 独立库不再存明文 DSN
-- ---------------------------------------------------------------------------
-- 若列仍存在则重命名思路：新增 secret_ref，废弃 dedicated_dsn
ALTER TABLE tenants
  ADD COLUMN IF NOT EXISTS dedicated_secret_ref VARCHAR(128) NULL
    COMMENT '独立库连接密钥引用ID（Vault/KMS/配置中心），禁止存明文DSN' AFTER db_strategy;

-- MySQL 8.0 无 IF NOT EXISTS for ADD COLUMN in older versions — 使用存储过程兼容见下
-- 若报错 Duplicate column，忽略即可

-- 建议手工：不再使用 dedicated_dsn；若已有列可：
-- ALTER TABLE tenants DROP COLUMN dedicated_dsn;

-- ---------------------------------------------------------------------------
-- P0-1: bills 状态模型
-- ---------------------------------------------------------------------------
ALTER TABLE bills
  MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'DRAFT'
    COMMENT 'DRAFT|ISSUED|PARTIALLY_PAID|PAID|VOID|DISCARDED（禁止OVERDUE）';

-- overdue_since: 首次判定逾期日期；结清/作废清空
-- 若列已存在会失败，部署时按环境跳过
ALTER TABLE bills
  ADD COLUMN overdue_since DATE NULL
    COMMENT '首次逾期日期；is_overdue 由 status+due_date+open_amount 计算' AFTER due_date;

-- 索引：逾期扫描（应用层条件 status in ISSUED,PARTIALLY_PAID and due_date < today）
ALTER TABLE bills
  ADD INDEX idx_bills_due_open (tenant_id, status, due_date);

-- contract_id FK（可空）
-- ALTER TABLE bills ADD CONSTRAINT fk_bills_contract
--   FOREIGN KEY (contract_id) REFERENCES lease_contracts(id);
-- 若历史脏数据可暂缓 FK

-- ---------------------------------------------------------------------------
-- P0-2: 合同条款 / 附件 — 已并入 01-core-ddl-v1.sql 基线
-- 若旧库仅有 v1 无条款表，可单独执行下列 CREATE（与基线一致，IF NOT EXISTS）
-- ---------------------------------------------------------------------------
-- （见基线 lease_terms / attachments）

-- 催缴记录命名冻结：collection_actions → collection_records
-- 若旧实验库已建 collection_actions：
-- RENAME TABLE collection_actions TO collection_records;
-- ALTER TABLE collection_records CHANGE action_type record_type VARCHAR(32) NOT NULL;

-- ---------------------------------------------------------------------------
-- Party 多联系人
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS party_contacts (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  party_id        BIGINT       NOT NULL,
  name            VARCHAR(64)  NULL,
  phone           VARCHAR(32)  NOT NULL,
  role_label      VARCHAR(64)  NULL COMMENT '财务/法人/经办等',
  is_primary      TINYINT(1)   NOT NULL DEFAULT 0,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_party_contacts_party (tenant_id, party_id),
  CONSTRAINT fk_party_contacts_party FOREIGN KEY (party_id) REFERENCES parties(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入驻方联系人';

-- ---------------------------------------------------------------------------
-- AI 识别明细（人工复核）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_job_items (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  job_id          BIGINT       NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'PENDING'
    COMMENT 'PENDING|MATCHED|COMMITTED|REJECTED|FAILED',
  confidence      DECIMAL(5,4) NULL,
  draft_json      JSON         NOT NULL COMMENT 'BillDraft 结构',
  party_id        BIGINT       NULL,
  bill_id         BIGINT       NULL COMMENT 'commit 后账单',
  error_message   VARCHAR(512) NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  KEY idx_ai_job_items_job (tenant_id, job_id),
  CONSTRAINT fk_ai_job_items_job FOREIGN KEY (job_id) REFERENCES ai_jobs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI任务明细项';

-- ---------------------------------------------------------------------------
-- 编号序列 / 幂等 / 页面二次验证 / 消费日志
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS number_sequences (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  biz_type        VARCHAR(32)  NOT NULL COMMENT 'CONTRACT|BILL|PAYMENT|LEDGER',
  period_key      VARCHAR(16)  NOT NULL DEFAULT '' COMMENT 'yyyyMM 或空',
  next_val        BIGINT       NOT NULL DEFAULT 1,
  updated_at      DATETIME(3)  NULL ON UPDATE CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_number_seq (tenant_id, biz_type, period_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='业务编号序列';

CREATE TABLE IF NOT EXISTS idempotency_keys (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT       NULL,
  idem_key        VARCHAR(128) NOT NULL,
  operation       VARCHAR(64)  NOT NULL,
  request_hash    VARCHAR(128) NULL,
  response_json   JSON         NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  expires_at      DATETIME(3)  NULL,
  UNIQUE KEY uk_idem (tenant_id, idem_key),
  KEY idx_idem_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='写操作幂等键';

CREATE TABLE IF NOT EXISTS page_access_proofs (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT       NOT NULL,
  purpose         VARCHAR(64)  NOT NULL COMMENT 'COLLECTION_SMS|OTHER',
  proof_hash      VARCHAR(128) NOT NULL,
  expires_at      DATETIME(3)  NOT NULL,
  used_at         DATETIME(3)  NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_proof_hash (proof_hash),
  KEY idx_proof_user (tenant_id, user_id, purpose)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='高敏页面二次验证凭证';

CREATE TABLE IF NOT EXISTS inbox_consume_log (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  consumer_name   VARCHAR(64)  NOT NULL,
  event_id        VARCHAR(64)  NOT NULL,
  status          VARCHAR(32)  NOT NULL DEFAULT 'PROCESSED',
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  UNIQUE KEY uk_inbox (consumer_name, event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件消费幂等日志';

-- ---------------------------------------------------------------------------
-- 可选：动态菜单（v1.1 预留，一期可用静态路由）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS menus (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT       NULL COMMENT 'NULL=模板',
  parent_id       BIGINT       NULL,
  name            VARCHAR(64)  NOT NULL,
  path            VARCHAR(128) NOT NULL DEFAULT '',
  component       VARCHAR(128) NULL,
  auth_code       VARCHAR(128) NULL,
  sort_order      INT          NOT NULL DEFAULT 0,
  status          TINYINT      NOT NULL DEFAULT 1,
  meta_json       JSON         NULL,
  created_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY idx_menus_tenant (tenant_id, parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜单（可选）';

CREATE TABLE IF NOT EXISTS role_menus (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id       BIGINT NOT NULL,
  role_id         BIGINT NOT NULL,
  menu_id         BIGINT NOT NULL,
  UNIQUE KEY uk_role_menu (role_id, menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色菜单';

-- ---------------------------------------------------------------------------
-- units.used_area 注释强化（投影）
-- ---------------------------------------------------------------------------
ALTER TABLE units
  MODIFY COLUMN used_area DECIMAL(12,2) NOT NULL DEFAULT 0
    COMMENT '投影字段=有效合同占用面积之和，禁止业务直接作为主数据写入';
