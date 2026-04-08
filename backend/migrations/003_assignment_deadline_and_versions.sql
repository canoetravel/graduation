SELECT COUNT(*) INTO @has_deadline_at
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'assignments'
  AND COLUMN_NAME = 'deadline_at';
SET @sql = IF(@has_deadline_at = 0,
  'ALTER TABLE assignments ADD COLUMN deadline_at DATETIME NULL AFTER teacher',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS submission_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student VARCHAR(50) NOT NULL,
    version_no INT NOT NULL,
    submission_id INT NOT NULL,
    commit_hash VARCHAR(64) NOT NULL,
    commit_message VARCHAR(255) NULL,
    total_score INT NOT NULL,
    status_summary VARCHAR(255) NULL,
    report_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_assignment_student_version (assignment_id, student, version_no),
    INDEX idx_version_assignment_student (assignment_id, student),
    INDEX idx_version_submission (submission_id),
    CONSTRAINT fk_versions_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_versions_submission
        FOREIGN KEY (submission_id) REFERENCES submissions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS submission_version_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_id INT NOT NULL,
    problem_id INT NOT NULL,
    code TEXT,
    output TEXT,
    score INT NOT NULL,
    status VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_version_items_version (version_id),
    INDEX idx_version_items_problem (problem_id),
    CONSTRAINT fk_version_items_version
        FOREIGN KEY (version_id) REFERENCES submission_versions(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_version_items_problem
        FOREIGN KEY (problem_id) REFERENCES problems(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
