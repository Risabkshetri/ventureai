import operator
from typing import Annotated, Any

from typing_extensions import TypedDict


class VerificationState(TypedDict):
    """
    Represents the state of the verification workflow managed by LangGraph.
    
    Attributes:
        structured_analysis: The initial structured data containing claims, 
            founder info, and general deck analysis.
        claim_verification_result: Results from the Claim Verification Agent.
        founder_research_result: Results from the Founder Research Agent.
        manipulation_detection_result: Results from the Manipulation Detection Agent.
        errors: A list of any errors encountered during the parallel verification step.
    """

    structured_analysis: dict[str, Any]
    
    # We use Annotated with operator.add or similar if we wanted to merge arrays, 
    # but since these are populated by specific agents, simple assignment is fine 
    # for dicts in this parallel step, or we can just use standard TypedDict.
    # We'll use simple assignment since each agent writes to exactly one distinct key.
    claim_verification_result: dict[str, Any] | None
    founder_research_result: dict[str, Any] | None
    manipulation_detection_result: dict[str, Any] | None
    
    # Annotated list allows appending errors from any node safely in parallel
    errors: Annotated[list[str], operator.add]
