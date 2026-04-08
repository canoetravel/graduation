CREATE TABLE IF NOT EXISTS plagiarism_ai_reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    problem_id INT NOT NULL,
    submission_a INT NOT NULL,
    submission_b INT NOT NULL,
    similarity_score DECIMAL(6,4) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    summary_text TEXT,
    report_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_ai_pair (assignment_id, problem_id, submission_a, submission_b),
    INDEX idx_ai_assignment (assignment_id),
    INDEX idx_ai_problem (problem_id),
    CONSTRAINT fk_ai_reports_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
