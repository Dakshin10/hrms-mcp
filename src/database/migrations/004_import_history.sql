CREATE TABLE IF NOT EXISTS import_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_name TEXT NOT NULL,

    rows_processed INTEGER,

    rows_inserted INTEGER,

    rows_failed INTEGER,

    started_at TEXT,

    completed_at TEXT
);