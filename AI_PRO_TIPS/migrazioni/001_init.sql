CREATE TABLE IF NOT EXISTS config_kv (
  k   VARCHAR(100) PRIMARY KEY,
  val TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS emit_log (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  kind       VARCHAR(50),
  created_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS error_log (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  source     VARCHAR(50),
  message    TEXT,
  created_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS betslips (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  code        VARCHAR(32) UNIQUE,
  short_id    CHAR(5) UNIQUE,
  total_odds  DECIMAL(10,2),
  legs_count  INT,
  status      ENUM('OPEN','PENDING','WON','LOST','VOID','CANCELLED') DEFAULT 'OPEN',
  created_at  DATETIME,
  settled_at  DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS selections (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  betslip_id  BIGINT NOT NULL,
  fixture_id  BIGINT NOT NULL,
  league_id   BIGINT,
  start_time  DATETIME NOT NULL,
  home        VARCHAR(64) NOT NULL,
  away        VARCHAR(64) NOT NULL,
  market      VARCHAR(32) NOT NULL,
  pick        VARCHAR(64) NOT NULL,
  odds        DECIMAL(8,2) NOT NULL,
  result      ENUM('PENDING','WON','LOST','VOID') DEFAULT 'PENDING',
  INDEX idx_sel_bid (betslip_id),
  INDEX idx_sel_fx  (fixture_id),
  CONSTRAINT fk_sel_bet FOREIGN KEY (betslip_id) REFERENCES betslips(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fixture_cache (
  fixture_id BIGINT PRIMARY KEY,
  odds_json  JSON,
  updated_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scheduled_messages (
  id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  short_id  CHAR(5) NOT NULL,
  kind      ENUM('value','combo','stat','story','banter') NOT NULL,
  payload   MEDIUMTEXT NOT NULL,
  send_at   DATETIME NOT NULL,
  sent_at   DATETIME NULL,
  status    ENUM('QUEUED','SENT','CANCELLED') DEFAULT 'QUEUED',
  notes     VARCHAR(255) NULL,
  INDEX idx_sched_send (status, send_at),
  INDEX idx_sched_sid  (short_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
