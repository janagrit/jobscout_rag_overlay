import os
from pathlib import Path

from dotenv import load_dotenv

# Load rag_service/.env regardless of the working directory; real env vars take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
RAG_SERVICE_TOKEN = os.getenv("RAG_SERVICE_TOKEN", "")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
TOP_K = int(os.getenv("TOP_K", "5"))
MAX_PROFILE_CHARS = 100_000
MAX_JOB_DESCRIPTION_CHARS = 30_000
