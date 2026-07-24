import json
from typing import Any

from groq import Groq
from tavily import TavilyClient

from app.core.config import settings

def run_founder_research(structured_analysis: dict[str, Any]) -> dict[str, Any]:
    """
    1. Extracts founder name and startup name from structured analysis
    2. Searches Tavily for founder background
    3. Analyzes background using Groq to return a profile
    """
    if not settings.GROQ_API_KEY or not settings.TAVILY_API_KEY:
        return {"status": "error", "message": "Missing API keys for verification"}

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    
    # 1. Extract Founder Info
    # This assumes structured_analysis has basic info or we can extract it quickly
    # For a real implementation, you might pass founder_name and startup_name explicitly.
    extract_prompt = f"""
    Extract the main founder name and the startup name from the following analysis.
    Return a JSON object with 'founder_name' and 'startup_name'. If multiple founders, pick the CEO/Main one.
    
    Analysis:
    {json.dumps(structured_analysis)[:3000]}
    """
    
    try:
        extract_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": extract_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        parsed = json.loads(extract_res.choices[0].message.content or "{}")
        founder_name = parsed.get("founder_name")
        startup_name = parsed.get("startup_name")
    except Exception as e:
        return {"status": "error", "message": f"Founder extraction failed: {e!s}"}

    if not founder_name or founder_name.lower() in ("unknown", "n/a", ""):
        return {"founder_profile": {"error": "Founder name not found in analysis"}}
        
    query = f"{founder_name} founder {startup_name} linkedin experience education"
    
    try:
        search_res = tavily_client.search(query=query, search_depth="basic", max_results=5)
        evidence_text = "\n".join([r.get("content", "") for r in search_res.get("results", [])])
        
        analyze_prompt = f"""
        Analyze the following web evidence to create a professional profile for {founder_name}, founder of {startup_name}.
        Return ONLY a JSON object with:
        - experience (string: e.g. 'Ex Google, 10 years in SaaS')
        - education (string: e.g. 'IIT Delhi, Stanford MBA')
        - previous_company (string: e.g. 'Google, Microsoft')
        - confidence (float: 0.0 to 1.0)
        
        Evidence:
        {evidence_text}
        """
        
        analyze_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": analyze_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        
        profile = json.loads(analyze_res.choices[0].message.content or "{}")
        return {"founder_profile": profile}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
