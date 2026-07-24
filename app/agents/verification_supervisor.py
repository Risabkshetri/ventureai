from langgraph.graph import StateGraph, START, END

from app.agents.verification_state import VerificationState
from app.agents.claim_verification_agent import run_claim_verification
from app.agents.founder_research_agent import run_founder_research
from app.agents.manipulation_detection_agent import run_manipulation_detection


def node_claim_verification(state: VerificationState):
    """Executes the Claim Verification Agent."""
    try:
        result = run_claim_verification(state["structured_analysis"])
        return {"claim_verification_result": result}
    except Exception as e:
        return {"claim_verification_result": {"status": "error", "message": str(e)}, "errors": [f"Claim Agent Error: {e}"]}


def node_founder_research(state: VerificationState):
    """Executes the Founder Research Agent."""
    try:
        result = run_founder_research(state["structured_analysis"])
        return {"founder_research_result": result}
    except Exception as e:
        return {"founder_research_result": {"status": "error", "message": str(e)}, "errors": [f"Founder Agent Error: {e}"]}


def node_manipulation_detection(state: VerificationState):
    """Executes the Manipulation Detection Agent."""
    try:
        result = run_manipulation_detection(state["structured_analysis"])
        return {"manipulation_detection_result": result}
    except Exception as e:
        return {"manipulation_detection_result": {"status": "error", "message": str(e)}, "errors": [f"Manipulation Agent Error: {e}"]}


def create_verification_graph():
    """
    Builds the LangGraph orchestrator for verification.
    The graph executes three agents in parallel.
    """
    builder = StateGraph(VerificationState)  # type: ignore

    # Add Nodes
    builder.add_node("claim_verification", node_claim_verification)
    builder.add_node("founder_research", node_founder_research)
    builder.add_node("manipulation_detection", node_manipulation_detection)

    # Add Edges from START (these will run in parallel)
    builder.add_edge(START, "claim_verification")
    builder.add_edge(START, "founder_research")
    builder.add_edge(START, "manipulation_detection")

    # Add Edges to END
    builder.add_edge("claim_verification", END)
    builder.add_edge("founder_research", END)
    builder.add_edge("manipulation_detection", END)

    return builder.compile()

# Instantiate the compiled graph so it can be imported and invoked directly
verification_supervisor = create_verification_graph()

