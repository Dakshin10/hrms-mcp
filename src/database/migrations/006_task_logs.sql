CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    employee_name TEXT NOT NULL,

    role TEXT,

    task_description TEXT,

    category TEXT,

    assumptions TEXT,

    actual_hours REAL,

    eta TEXT,

    confidence TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);