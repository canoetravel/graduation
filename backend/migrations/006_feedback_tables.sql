CREATE TABLE IF NOT EXISTS version_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version_id INT NOT NULL UNIQUE,
    assignment_id INT NOT NULL,
    student VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    summary_text TEXT,
    feedback_json LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_version_feedback_assignment_student (assignment_id, student),
    CONSTRAINT fk_version_feedback_version
        FOREIGN KEY (version_id) REFERENCES submission_versions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS student_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student VARCHAR(50) NOT NULL,
    based_on_version_count INT NOT NULL DEFAULT 0,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    summary_text TEXT,
    feedback_json LONGTEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_student_feedback (assignment_id, student),
    INDEX idx_student_feedback_assignment_student (assignment_id, student),
    CONSTRAINT fk_student_feedback_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
