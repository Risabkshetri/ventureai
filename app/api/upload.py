import logging
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from pydantic import BaseModel

from app.core.config import settings
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

class UploadResponse(BaseModel):
    url: str

@router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload an image to Cloudinary and return the secure URL.
    Only authenticated users can upload images.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image."
        )

    try:
        # Upload file bytes to Cloudinary
        file_bytes = await file.read()
        
        # We can specify folder if needed
        result = cloudinary.uploader.upload(
            file_bytes,
            resource_type="image",
            folder="ventureai_images"
        )
        
        secure_url = result.get("secure_url")
        if not secure_url:
            raise Exception("No secure_url returned from Cloudinary.")
            
        logger.info(f"User {current_user.get('id')} uploaded image: {secure_url}")
        return UploadResponse(url=secure_url)

    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image."
        )
