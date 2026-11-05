import logging
import uuid
from contextlib import contextmanager

from fastapi import Depends, FastAPI, HTTPException
from app.config import MAX_JOB_DESCRIPTION_CHARS, MAX_PROFILE_CHARS
from app.schemas import ProfileIndexRequest, MatchExplainRequest, MatchExplainResponse
from app.security import require_service_token
from app.service import RAGService
from app.store import EmptyProfileError

logger = logging.getLogger("rag_service")

app = FastAPI(title="Job Scout RAG Service", version="0.1.0")
service_instance = None


def get_service():
    global service_instance
    if service_instance is None:
        service_instance = RAGService()
    return service_instance


@contextmanager
def upstream_guard(operation: str):
    """Turn model/vector-store failures into a generic 502.

    Only the exception type and a correlation ID are logged: exception messages can contain
    request data, so they are never logged or returned.
    """
    try:
        yield
    except (HTTPException, EmptyProfileError):
        raise
    except Exception as exc:
        correlation_id = uuid.uuid4().hex
        logger.error("%s failed: %s correlation_id=%s", operation, type(exc).__name__, correlation_id)
        raise HTTPException(
            status_code=502, detail="Upstream error", headers={"X-Correlation-ID": correlation_id}
        ) from None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/internal/v1/profiles/index", dependencies=[Depends(require_service_token)])
def index_profile(payload: ProfileIndexRequest):
    if len(payload.profile_text) > MAX_PROFILE_CHARS:
        raise HTTPException(status_code=413, detail="Profile is too large")
    try:
        with upstream_guard("index_profile"):
            count = get_service().index_profile(payload.tenant_id, payload.profile_id, payload.profile_text)
    except EmptyProfileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"indexed_chunks": count}


@app.post(
    "/internal/v1/matches/explain",
    response_model=MatchExplainResponse,
    dependencies=[Depends(require_service_token)],
)
def explain_match(payload: MatchExplainRequest):
    if len(payload.job.description) > MAX_JOB_DESCRIPTION_CHARS:
        raise HTTPException(status_code=413, detail="Job description is too large")
    with upstream_guard("explain_match"):
        result = get_service().explain_match(
            payload.tenant_id, payload.profile_id, payload.job.model_dump()
        )
    return {
        **result,
        "disclaimer": "This is an evidence-based assistant explanation, not a hiring prediction or guarantee.",
    }
