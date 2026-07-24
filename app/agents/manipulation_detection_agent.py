import json
from typing import Any

from groq import Groq

from app.core.config import settings

def run_manipulation_detection(structured_analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Analyzes the structured analysis for vanity metrics, contradictions, 
    unsupported claims, buzzword stuffing, etc., without doing web searches.
    """
    if not settings.GROQ_API_KEY:
        return {"status": "error", "message": "Missing Groq API key"}

    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    
    analyze_prompt = f"""
    You are an expert due diligence auditor. Analyze the following structured pitch deck analysis.
    Look closely for:
    1. Vanity Metrics (metrics that look good but lack substance)
    2. Contradictions (e.g., '500 customers' on one slide and '120 customers' on another)
    3. Unsupported TAM (Total Addressable Market that seems artificially inflated without basis)
    4. Buzzword Stuffing (excessive use of 'AI', 'Blockchain', 'Synergy' without clear application)
    5. Missing Baselines (percentages without the base numbers, e.g., 'grew by 500%')

    Return ONLY a JSON array of objects, where each object represents a detected flag.
    Each object should have:
    - category (string: e.g. "Contradiction", "Vanity Metric")
    - description (string: clear explanation of what was found)
    - severity (string: "Low", "Medium", "High")

    Analysis to audit:
    {json.dumps(structured_analysis)[:5000]}
    """
    
    try:
        analyze_res = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": analyze_prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
        )
        
        content = analyze_res.choices[0].message.content or "{}"
        try:
            parsed = json.loads(content)
            flags = parsed.get("flags", [])
            if not flags and isinstance(parsed, list):
                flags = parsed
            elif not flags and isinstance(parsed, dict) and len(parsed) > 0:
                # Some models might wrap it differently if we didn't specify 'flags' key in prompt
                # But we asked for a JSON array of objects. Let's just return what we got if it's a dict containing a list
                for k, v in parsed.items():
                    if isinstance(v, list):
                        flags = v
                        break
        except json.JSONDecodeError:
            flags = []
            
        return {"quality_flags": flags}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
