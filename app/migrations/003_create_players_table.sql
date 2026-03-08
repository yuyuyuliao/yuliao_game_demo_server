CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account TEXT NOT NULL UNIQUE,
    -- 该字段仅用于存储密码哈希值，禁止写入明文密码
    password TEXT NOT NULL,
    gold INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1
);
