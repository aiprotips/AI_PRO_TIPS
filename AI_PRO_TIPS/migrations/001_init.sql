-- Create database and user if needed (run on your MySQL server)
-- CREATE DATABASE aiptips DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- CREATE USER 'aiptips'@'%' IDENTIFIED BY 'PASSWORD_FORTISSIMA';
-- GRANT ALL PRIVILEGES ON aiptips.* TO 'aiptips'@'%';
-- FLUSH PRIVILEGES;

-- Use the database
-- USE aiptips;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  telegram_chat_id BIGINT NOT NULL UNIQUE,
  username VARCHAR(64) NULL,
  lang VARCHAR(8) DEFAULT 'it',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS betslips (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(20) NOT NULL UNIQUE,
  status ENUM('PENDING','WON','LOST','CANCELLED') NOT NULL DEFAULT 'PENDING',
  total_odds DECIMAL(8,2) NOT NULL,
  legs_count INT NOT NULL,
  legs_won INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  settled_at TIMESTAMP NULL DEFAULT NULL,
  INDEX idx_bets_status (status),
  INDEX idx_bets_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS selections (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  betslip_id BIGINT NOT NULL,
  fixture_id BIGINT NOT NULL,
  league_id INT NULL,
  start_time DATETIME NOT NULL,
  home VARCHAR(64) NOT NULL,
  away VARCHAR(64) NOT NULL,
  market VARCHAR(40) NOT NULL,
  pick VARCHAR(40) NOT NULL,
  odds DECIMAL(8,2) NOT NULL,
  result ENUM('PENDING','WON','LOST','VOID') NOT NULL DEFAULT 'PENDING',
  resolved_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sel_betslip FOREIGN KEY (betslip_id) REFERENCES betslips(id) ON DELETE CASCADE,
  INDEX idx_sel_fixture (fixture_id),
  INDEX idx_sel_start (start_time),
  INDEX idx_sel_betslip (betslip_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS emit_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  kind VARCHAR(32) NOT NULL,
  at DATETIME NOT NULL,
  text_hash CHAR(64) NULL,
  INDEX idx_emit_day (at),
  INDEX idx_emit_kind_day (kind, at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS config_kv (
  k VARCHAR(64) PRIMARY KEY,
  v TEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS error_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  src VARCHAR(64) NOT NULL,
  message TEXT NOT NULL,
  payload TEXT NULL,
  INDEX idx_err_at (at),
  INDEX idx_err_src (src)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fixture_cache (
  fixture_id BIGINT PRIMARY KEY,
  league_id INT NOT NULL,
  start_time DATETIME NOT NULL,
  status VARCHAR(16) NOT NULL,
  home VARCHAR(64) NOT NULL,
  away VARCHAR(64) NOT NULL,
  odds_json JSON NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_fx_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
