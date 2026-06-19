CREATE INDEX IF NOT EXISTS idx_employees_department
ON employees(department);

CREATE INDEX IF NOT EXISTS idx_employees_job_title
ON employees(job_title);

CREATE INDEX IF NOT EXISTS idx_employees_manager
ON employees(manager_id);

CREATE INDEX IF NOT EXISTS idx_employees_status
ON employees(status);

CREATE INDEX IF NOT EXISTS idx_employees_location
ON employees(location);