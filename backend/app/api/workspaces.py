from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.db import get_db
from app.models.models import User, Workspace
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/", response_model=WorkspaceResponse)
def create_workspace(
    data: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new team workspace."""
    if current_user.subscription_tier == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You need a Pro or Enterprise plan to create team workspaces."
        )
        
    workspace = Workspace(name=data.name, owner_id=current_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    # Auto-assign the creator
    current_user.workspace_id = workspace.id
    db.commit()
    
    return workspace

@router.get("/", response_model=List[WorkspaceResponse])
def get_my_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get workspaces owned by or joined by the user."""
    # Simplified: return the one they are in
    if not current_user.workspace_id:
        return []
    workspace = db.query(Workspace).filter(Workspace.id == current_user.workspace_id).first()
    return [workspace] if workspace else []
