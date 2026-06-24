CREATE TABLE IF NOT EXISTS timesheets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id TEXT NOT NULL,
  employee_name TEXT,
  task_name TEXT NOT NULL,
  department TEXT,
  eta_hours REAL,
  actual_hours REAL NOT NULL,
  ftr_flag INTEGER DEFAULT 1,
  rework_flag INTEGER DEFAULT 0,
  task_status TEXT,
  completion_date TEXT,
  month INTEGER,
  year INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_timesheets_employee
  ON timesheets(employee_id);
CREATE INDEX IF NOT EXISTS idx_timesheets_dept
  ON timesheets(department);
CREATE INDEX IF NOT EXISTS idx_timesheets_period
  ON timesheets(year, month);
