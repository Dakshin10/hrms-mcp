CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    event_type TEXT NOT NULL,

    actor TEXT,

    resource_type TEXT,

    resource_id TEXT,

    action TEXT NOT NULL,

    metadata TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);