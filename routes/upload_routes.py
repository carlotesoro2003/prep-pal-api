from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
import time
import random
import string
from pathlib import Path
from auth import get_current_user
from models import User

router = APIRouter(prefix="/upload", tags=["upload"])

# Create uploads directory
UPLOAD_DIR = Path("uploads/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def generate_unique_filename(user_id: int, original_filename: str) -> str:
    timestamp = int(time.time())
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'jpg'
    return f"avatar_{user_id}_{timestamp}_{random_string}.{file_extension}"

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Validate file size (5MB max)
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File size must be less than 5MB")
    
    # Generate unique filename
    unique_filename = generate_unique_filename(current_user.id, file.filename)
    file_path = UPLOAD_DIR / unique_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    # Return the URL
    file_url = f"/uploads/avatars/{unique_filename}"
    
    return {
        "url": file_url,
        "filename": unique_filename,
        "message": "Avatar uploaded successfully"
    }

@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)