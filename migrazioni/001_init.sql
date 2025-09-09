-- =========================================================
-- AI_PRO_TIPS / migrazioni / 001_init.sql
-- Schema completo e coerente con il progetto
-- =========================================================

-- KV di configurazione leggera
CREATE TABLE IF NOT EXISTS config_kv (
  k   VARCHAR(100) PRIMARY KEY,
  val TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Log contenuti emessi (anti-flood / statistiche)
CREATE TABLE IF NOT EXISTS emit_log (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  kind       VARCHAR(50),
  created_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Errori applicativi
CREATE TABLE IF NOT EXISTS error_log (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  source     VARCHAR(50),
  message    TEXT,
  created_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Schedine
CREATE TABLE IF NOT EXISTS betslips (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  code        VARCHAR(32) UNIQUE,  -- es: 091245-123
  short_id    CHAR(5) UNIQUE,      -- es: 48316 (ID umano per admin)
  total_odds  DECIMAL(10,2),
  legs_count  INT,
  status      ENUM('OPEN','PENDING','WON','LOST','VOID','CANCELLED') DEFAULT 'OPEN',
  created_at  DATETIME,
  settled_at  DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Selezioni (gambe)
CREATE TABLE IF NOT EXISTS selections (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  betslip_id  BIGINT NOT NULL,
  fixture_id  BIGINT NOT NULL,
  league_id   BIGINT,
  start_time  DATETIME NOT NULL,   -- kickoff UTC (consigliato), render in locale nei messaggi
  home        VARCHAR(64) NOT NULL,
  away        VARCHAR(64) NOT NULL,
  market      VARCHAR(32) NOT NULL, -- es: '1X','Under 3.5','Over 0.5','DNB Home','1','2','Home to Score','BTTS Yes'
  pick        VARCHAR(64) NOT NULL, -- di solito = market (se normalize)
  odds        DECIMAL(8,2) NOT NULL, -- quota Bet365
  result      ENUM('PENDING','WON','LOST','VOID') DEFAULT 'PENDING',
  INDEX idx_sel_bid (betslip_id),
  INDEX idx_sel_fx  (fixture_id),
  CONSTRAINT fk_sel_bet FOREIGN KEY (betslip_id) REFERENCES betslips(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Cache fixture (snapshot odds/markets per favorita, supporto live alert)
CREATE TABLE IF NOT EXISTS fixture_cache (
  fixture_id BIGINT PRIMARY KEY,
  odds_json  JSON,
  updated_at DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Coda invii (anteprime complete + orari T-3h, controllata da admin)
CREATE TABLE IF NOT EXISTS scheduled_messages (
  id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  short_id  CHAR(5) NOT NULL,  -- collega a betslip.short_id (o ID fittizio per contenuti non-bet)
  kind      ENUM('value','combo','stat','story','banter') NOT NULL,
  payload   MEDIUMTEXT NOT NULL,  -- messaggio HTML già renderizzato (come uscirà in canale)
  send_at   DATETIME NOT NULL,    -- orario programmato di invio (>= 08:00 locale / T-3h dalla prima partita della schedina)
  sent_at   DATETIME NULL,
  status    ENUM('QUEUED','SENT','CANCELLED') DEFAULT 'QUEUED',
  notes     VARCHAR(255) NULL,
  INDEX idx_sched_send (status, send_at),
  INDEX idx_sched_sid  (short_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indici utili (se servisse ricreare rapidamente)
-- CREATE INDEX idx_bets_status ON betslips(status);
-- CREATE INDEX idx_sched_status ON scheduled_messages(status);

-- Fine migrazione
