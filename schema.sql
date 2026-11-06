CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    monthly_limit REAL NOT NULL CHECK (monthly_limit >= 0),
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    amount REAL NOT NULL CHECK (amount > 0),
    date TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_expenses_category_date ON expenses(category_id, date);