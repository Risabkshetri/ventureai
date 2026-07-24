from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StartupBase(BaseModel):
    startup_name: str
    industry: str | None = None
    stage: str | None = None
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None
    tagline: str | None = None
    team_size: str | None = None
    funding_raised: str | None = None
    linkedin_url: str | None = None


class StartupCreate(StartupBase):
    pass


class StartupUpdate(BaseModel):
    startup_name: str | None = None
    industry: str | None = None
    stage: str | None = None
    website: str | None = None
    description: str | None = None
    logo_url: str | None = None
    tagline: str | None = None
    team_size: str | None = None
    funding_raised: str | None = None
    linkedin_url: str | None = None


class StartupResponse(StartupBase):
    id: UUID
    founder_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PitchDeckUploadResponse(BaseModel):
    id: UUID
    status: str


class EvaluationResponse(BaseModel):
    id: UUID
    startup_id: UUID
    version: int
    status: str
    progress_stage: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationStatusResponse(BaseModel):
    id: UUID
    status: str
    progress_stage: str | None = None
    extraction_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExecutiveSummaryReport(BaseModel):
    executive_summary: str | None = None
    problem: str | None = None
    solution: str | None = None
    target_market: str | None = None
    business_model: str | None = None
    traction: str | None = None


class RiskItemReport(BaseModel):
    id: str | None = None
    category: str
    risk: str
    severity: str


class QuestionItemReport(BaseModel):
    id: str | None = None
    category: str
    question: str


class ScoresReport(BaseModel):
    market_opportunity: int | None = 0
    product_innovation: int | None = 0
    team_strength: int | None = 0
    business_model_score: int | None = 0
    competitive_advantage: int | None = 0
    traction_score: int | None = 0
    scalability: int | None = 0
    startup_score: int | None = 0
    score_reasoning: dict[str, str] | None = None


class EvaluationReportResponse(BaseModel):
    evaluation_id: str
    summary: ExecutiveSummaryReport
    risks: list[RiskItemReport]
    questions: list[QuestionItemReport]
    scores: ScoresReport

