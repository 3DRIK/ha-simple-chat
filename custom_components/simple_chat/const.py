"""Constants for Simple Chat."""

DOMAIN = "simple_chat"

STORAGE_VERSION = 1
STORAGE_KEY = "simple_chat.messages"

MAX_MESSAGES_STORED = 1000
DEFAULT_HISTORY_LIMIT = 100

EVENT_NEW_MESSAGE = "simple_chat_new_message"
EVENT_MESSAGE_DELETED = "simple_chat_message_deleted"
EVENT_MESSAGES_READ = "simple_chat_messages_read"
EVENT_TYPING = "simple_chat_typing"
EVENT_REACTION = "simple_chat_reaction"

FRONTEND_URL_BASE = "/simple_chat_frontend"
CARD_FILENAME = "simple-chat-card.js"
