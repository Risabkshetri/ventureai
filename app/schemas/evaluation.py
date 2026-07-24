from pydantic import BaseModel, Field


class SummaryAgentOutput(BaseModel):
    problem: str = Field(description="The problem the startup is solving")
    solution: str = Field(description="The startup's proposed solution")
    target_market: str = Field(description="The target market and size details")
    business_model: str = Field(description="The revenue model and monetization strategy")
    traction: str = Field(description="Current progress, customers, revenue, or pilots")
    executive_summary: str = Field(description="A high-level concise investor-ready summary of the startup")


class RiskItem(BaseModel):
    category: str = Field(description="Risk category (e.g., Financial, Competition, Regulatory, Product)")
    risk: str = Field(description="Detailed description of the identified risk")
    severity: str = Field(description="Risk severity level. Must be one of: 'low', 'medium', 'high'")


class RiskAgentOutput(BaseModel):
    risks: list[RiskItem] = Field(description="List of identified risks for the startup")


class QuestionItem(BaseModel):
    category: str = Field(description="Category of the question (e.g., Business Model, Growth, Technology)")
    question: str = Field(description="The suggested investor question to ask the founder")


class QuestionAgentOutput(BaseModel):
    questions: list[QuestionItem] = Field(description="Suggested questions for investors during meetings")


class ScoreReasoning(BaseModel):
    market_opportunity: str = Field(description="Reasoning for market opportunity score")
    product_innovation: str = Field(description="Reasoning for product and innovation score")
    team_strength: str = Field(description="Reasoning for team and founder strength score")
    business_model_score: str = Field(description="Reasoning for business model score")
    competitive_advantage: str = Field(description="Reasoning for competitive advantage score")
    traction_score: str = Field(description="Reasoning for traction score")
    scalability: str = Field(description="Reasoning for scalability score")


class ScoreAgentOutput(BaseModel):
    market_opportunity: int = Field(description="Score for market opportunity (0-100)", ge=0, le=100)
    product_innovation: int = Field(description="Score for product and innovation (0-100)", ge=0, le=100)
    team_strength: int = Field(description="Score for founder and team strength (0-100)", ge=0, le=100)
    business_model_score: int = Field(description="Score for business/revenue model viability (0-100)", ge=0, le=100)
    competitive_advantage: int = Field(description="Score for defensive moat and competition (0-100)", ge=0, le=100)
    traction_score: int = Field(description="Score for traction and current velocity (0-100)", ge=0, le=100)
    scalability: int = Field(description="Score for scalability potential (0-100)", ge=0, le=100)
    startup_score: int = Field(description="Overall consolidated score for the startup (0-100)", ge=0, le=100)
    score_reasoning: ScoreReasoning = Field(
        description="Reasoning details justifying each scoring dimension score"
    )
