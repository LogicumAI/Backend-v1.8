import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Chat, Project, ProjectChatLink
from app.core.deps import get_current_user_id

router = APIRouter(prefix="/projects", tags=["projects"])

class ProjectCreate(BaseModel):
    name: str
    icon: str = "📁"

class ChatIdsList(BaseModel):
    chat_ids: List[int]

@router.get("/", response_model=List[Project])
async def list_projects(
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all projects for the current user."""
    projects = session.exec(select(Project).where(Project.user_id == user_id)).all()
    return projects

@router.post("/", response_model=Project)
async def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Create a new project associated with the current user."""
    project = Project(name=payload.name, icon=payload.icon, user_id=user_id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project

@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: int,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    session.delete(project)
    session.commit()
    return {"ok": True}

@router.get("/{project_id}/chats", response_model=List[Chat])
async def list_project_chats(
    project_id: int,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.chats

@router.post("/{project_id}/chats")
async def add_chats_to_project(
    project_id: int,
    payload: ChatIdsList,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    
    for chat_id in payload.chat_ids:
        chat = session.get(Chat, chat_id)
        # Ensure chat also belongs to user
        if chat and chat.user_id == user_id and chat not in project.chats:
            project.chats.append(chat)
    
    session.add(project)
    session.commit()
    return {"ok": True}

@router.delete("/{project_id}/chats/{chat_id}")
async def remove_chat_from_project(
    project_id: int,
    chat_id: int,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Verify project ownership
    project = session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the link entry
    statement = select(ProjectChatLink).where(
        ProjectChatLink.project_id == project_id,
        ProjectChatLink.chat_id == chat_id
    )
    link = session.exec(statement).first()
    if link:
        session.delete(link)
        session.commit()
    return {"ok": True}
