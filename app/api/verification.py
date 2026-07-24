from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, require_role
from app.core.supabase_client import supabase_service_client
from app.agents.verification_state import VerificationState
from app.agents.verification_supervisor import verification_supervisor

router = APIRouter()


class VerifyRequest(BaseModel):
    evaluation_id: str


@router.post(
    "/{evaluation_id}/verify",
    status_code=status.HTTP_200_OK,
    summary="Run multi-agent due diligence verification",
)
async def verify_evaluation(
    evaluation_id: str,
    current_user: dict = Depends(require_role("investor")),
):
    """
    Triggers the LangGraph verification layer for a specific evaluation.
    1. Loads existing structured analysis from the database
    2. Runs the verification supervisor (which runs 3 agents in parallel)
    3. Stores the results in `verification_reports`
    """
    
    # 1. Fetch structured analysis (from various tables linked to evaluation_id)
    try:
        # Fetch startup info to get the founder name and startup name
        eval_res = supabase_service_client.table("evaluations").select(
            "id, startups(name, users(name))"
        ).eq("id", evaluation_id).single().execute()
        
        if not eval_res.data:
            raise HTTPException(status_code=404, detail="Evaluation not found")
            
        startup_name = eval_res.data.get("startups", {}).get("name", "Unknown Startup")
        founder_name = eval_res.data.get("startups", {}).get("users", {}).get("name", "Unknown Founder")
        
        # Fetch summaries, risks, etc.
        exec_res = supabase_service_client.table("executive_summaries").select("*").eq("evaluation_id", evaluation_id).execute()
        risks_res = supabase_service_client.table("identified_risks").select("*").eq("evaluation_id", evaluation_id).execute()
        
        structured_analysis = {
            "startup_name": startup_name,
            "founder_name": founder_name,
            "executive_summary": exec_res.data[0] if exec_res.data else {},
            "identified_risks": risks_res.data if risks_res.data else []
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load structured analysis: {e!s}"
        ) from e

    # 2. Run Verification Supervisor
    try:
        initial_state: VerificationState = {
            "structured_analysis": structured_analysis,
            "claim_verification_result": None,
            "founder_research_result": None,
            "manipulation_detection_result": None,
            "errors": []
        }
        
        # LangGraph invoke
        final_state = verification_supervisor.invoke(initial_state)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification agents failed: {e!s}"
        ) from e
        
    # 3. Store Results in database
    try:
        # We use upsert in case they click it again
        supabase_service_client.table("verification_reports").upsert({
            "evaluation_id": evaluation_id,
            "claim_verification": final_state.get("claim_verification_result", {}),
            "founder_research": final_state.get("founder_research_result", {}),
            "manipulation_detection": final_state.get("manipulation_detection_result", {})
        }, on_conflict="evaluation_id").execute()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save verification report: {e!s}"
        ) from e
        
    return {
        "status": "success",
        "message": "Due diligence verification completed successfully",
        "report": {
            "claim_verification": final_state.get("claim_verification_result"),
            "founder_research": final_state.get("founder_research_result"),
            "manipulation_detection": final_state.get("manipulation_detection_result"),
            "errors": final_state.get("errors", [])
        }
    }


class VerifyClaimRequest(BaseModel):
    claim: str
    category: str = "General"


class VerifyClaimResponse(BaseModel):
    status: str
    confidence: float
    evidence: list[str]
    reason: str


@router.post(
    "/startups/{startup_id}/verify-claim",
    response_model=VerifyClaimResponse,
    summary="Verify a specific claim on demand"
)
def verify_single_claim(
    startup_id: str,
    request: VerifyClaimRequest,
    current_user: dict = Depends(require_role("investor"))
):
    import logging
    logger = logging.getLogger(__name__)
    
    # 1. Check cache
    try:
        cache_resp = supabase_service_client.table("claim_verifications").select("*").eq("startup_id", startup_id).eq("claim_text", request.claim).execute()
        if cache_resp.data:
            cached = cache_resp.data[0]
            return {
                "status": cached["status"],
                "confidence": float(cached["confidence"] or 0.0),
                "evidence": cached["evidence_data"] or [],
                "reason": "Retrieved from cache."
            }
    except Exception as e:
        logger.warning(f"Cache check failed: {e}")

    # 2. Verify with Tavily & Groq
    from tavily import TavilyClient
    from groq import Groq
    import json
    from app.core.config import settings

    if not settings.GROQ_API_KEY or not settings.TAVILY_API_KEY:
        raise HTTPException(status_code=500, detail="Missing API keys for verification")
        
    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    try:
        search_res = tavily_client.search(query=request.claim, search_depth="basic", max_results=3)
        evidence_text = "\n".join([r.get("content", "") for r in search_res.get("results", [])])
        evidence_urls = [r.get("url", "") for r in search_res.get("results", [])]
        
        verify_prompt = f"""
        Analyze the following startup claim against the provided web evidence.
        Determine if the claim is Verified, Unverified, or Contradicted.
        Return a JSON object with:
        - status (string: "Verified", "Unverified", "Contradicted")
        - confidence (float: 0.0 to 1.0)
        - reason (string: brief explanation)
        
        Claim: {request.claim}
        Evidence: {evidence_text}
        """
        
        verify_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": verify_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        
        v_content = verify_res.choices[0].message.content or "{}"
        v_parsed = json.loads(v_content)
        
        status_val = v_parsed.get("status", "Unverified")
        confidence_val = float(v_parsed.get("confidence", 0.0))
        reason_val = v_parsed.get("reason", "")
        
        # 3. Save to cache
        try:
            supabase_service_client.table("claim_verifications").insert({
                "startup_id": startup_id,
                "claim_text": request.claim,
                "category": request.category,
                "status": status_val,
                "confidence": confidence_val,
                "evidence_data": evidence_urls
            }).execute()
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

        return {
            "status": status_val,
            "confidence": confidence_val,
            "evidence": evidence_urls,
            "reason": reason_val
        }

    except Exception as e:
        logger.error(f"Error verifying claim: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


