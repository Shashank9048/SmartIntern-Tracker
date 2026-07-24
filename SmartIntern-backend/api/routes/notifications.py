from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging
from beanie import PydanticObjectId

from ..models import Notification
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

class NotificationResponse(BaseModel):
    id: str
    type: str
    payload: dict
    read_bool: bool
    created_at: datetime

@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all notifications for the current user, sorted by most recent first.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    docs = await Notification.find(Notification.user_id == user_email).sort("-created_at").limit(50).to_list()
    
    return [
        NotificationResponse(
            id=str(doc.id),
            type=doc.type,
            payload=doc.payload,
            read_bool=doc.read_bool,
            created_at=doc.created_at
        )
        for doc in docs
    ]

@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    """
    user_email = current_user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        doc_id = PydanticObjectId(notification_id)
        notification = await Notification.get(doc_id)
        if not notification or notification.user_id != user_email:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        notification.read_bool = True
        await notification.save()
        return {"message": "Marked as read"}
    except Exception as e:
        logger.error(f"Error marking notification read: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
