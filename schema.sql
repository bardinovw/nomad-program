CREATE TABLE IF NOT EXISTS days (
    day_number INTEGER PRIMARY KEY,
    date TEXT,
    week INTEGER,
    theme TEXT,
    is_rest BOOLEAN
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY,
    day_number INTEGER REFERENCES days(day_number),
    type TEXT,
    title TEXT,
    status TEXT DEFAULT 'pending',
    deadline TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_map (
    theme TEXT PRIMARY KEY,
    status TEXT DEFAULT 'not_started'
);