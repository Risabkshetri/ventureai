import asyncio
import anyio
import logging
from uuid import UUID

from app.core.supabase_client import supabase_service_client
from app.core.config import settings
from app.agents import (
    run_summary_agent,
    run_risk_agent,
    run_question_agent,
    run_scoring_agent,
)
from app.services.pdf_processing import chunk_text, extract_text

logger = logging.getLogger(__name__)


async def run_evaluation_pipeline(
    evaluation_id: UUID,
    startup_id: UUID,
    file_bytes: bytes,
    file_name: str,
    storage_path: str = "",
) -> None:
    """Orchestrates the background PDF extraction, chunking, parallel AI evaluations,

    and saving results into the PostgreSQL database.
    """
    logger.info(f"Starting evaluation pipeline for evaluation_id={evaluation_id}, startup_id={startup_id}")

    db = supabase_service_client

    try:
        # 1. Update status to 'processing' and metadata status to 'extracting'
        db.table("evaluations").update(
            {"status": "processing"}
        ).eq("id", str(evaluation_id)).execute()

        db.table("pdf_metadata").update(
            {"extraction_status": "extracting"}
        ).eq("evaluation_id", str(evaluation_id)).execute()

        # 1.5 Upload to Supabase Storage in the background
        # We use anyio.to_thread.run_sync to avoid blocking the event loop
        if storage_path:
            def upload_to_supabase():
                db.storage.from_("pitch-decks").upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": "application/pdf"}
                )
            await anyio.to_thread.run_sync(upload_to_supabase)

        # 2. Extract Text from PDF/PPT bytes
        # (LlamaParse is primary; falls back to PyMuPDF/OCR)
        result = await extract_text(file_bytes, file_name)

        if not result.success:
            logger.error(f"Text extraction failed for evaluation_id={evaluation_id}: {result.error}")
            error_status = result.error or "extraction_failed"

            db.table("evaluations").update(
                {"status": "failed"}
            ).eq("id", str(evaluation_id)).execute()

            db.table("pdf_metadata").update(
                {"extraction_status": error_status}
            ).eq("evaluation_id", str(evaluation_id)).execute()
            return

        # Update page count and status to processing
        db.table("pdf_metadata").update({
            "page_count": result.page_count,
            "extraction_status": "processing"
        }).eq("evaluation_id", str(evaluation_id)).execute()

        cleaned_text = result.cleaned_text or ""

        # 3. Chunk the clean text
        chunks = await anyio.to_thread.run_sync(chunk_text, cleaned_text)
        reconstructed_text = "\n\n".join(chunks)

        logger.info(f"Evaluation_id={evaluation_id}: text extracted successfully ({result.page_count} pages, {len(chunks)} chunks). Invoking agents...")

        # 4. Invoke the 4 AI Agents sequentially using thread pools
        # We run them using anyio.to_thread.run_sync to avoid blocking the event loop.
        summary_out = await anyio.to_thread.run_sync(run_summary_agent, reconstructed_text)
        risk_out = await anyio.to_thread.run_sync(run_risk_agent, reconstructed_text)
        question_out = await anyio.to_thread.run_sync(run_question_agent, reconstructed_text)
        score_out = await anyio.to_thread.run_sync(run_scoring_agent, reconstructed_text)

        logger.info(f"Evaluation_id={evaluation_id}: AI Agents completed. Storing results in database...")

        # 5. Store results in PostgreSQL database
        # Insert summary
        db.table("executive_summaries").insert({
            "evaluation_id": str(evaluation_id),
            "problem": summary_out.problem,
            "solution": summary_out.solution,
            "target_market": summary_out.target_market,
            "business_model": summary_out.business_model,
            "traction": summary_out.traction,
            "executive_summary": summary_out.executive_summary,
        }).execute()

        # Insert risks
        risk_rows = [
            {
                "evaluation_id": str(evaluation_id),
                "category": item.category,
                "risk": item.risk,
                "severity": item.severity,
            }
            for item in risk_out.risks
        ]
        if risk_rows:
            db.table("identified_risks").insert(risk_rows).execute()

        # Insert questions
        question_rows = [
            {
                "evaluation_id": str(evaluation_id),
                "category": item.category,
                "question": item.question,
            }
            for item in question_out.questions
        ]
        if question_rows:
            db.table("investor_questions").insert(question_rows).execute()

        # Insert scores
        db.table("scores").insert({
            "evaluation_id": str(evaluation_id),
            "market_opportunity": score_out.market_opportunity,
            "product_innovation": score_out.product_innovation,
            "team_strength": score_out.team_strength,
            "business_model_score": score_out.business_model_score,
            "competitive_advantage": score_out.competitive_advantage,
            "traction_score": score_out.traction_score,
            "scalability": score_out.scalability,
            "startup_score": score_out.startup_score,
            "score_reasoning": score_out.score_reasoning.model_dump(),
        }).execute()

        # 6. Mark evaluation status as 'completed' and pdf_metadata status as 'success'
        db.table("evaluations").update(
            {"status": "completed"}
        ).eq("id", str(evaluation_id)).execute()

        db.table("pdf_metadata").update(
            {"extraction_status": "success"}
        ).eq("evaluation_id", str(evaluation_id)).execute()

        logger.info(f"Evaluation pipeline completed successfully for evaluation_id={evaluation_id}")

    except Exception as e:
        logger.error(f"Error executing evaluation pipeline for evaluation_id={evaluation_id}: {e}", exc_info=True)

        # Determine a user-friendly error status based on the exception type
        error_str = str(e).lower()
        if "quota" in error_str or "resource_exhausted" in error_str or "429" in error_str:
            error_status = "api_quota_exceeded"
        elif "api_key" in error_str or "401" in error_str or "403" in error_str:
            error_status = "api_key_invalid"
        elif "agent" in error_str and "failed" in error_str:
            error_status = "ai_analysis_failed"
        else:
            error_status = "analysis_error"

        # Update statuses to failed
        try:
            db.table("evaluations").update(
                {"status": "failed"}
            ).eq("id", str(evaluation_id)).execute()

            db.table("pdf_metadata").update(
                {"extraction_status": error_status}
            ).eq("evaluation_id", str(evaluation_id)).execute()
        except Exception as update_err:
            logger.error(f"Failed to update failed status in database: {update_err}")
