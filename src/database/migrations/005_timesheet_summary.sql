CREATE TABLE IF NOT EXISTS timesheet_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    employee_name TEXT NOT NULL,

    role TEXT,

    month TEXT,

    total_tasks INTEGER DEFAULT 0,

    total_hours REAL DEFAULT 0,

    rework_tasks INTEGER DEFAULT 0,

    utilization_percentage REAL DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);