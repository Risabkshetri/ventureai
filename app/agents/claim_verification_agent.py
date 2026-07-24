import json
from typing import Any

from groq import Groq
from tavily import TavilyClient

from app.core.config import settings

def run_claim_verification(structured_analysis: dict[str, Any]) -> dict[str, Any]:
    """
    1. Extracts claims from structured analysis
    2. Searches Tavily for evidence
    3. Verifies claims using Groq
    """
    if not settings.GROQ_API_KEY or not settings.TAVILY_API_KEY:
        return {"status": "error", "message": "Missing API keys for verification"}

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    
    # 1. Extract Claims
    extract_prompt = f"""
    Extract the 3 most significant factual claims (e.g. revenue, partnerships, customer count) 
    from the following startup analysis. Return ONLY a JSON array of strings.
    
    Analysis:
    {json.dumps(structured_analysis)[:3000]}
    """
    
    try:
        extract_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": extract_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        
        content = extract_res.choices[0].message.content or "{}"
        try:
            # We expect a JSON object with a 'claims' array due to standard LLM JSON behaviors
            parsed = json.loads(content)
            claims = parsed.get("claims", [])
            if not claims and isinstance(parsed, list):
                claims = parsed
        except json.JSONDecodeError:
            claims = []
            
    except Exception as e:
        return {"status": "error", "message": f"Claim extraction failed: {e!s}"}

    # If no claims found
    if not claims:
        return {"verified_claims": []}
        
    results = []
    
    # 2 & 3. Search and Verify
    for claim in claims[:3]:  # Limit to top 3 to manage time/costs
        try:
            # Search Tavily
            search_res = tavily_client.search(query=claim, search_depth="basic", max_results=3)
            evidence_text = "\n".join([r.get("content", "") for r in search_res.get("results", [])])
            evidence_urls = [r.get("url", "") for r in search_res.get("results", [])]
            
            # Verify with Groq
            verify_prompt = f"""
            Analyze the following claim against the provided web evidence.
            Determine if the claim is Verified, Unverified, or Contradicted.
            Return a JSON object with:
            - status (string: "Verified", "Unverified", "Contradicted")
            - confidence (float: 0.0 to 1.0)
            - reason (string: brief explanation)
            
            Claim: {claim}
            Evidence: {evidence_text}
            """
            
            verify_res = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": verify_prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            
            v_content = verify_res.choices[0].message.content or "{}"
            v_parsed = json.loads(v_content)
            
            results.append({
                "claim": claim,
                "status": v_parsed.get("status", "Unverified"),
                "confidence": v_parsed.get("confidence", 0.0),
                "reason": v_parsed.get("reason", ""),
                "evidence_urls": evidence_urls
            })
            
        except Exception as e:
            results.append({
                "claim": claim,
                "status": "Error",
                "reason": str(e)
            })

    return {"verified_claims": results}
