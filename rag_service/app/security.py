import hmac
from fastapi import Header, HTTPException
from app import config


def require_service_token(x_job_scout_service_token: str | None = Header(default=None)) -> None:
    # Read the token per request (not at import) so rotation/overrides take effect.
    expected = config.RAG_SERVICE_TOKEN
    if not expected or not x_job_scout_service_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not hmac.compare_digest(expected.encode(), x_job_scout_service_token.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")
