import hmac
from fastapi import Header, HTTPException
from app.config import RAG_SERVICE_TOKEN


def require_service_token(x_job_scout_service_token: str | None = Header(default=None)) -> None:
    expected = RAG_SERVICE_TOKEN
    if not expected or not x_job_scout_service_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not hmac.compare_digest(expected, x_job_scout_service_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
