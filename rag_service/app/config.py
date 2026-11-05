import os

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
RAG_SERVICE_TOKEN = os.getenv("RAG_SERVICE_TOKEN", "")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
TOP_K = int(os.getenv("TOP_K", "5"))
MAX_PROFILE_CHARS = 100_000
MAX_JOB_DESCRIPTION_CHARS = 30_000
