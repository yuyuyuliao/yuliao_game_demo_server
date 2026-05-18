CREATE TABLE IF NOT EXISTS player_conversation_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_player_conversation_windows_player_id
ON player_conversation_windows (player_id);
