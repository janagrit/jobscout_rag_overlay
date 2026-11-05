from pydantic import BaseModel, Field


class ProfileIndexRequest(BaseModel):
    # tenant_id and profile_id are supplied by the authenticated Worker only.
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    # Size limit is enforced in main.py so oversized input returns 413, as the contract says.
    profile_text: str = Field(min_length=1)


class JobInput(BaseModel):
    job_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)  # size limit -> 413 in main.py
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    ats_score: float | None = Field(default=None, ge=0, le=100)
    matched_keywords: list[str] = Field(default_factory=list, max_length=100)
    missing_keywords: list[str] = Field(default_factory=list, max_length=100)


class MatchExplainRequest(BaseModel):
    # tenant_id and profile_id are supplied by the authenticated Worker only.
    tenant_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    job: JobInput


class Evidence(BaseModel):
    source_id: str
    excerpt: str
    relevance_distance: float | None = None


class MatchExplainResponse(BaseModel):
    explanation: str
    strengths: list[str]
    gaps: list[str]
    evidence: list[Evidence]
    disclaimer: str
