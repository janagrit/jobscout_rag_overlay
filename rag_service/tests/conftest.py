"""Shared fixtures: an offline fake OpenAI client, an in-memory Chroma store and an API client."""
import hashlib
import json
import math
import os
import re
from collections import defaultdict
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


# ---------------------------------------------------------------------------
# Results table printed at the end of every run (and written to the GitHub job summary in CI).
# ---------------------------------------------------------------------------
def _collect(stats) -> tuple[dict, list[str]]:
    """Group test reports by file: passed/failed/skipped counts and total time."""
    rows = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0, "time": 0.0})
    failures = []
    for key in ("passed", "failed", "error", "skipped"):
        for report in stats.get(key, []):
            nodeid = getattr(report, "nodeid", "")
            if not nodeid:
                continue
            row = rows[Path(nodeid.split("::")[0]).name]
            row["time"] += getattr(report, "duration", 0.0)
            if key == "passed" and report.when == "call":
                row["passed"] += 1
            elif key in ("failed", "error"):
                row["failed"] += 1
                failures.append(nodeid)
            elif key == "skipped":
                row["skipped"] += 1
    # Durations of passing setup/teardown phases are not in stats; call time dominates anyway.
    return dict(sorted(rows.items())), failures


def _coverage(config):
    plugin = config.pluginmanager.getplugin("_cov")
    total = getattr(plugin, "cov_total", None) if plugin else None
    minimum = getattr(getattr(plugin, "options", None), "cov_fail_under", None) if plugin else None
    return total, minimum


def _totals(rows):
    return {k: sum(r[k] for r in rows.values()) for k in ("passed", "failed", "skipped", "time")}


def _coverage_text(total, minimum):
    if total is None:
        return "not measured"
    ok = minimum is None or total >= minimum
    floor = f" (minimum {minimum:g}%)" if minimum is not None else ""
    return f"{total:.1f}% {'✅' if ok else '❌'}{floor}"


@pytest.hookimpl(trylast=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    rows, failures = _collect(terminalreporter.stats)
    if not rows:
        return
    total = _totals(rows)
    deselected = len(terminalreporter.stats.get("deselected", []))
    cov_total, cov_min = _coverage(config)
    width = max(len(name) for name in [*rows, "Coverage (app/)"]) + 2

    tr = terminalreporter
    tr.write_sep("=", "Test results")
    tr.write_line(f"{'Suite':<{width}}{'Passed':>8}{'Failed':>8}{'Skipped':>9}{'Time':>9}")
    for name, r in [*rows.items(), ("TOTAL", total)]:
        line = f"{name:<{width}}{r['passed']:>8}{r['failed']:>8}{r['skipped']:>9}{r['time']:>8.2f}s"
        if name == "TOTAL" and deselected:
            line += f"   ({deselected} deselected)"
        tr.write_line(line, bold=name == "TOTAL", red=name == "TOTAL" and r["failed"] > 0)
    tr.write_line(f"{'Coverage (app/)':<{width}}{_coverage_text(cov_total, cov_min)}", bold=True)
    if failures:
        tr.write_line("Failed tests:", red=True)
        for nodeid in failures:
            tr.write_line(f"  {nodeid}", red=True)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        lines = ["## Test results", "", "| Suite | Passed | Failed | Skipped | Time |", "|---|---:|---:|---:|---:|"]
        for name, r in rows.items():
            lines.append(f"| `{name}` | {r['passed']} | {r['failed']} | {r['skipped']} | {r['time']:.2f}s |")
        lines.append(f"| **Total** | **{total['passed']}** | **{total['failed']}** | **{total['skipped']}** | {total['time']:.2f}s |")
        lines += ["", f"**Coverage (app/):** {_coverage_text(cov_total, cov_min)}"]
        if deselected:
            lines.append(f"\n{deselected} tests deselected (live model checks run only with `pytest -m live`).")
        if failures:
            lines += ["", "**Failed tests:**", *[f"- `{n}`" for n in failures]]
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
