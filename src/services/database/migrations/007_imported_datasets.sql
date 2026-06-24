CREATE TABLE IF NOT EXISTS imported_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    table_name TEXT NOT NULL,

    source_file TEXT NOT NULL,

    row_count INTEGER DEFAULT 0,

    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
);