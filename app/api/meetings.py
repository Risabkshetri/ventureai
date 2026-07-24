import logging
from typing import Any
from uuid import UUID

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import require_role
from app.core.supabase_client import supabase_client, supabase_service_client
from app.schemas.meeting import MeetingRequestCreate, MeetingResponseUpdate
from app.services.zoom_service import create_zoom_meeting

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED)
def request_meeting(
    meeting_in: MeetingRequestCreate,
    current_user: dict = Depends(require_role("investor")),
):
    try:
        # First, find the founder of this startup
        startup_resp = supabase_client.table("startups").select("founder_id").eq("id", str(meeting_in.startup_id)).execute()
        startup_data: Any = startup_resp.data
        if not startup_data:
            raise HTTPException(status_code=404, detail="Startup not found")
        
        founder_id = startup_data[0]["founder_id"]

        # Check if request already exists
        existing_resp = supabase_client.table("meeting_requests").select("*").eq("investor_id", str(current_user["id"])).eq("startup_id", str(meeting_in.startup_id)).execute()
        
        if existing_resp.data:
            existing_req: Any = existing_resp.data[0]
            if existing_req["status"] in ["pending", "accepted"]:
                return existing_req
            elif existing_req["status"] == "declined":
                # Check cooldown
                declined_time_str = existing_req.get("declined_at") or existing_req.get("updated_at")
                if declined_time_str:
                    # Supabase returns ISO format strings like "2023-01-01T12:00:00+00:00"
                    declined_time = datetime.fromisoformat(declined_time_str)
                    now_time = datetime.now(timezone.utc)
                    days_passed = (now_time - declined_time).total_seconds() / 86400.0
                    
                    if days_passed < 7:
                        remaining_days = math.ceil(7 - days_passed)
                        raise HTTPException(status_code=400, detail=f"Meeting request was declined. You can re-request after {remaining_days} days.")
                
                # Update existing request back to pending
                update_data = {
                    "status": "pending",
                    "scheduled_at": meeting_in.scheduled_at.isoformat(),
                    "agenda": meeting_in.agenda,
                    "updated_at": "now()",
                    "declined_at": None
                }
                update_resp = supabase_service_client.table("meeting_requests").update(update_data).eq("id", existing_req["id"]).execute()
                if getattr(update_resp, 'data', None):
                    return update_resp.data[0]
                else:
                    raise HTTPException(status_code=500, detail="Failed to re-request meeting.")

        data = {
            "investor_id": str(current_user["id"]),
            "startup_id": str(meeting_in.startup_id),
            "founder_id": founder_id,
            "status": "pending",
            "scheduled_at": meeting_in.scheduled_at.isoformat(),
            "agenda": meeting_in.agenda,
        }

        response = supabase_service_client.table("meeting_requests").insert(data).execute()

        resp_data: Any = getattr(response, 'data', None)
        if not resp_data:
            raise HTTPException(status_code=500, detail="Failed to create meeting request. Please add 'agenda' column to meeting_requests table in Supabase.")
        return resp_data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating meeting request: {e}")
        raise HTTPException(status_code=500, detail="Failed to create meeting request") from e


# get meetings of investor
@router.get("/investor")
def list_investor_meetings(current_user: dict = Depends(require_role("investor"))):
    try:
        response = supabase_client.table("meeting_requests").select("*, startups(*)").eq("investor_id", str(current_user["id"])).execute()
        return response.data
    except Exception as e:
        logger.error(f"Error listing investor meetings: {e}")
        raise HTTPException(status_code=500, detail="Failed to list meetings") from e


@router.get("/founder")
def list_founder_meetings(current_user: dict = Depends(require_role("founder"))):
    try:
        # We also want to return investor details (name) and startup details
        response = supabase_client.table("meeting_requests").select("*, startups(startup_name), users!meeting_requests_investor_id_fkey(name, profile_photo_url)").eq("founder_id", str(current_user["id"])).execute()
        return response.data
    except Exception as e:
        logger.error(f"Error listing founder meetings: {e}")
        raise HTTPException(status_code=500, detail="Failed to list meetings") from e


@router.put("/{meeting_id}/respond")
async def respond_to_meeting(
    meeting_id: UUID,
    update_in: MeetingResponseUpdate,
    current_user: dict = Depends(require_role("founder")),
):
    try:
        if update_in.status not in ["accepted", "declined"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        # Verify ownership
        meeting_resp = supabase_service_client.table("meeting_requests").select("*").eq("id", str(meeting_id)).execute()
        meeting_data: Any = meeting_resp.data
        if not meeting_data:
            raise HTTPException(status_code=404, detail="Meeting request not found")
        
        if meeting_data[0]["founder_id"] != str(current_user["id"]):
            raise HTTPException(status_code=403, detail="Not authorized")

        update_data = {
            "status": update_in.status,
            "updated_at": "now()"
        }
        
        if update_in.status == "declined":
            update_data["declined_at"] = datetime.now(timezone.utc).isoformat()

        if update_in.status == "accepted":
            # Call Zoom API to generate meeting
            try:
                # Parse the ISO format string to a datetime object
                scheduled_time = datetime.fromisoformat(meeting_data[0]["scheduled_at"])
                topic = f"Investor Meeting: {meeting_data[0].get('startup_id', 'Startup')}"
                agenda = meeting_data[0].get("agenda", "")
                
                zoom_details = await create_zoom_meeting(
                    topic=topic,
                    start_time=scheduled_time,
                    agenda=agenda
                )
                
                update_data["meeting_link"] = zoom_details["join_url"]
            except Exception as e:
                logger.error(f"Failed to generate Zoom link: {e}")
                # We fail the request so the founder can try again
                raise HTTPException(status_code=500, detail="Accepted, but failed to generate Zoom link. Check Zoom credentials.")

        response = supabase_service_client.table("meeting_requests").update(update_data).eq("id", str(meeting_id)).execute()
        
        if not getattr(response, 'data', None):
            raise HTTPException(status_code=500, detail="Failed to update meeting")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to meeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to respond to meeting") from e
