import os
import httpx
from datetime import datetime
import base64
from app.core.config import settings

async def get_zoom_access_token() -> str:
    account_id = settings.ZOOM_ACCOUNT_ID
    client_id = settings.ZOOM_CLIENT_ID
    client_secret = settings.ZOOM_CLIENT_SECRET
    
    if not account_id or not client_id or not client_secret:
        raise ValueError("Zoom API credentials are not set in the environment variables.")
        
    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={account_id}"
    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["access_token"]

async def create_zoom_meeting(topic: str, start_time: datetime, agenda: str = "") -> dict:
    access_token = await get_zoom_access_token()
    
    url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "topic": topic,
        "type": 2, # Scheduled meeting
        "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": "UTC",
        "agenda": agenda,
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True,
            "jbh_time": 5,
            "mute_upon_entry": False,
            "waiting_room": False
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
