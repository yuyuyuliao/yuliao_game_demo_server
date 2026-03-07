CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS land_plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price INTEGER NOT NULL,
    description TEXT NOT NULL,
    level INTEGER NOT NULL,
    growth_multiplier REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    growth_seconds INTEGER NOT NULL,
    price INTEGER NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crop_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    land_id INTEGER NOT NULL UNIQUE,
    crop_id INTEGER NOT NULL,
    planted_at DATETIME NOT NULL,
    last_state_update_at DATETIME NOT NULL,
    water REAL NOT NULL,
    fertility REAL NOT NULL,
    temperature REAL NOT NULL,
    FOREIGN KEY (land_id) REFERENCES land_plots(id),
    FOREIGN KEY (crop_id) REFERENCES crops(id)
);
