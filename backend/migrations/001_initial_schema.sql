CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    salt VARCHAR(32) NOT NULL,
    role ENUM('student', 'teacher') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    teacher VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS problems (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    problem_type ENUM('process', 'file', 'memory') NOT NULL,
    points INT NOT NULL,
    test_cases JSON,
    time_limit INT DEFAULT 3,
    memory_limit INT DEFAULT NULL,
    pids_limit INT DEFAULT NULL,
    file_size_limit INT DEFAULT NULL,
    syscall_allowlist TEXT,
    syscall_denylist TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_assignment_id (assignment_id),
    CONSTRAINT fk_problems_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student VARCHAR(50) NOT NULL,
    total_score INT NOT NULL,
    report_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_submission_assignment (assignment_id),
    CONSTRAINT fk_submissions_assignment
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS submission_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    submission_id INT NOT NULL,
    problem_id INT NOT NULL,
    code TEXT,
    output TEXT,
    score INT NOT NULL,
    status VARCHAR(10),
    time_used VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_submission_id (submission_id),
    INDEX idx_problem_id (problem_id),
    CONSTRAINT fk_items_submission
        FOREIGN KEY (submission_id) REFERENCES submissions(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_items_problem
        FOREIGN KEY (problem_id) REFERENCES problems(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
