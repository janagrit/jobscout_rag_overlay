"""Shared fixtures: an offline fake OpenAI client, an in-memory Chroma store and an API client."""
import hashlib
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

import chromadb
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.service import RAGService
from app.store import ProfileStore

FIXTURES = Path(__file__).parent / "fixtures"
TEST_TOKEN = "test-secret-token"
EMBED_DIM = 64


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> dict:
    return json.loads(load_text(name))


def fake_embedding(text: str) -> list[float]:
    """Deterministic bag-of-words vector: texts sharing words are close in cosine space."""
    vec = [0.0] * EMBED_DIM
    for token in re.findall(r"\w+", text.lower()):
        bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % EMBED_DIM
        vec[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec] if any(vec) else [1.0 / math.sqrt(EMBED_DIM)] * EMBED_DIM


class _Embeddings:
    def __init__(self, parent):
        self.parent = parent

    def create(self, model, input):
        self.parent.embedding_calls.append({"model": model, "input": list(input)})
        if self.parent.embed_error:
            raise self.parent.embed_error
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_embedding(t)) for t in input])


class _Responses:
    def __init__(self, parent):
        self.parent = parent

    def create(self, **kwargs):
        self.parent.response_calls.append(kwargs)
        if self.parent.response_error:
            raise self.parent.response_error
        return SimpleNamespace(output_text=self.parent.output_text)


class FakeOpenAI:
    """Stands in for openai.OpenAI. Tests set `output_text` or the `*_error` attributes."""

    def __init__(self):
        self.embedding_calls: list[dict] = []
        self.response_calls: list[dict] = []
        self.output_text = json.dumps(
            {"explanation": "Fake explanation.", "strengths": [], "gaps": [], "evidence": []}
        )
        self.embed_error: Exception | None = None
        self.response_error: Exception | None = None
        self.embeddings = _Embeddings(self)
        self.responses = _Responses(self)


@pytest.fixture
def chroma_client():
    # EphemeralClient instances share one in-memory backend, so clear it around each test.
    client = chromadb.EphemeralClient()

    def wipe():
        for col in client.list_collections():
            client.delete_collection(col.name if hasattr(col, "name") else col)

    wipe()
    yield client
    wipe()


@pytest.fixture
def fake_openai():
    return FakeOpenAI()


@pytest.fixture
def store(chroma_client):
    return ProfileStore(client=chroma_client)


@pytest.fixture
def service(fake_openai, store):
    return RAGService(client=fake_openai, store=store)


@pytest.fixture
def cv_text():
    return load_text("cv_qa_engineer.txt")


@pytest.fixture
def api(monkeypatch, service):
    """TestClient wired to the offline service, authenticated with the test token."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.config.RAG_SERVICE_TOKEN", TEST_TOKEN)
    monkeypatch.setattr(main, "service_instance", service)
    client = TestClient(main.app, raise_server_exceptions=False)
    client.headers["X-Job-Scout-Service-Token"] = TEST_TOKEN
    return client
