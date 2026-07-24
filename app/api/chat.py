import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from groq import Groq

from app.api.deps import require_role
from app.core.supabase_client import supabase_service_client
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
groq_client = Groq(api_key=settings.GROQ_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None  # If None, a new session will be created


class ChatResponse(BaseModel):
    answer: str
    session_id: str


class CreateSessionRequest(BaseModel):
    startup_id: Optional[str] = None
    title: Optional[str] = "New Chat"


class UpdateSessionRequest(BaseModel):
    is_pinned: Optional[bool] = None
    title: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Fetch startup context for AI prompt
# ─────────────────────────────────────────────────────────────────────────────

def _get_startup_context(startup_id: str) -> str:
    try:
        eval_resp = (
            supabase_service_client.table("evaluations")
            .select("id")
            .eq("startup_id", startup_id)
            .eq("status", "completed")
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        if eval_resp.data:
            eval_id = eval_resp.data[0]["id"]
            summary_resp = (
                supabase_service_client.table("executive_summaries")
                .select("*")
                .eq("evaluation_id", eval_id)
                .execute()
            )
            if summary_resp.data:
                s = summary_resp.data[0]
                if not isinstance(s, dict):
                    return "No context available."
                return (
                    f"Startup Problem: {s.get('problem', '')}\n"
                    f"Startup Solution: {s.get('solution', '')}\n"
                    f"Business Model: {s.get('business_model', '')}\n"
                    f"Traction: {s.get('traction', '')}"
                )
    except Exception:
        pass
    return "No context available."


# ─────────────────────────────────────────────────────────────────────────────
# GET /chat/sessions — list all sessions for current user
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions", summary="Get all chat sessions for the current user")
def get_chat_sessions(current_user: dict = Depends(require_role("investor"))):
    user_id = current_user["id"]
    resp = (
        supabase_service_client.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("is_pinned", desc=True)
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


# ─────────────────────────────────────────────────────────────────────────────
# POST /chat/sessions — create a new chat session
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sessions", summary="Create a new chat session")
def create_chat_session(
    body: CreateSessionRequest,
    current_user: dict = Depends(require_role("investor")),
):
    user_id = current_user["id"]
    payload = {
        "user_id": user_id,
        "title": body.title or "New Chat",
    }
    if body.startup_id:
        payload["startup_id"] = body.startup_id

    resp = supabase_service_client.table("chat_sessions").insert(payload).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create session")
    return resp.data[0]


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /chat/sessions/{session_id} — update title or pin status
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/sessions/{session_id}", summary="Update a chat session (pin/rename)")
def update_chat_session(
    session_id: str,
    body: UpdateSessionRequest,
    current_user: dict = Depends(require_role("investor")),
):
    user_id = current_user["id"]
    update_data = {}
    if body.is_pinned is not None:
        update_data["is_pinned"] = body.is_pinned
    if body.title is not None:
        update_data["title"] = body.title

    if not update_data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    resp = (
        supabase_service_client.table("chat_sessions")
        .update(update_data)
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return resp.data[0]


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /chat/sessions/{session_id} — delete a session and all its messages
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/sessions/{session_id}", summary="Delete a chat session")
def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(require_role("investor")),
):
    user_id = current_user["id"]
    resp = (
        supabase_service_client.table("chat_sessions")
        .delete()
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# GET /chat/sessions/{session_id}/messages — get all messages for a session
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages", summary="Get messages for a session")
def get_session_messages(
    session_id: str,
    current_user: dict = Depends(require_role("investor")),
):
    user_id = current_user["id"]

    # Verify ownership
    session_resp = (
        supabase_service_client.table("chat_sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="Session not found")

    msgs_resp = (
        supabase_service_client.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return msgs_resp.data or []


# ─────────────────────────────────────────────────────────────────────────────
# POST /startups/{startup_id}/chat — main AI chat endpoint (saves to DB)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/startups/{startup_id}/chat",
    response_model=ChatResponse,
    summary="Ask an AI question about a specific startup",
)
def startup_ai_chat(
    startup_id: str,
    request: ChatRequest,
    current_user: dict = Depends(require_role("investor")),
):
    user_id = current_user["id"]

    try:
        # ── 1. Resolve or create session ──────────────────────────────────────
        session_id = request.session_id

        if not session_id:
            # Auto-generate title from the first few words of the question
            words = request.question.strip().split()
            title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")

            sess_resp = supabase_service_client.table("chat_sessions").insert({
                "user_id": user_id,
                "startup_id": startup_id,
                "title": title,
            }).execute()

            if not sess_resp.data:
                raise HTTPException(status_code=500, detail="Failed to create chat session")
            session_id = sess_resp.data[0]["id"]
        else:
            # Update session timestamp & attach startup_id if missing
            supabase_service_client.table("chat_sessions").update({
                "startup_id": startup_id,
                "updated_at": "now()",
            }).eq("id", session_id).eq("user_id", user_id).execute()

        # ── 2. Save user message ─────────────────────────────────────────────
        supabase_service_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "user",
            "content": request.question,
        }).execute()

        # ── 3. Build AI context & call Groq ──────────────────────────────────
        context_text = _get_startup_context(startup_id)

        if not groq_client:
            raise HTTPException(status_code=500, detail="Missing GROQ_API_KEY")

        prompt = f"""You are an AI assistant helping a Venture Capital investor evaluate a startup.
Answer their question concisely based on this startup context:
{context_text}

Investor Question: {request.question}"""

        chat_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )

        answer = chat_res.choices[0].message.content or "I'm sorry, I couldn't generate an answer."

        # ── 4. Save AI message ───────────────────────────────────────────────
        supabase_service_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "ai",
            "content": answer,
        }).execute()

        return {"answer": answer, "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in AI chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
