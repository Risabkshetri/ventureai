from app.schemas.agent_outputs import QuestionAgentOutput
from app.services.llm_client import call_agent
from .base import load_prompt

def run_question_agent(pitch_deck_text: str) -> QuestionAgentOutput:
    system_prompt = load_prompt("question_prompt.md")
    return call_agent(
        agent_name="QuestionAgent",
        system_prompt=system_prompt,
        user_payload={"pitch_deck_text": pitch_deck_text},
        response_schema=QuestionAgentOutput,
    )
