"""LLM client layer for VentureAI agents.

Provides a single reusable `call_agent` function that:
  1. Sends a system prompt + JSON user payload to Groq with native JSON mode.
  2. Parses the response via JSON parsing.
  3. On parse/validation failure, re-prompts once with a correction message.
  4. On double failure, raises `AgentFailureError` — callers decide what to do.

Do NOT import individual agents here; this module has no knowledge of agent schemas.
Agent-specific Pydantic models are defined per-agent and passed in via `response_schema`.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Typed return for failed agents ────────────────────────────────────────────

T = TypeVar("T", bound=BaseModel)

class AgentFailureError(Exception):
    """Raised when call_agent exhausts all retries and cannot produce valid output.

    Attributes:
        agent_name: Name of the agent that failed (for logging / orchestrator decisions).
        last_error: The last exception that caused the failure.
    """

    def __init__(self, agent_name: str, last_error: Exception) -> None:
        self.agent_name = agent_name
        self.last_error = last_error
        super().__init__(f"Agent '{agent_name}' failed after retries: {last_error}")


# ── Core helper ───────────────────────────────────────────────────────────────

def call_agent(
    agent_name: str,
    system_prompt: str,
    user_payload: dict[str, Any],
    response_schema: type[T],
) -> T:
    """Send a structured request to Groq and return a validated Pydantic model.

    Args:
        agent_name: Human-readable name used in logging and error messages.
        system_prompt: The agent's system-role instruction.
        user_payload: Dict that will be JSON-serialised and sent as the user turn.
        response_schema: A Pydantic BaseModel subclass that describes the expected output.

    Returns:
        A validated instance of `response_schema`.

    Raises:
        AgentFailureError: If all retries and correction re-prompts fail.
    """
    user_message = json.dumps(user_payload, ensure_ascii=False, indent=2)

    # Groq JSON Mode requires the word 'json' to be in the prompt or messages
    if "json" not in system_prompt.lower() and "json" not in user_message.lower():
        system_prompt += "\nOutput must be returned in JSON format."

    client = Groq(api_key=settings.GROQ_API_KEY)
    max_retries = 5
    backoff = 3.0
    
    generation_config = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    raw_text = ""
    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(**generation_config)
            raw_text = completion.choices[0].message.content or ""
            break
        except Exception as e:
            is_rate_limit = (
                "429" in str(e) or
                "rate" in str(e).lower() or
                "quota" in str(e).lower() or
                "exhausted" in str(e).lower()
            )
            if is_rate_limit and attempt < max_retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.warning(
                    "[%s] Groq API rate limit hit. Retrying in %.1fs (Attempt %d/%d)... Error: %s",
                    agent_name,
                    sleep_time,
                    attempt,
                    max_retries,
                    e
                )
                time.sleep(sleep_time)
            else:
                logger.error("[%s] Unexpected error on initial Groq call: %s", agent_name, e)
                raise AgentFailureError(agent_name, e) from e

    try:
        data = json.loads(raw_text)
        return response_schema.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "[%s] Groq initial response failed validation (%s: %s). Retrying with correction.",
            agent_name,
            type(exc).__name__,
            exc,
        )

    # ── Attempt 2: correction re-prompt ──────────────────────────────────────
    correction_message = (
        "Your previous output was invalid JSON; return ONLY valid JSON matching the schema."
    )
    
    generation_config_retry = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": raw_text},
            {"role": "user", "content": correction_message}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }

    raw_text_retry = ""
    for attempt in range(1, max_retries + 1):
        try:
            completion = client.chat.completions.create(**generation_config_retry)
            raw_text_retry = completion.choices[0].message.content or ""
            break
        except Exception as e:
            is_rate_limit = (
                "429" in str(e) or
                "rate" in str(e).lower() or
                "quota" in str(e).lower() or
                "exhausted" in str(e).lower()
            )
            if is_rate_limit and attempt < max_retries:
                sleep_time = backoff * (2 ** (attempt - 1))
                logger.warning(
                    "[%s] Groq API rate limit hit on retry. Retrying in %.1fs (Attempt %d/%d)... Error: %s",
                    agent_name,
                    sleep_time,
                    attempt,
                    max_retries,
                    e
                )
                time.sleep(sleep_time)
            else:
                logger.error("[%s] Unexpected error on Groq correction call: %s", agent_name, e)
                raise AgentFailureError(agent_name, e) from e

    try:
        data_retry = json.loads(raw_text_retry)
        return response_schema.model_validate(data_retry)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.error(
            "[%s] Groq correction re-prompt also failed (%s: %s). Giving up.",
            agent_name,
            type(exc).__name__,
            exc,
        )
        raise AgentFailureError(agent_name, exc) from exc
