SELECT COUNT(*) INTO @has_report_json
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'submissions'
  AND COLUMN_NAME = 'report_json';
SET @sql = IF(@has_report_json = 0,
  'ALTER TABLE submissions ADD COLUMN report_json TEXT',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_time_limit
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'time_limit';
SET @sql = IF(@has_time_limit = 0,
  'ALTER TABLE problems ADD COLUMN time_limit INT DEFAULT 3',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_memory_limit
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'memory_limit';
SET @sql = IF(@has_memory_limit = 0,
  'ALTER TABLE problems ADD COLUMN memory_limit INT DEFAULT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_pids_limit
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'pids_limit';
SET @sql = IF(@has_pids_limit = 0,
  'ALTER TABLE problems ADD COLUMN pids_limit INT DEFAULT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_file_size_limit
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'file_size_limit';
SET @sql = IF(@has_file_size_limit = 0,
  'ALTER TABLE problems ADD COLUMN file_size_limit INT DEFAULT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_allowlist
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'syscall_allowlist';
SET @sql = IF(@has_allowlist = 0,
  'ALTER TABLE problems ADD COLUMN syscall_allowlist TEXT',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) INTO @has_denylist
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'problems'
  AND COLUMN_NAME = 'syscall_denylist';
SET @sql = IF(@has_denylist = 0,
  'ALTER TABLE problems ADD COLUMN syscall_denylist TEXT',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE problems
MODIFY COLUMN problem_type ENUM('process', 'file', 'memory') NOT NULL;
