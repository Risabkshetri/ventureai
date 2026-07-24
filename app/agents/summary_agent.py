from app.schemas.agent_outputs import SummaryAgentOutput
from app.services.llm_client import call_agent
from .base import load_prompt

def run_summary_agent(pitch_deck_text: str) -> SummaryAgentOutput:
    system_prompt = load_prompt("summary_prompt.md")
    return call_agent(
        agent_name="SummaryAgent",
        system_prompt=system_prompt,
        user_payload={"pitch_deck_text": pitch_deck_text},
        response_schema=SummaryAgentOutput,
    )
