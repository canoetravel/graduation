ALTER TABLE problems
MODIFY COLUMN problem_type ENUM('normal', 'process', 'file', 'memory') NOT NULL;
