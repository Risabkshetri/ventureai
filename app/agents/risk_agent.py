from app.schemas.agent_outputs import RiskAgentOutput
from app.services.llm_client import call_agent
from .base import load_prompt

def run_risk_agent(pitch_deck_text: str) -> RiskAgentOutput:
    system_prompt = load_prompt("risk_prompt.md")
    return call_agent(
        agent_name="RiskAgent",
        system_prompt=system_prompt,
        user_payload={"pitch_deck_text": pitch_deck_text},
        response_schema=RiskAgentOutput,
    )
