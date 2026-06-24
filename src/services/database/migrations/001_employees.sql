CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,

    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,

    email TEXT UNIQUE NOT NULL,
    phone_number TEXT,

    department TEXT NOT NULL,
    job_title TEXT NOT NULL,

    employment_type TEXT NOT NULL,

    date_of_joining TEXT NOT NULL,
    date_of_birth TEXT,

    gender TEXT,

    annual_salary_inr INTEGER,

    manager_id TEXT,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    location TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);