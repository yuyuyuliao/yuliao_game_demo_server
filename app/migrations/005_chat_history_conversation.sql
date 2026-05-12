ALTER TABLE chat_history ADD COLUMN conversation_id TEXT NOT NULL DEFAULT 'default';
ALTER TABLE chat_history ADD COLUMN role TEXT NOT NULL DEFAULT 'user';
ALTER TABLE chat_history ADD COLUMN message_order INTEGER;

UPDATE chat_history
SET message_order = id
WHERE message_order IS NULL;

CREATE INDEX IF NOT EXISTS idx_chat_history_player_conversation_order
ON chat_history (player_id, conversation_id, message_order);
