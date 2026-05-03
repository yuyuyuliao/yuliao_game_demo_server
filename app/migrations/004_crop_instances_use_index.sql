PRAGMA foreign_keys=OFF;

CREATE TABLE IF NOT EXISTS crop_instances_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    "index" INTEGER NOT NULL UNIQUE,
    crop_id INTEGER NOT NULL,
    planted_at DATETIME NOT NULL,
    last_state_update_at DATETIME NOT NULL,
    water REAL NOT NULL,
    fertility REAL NOT NULL,
    temperature REAL NOT NULL,
    FOREIGN KEY (crop_id) REFERENCES crops(id)
);

INSERT INTO crop_instances_new (id, "index", crop_id, planted_at, last_state_update_at, water, fertility, temperature)
SELECT id, land_id, crop_id, planted_at, last_state_update_at, water, fertility, temperature
FROM crop_instances;

DROP TABLE crop_instances;
ALTER TABLE crop_instances_new RENAME TO crop_instances;

PRAGMA foreign_keys=ON;
