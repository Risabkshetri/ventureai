from app.schemas.agent_outputs import ScoreAgentOutput
from app.services.llm_client import call_agent
from .base import load_prompt

def run_scoring_agent(pitch_deck_text: str) -> ScoreAgentOutput:
    system_prompt = load_prompt("scoring_prompt.md")
    return call_agent(
        agent_name="ScoringAgent",
        system_prompt=system_prompt,
        user_payload={"pitch_deck_text": pitch_deck_text},
        response_schema=ScoreAgentOutput,
    )
