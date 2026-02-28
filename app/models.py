import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class User(SQLModel, table=True):
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    email: str = Field(index=True, unique=True)
    name: Optional[str] = None
    preferred_name: Optional[str] = None
    hashed_password: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    projects: List["Project"] = Relationship(back_populates="user")
    chats: List["Chat"] = Relationship(back_populates="user")


class RefreshToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectChatLink(SQLModel, table=True):
    project_id: Optional[int] = Field(default=None, foreign_key="project.id", primary_key=True)
    chat_id: Optional[int] = Field(default=None, foreign_key="chat.id", primary_key=True)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    name: str
    icon: str = "📁"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: Optional[User] = Relationship(back_populates="projects")
    chats: List["Chat"] = Relationship(back_populates="projects", link_model=ProjectChatLink)


class Chat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: Optional[User] = Relationship(back_populates="chats")
    messages: List["Message"] = Relationship(back_populates="chat")
    turn_summaries: List["TurnSummary"] = Relationship(back_populates="chat")
    projects: List["Project"] = Relationship(back_populates="chats", link_model=ProjectChatLink)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id")
    role: str  # "user" or "assistant"
    content: str
    model_used: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chat: Optional[Chat] = Relationship(back_populates="messages")


class TurnSummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(foreign_key="chat.id")
    turn_index: int
    summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chat: Optional[Chat] = Relationship(back_populates="turn_summaries")


class OCRDocumentV3(SQLModel, table=True):
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    filename: str
    s3_key: str
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chunks: List["OCRChunkV3"] = Relationship(back_populates="document")


class OCRChunkV3(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="ocrdocumentv3.id", index=True)
    content: str
    chunk_type: str  # text, diagram, table, illustration
    origin_position: Optional[str] = None
    embedding: Optional[str] = None  # JSON string of vector
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    document: Optional[OCRDocumentV3] = Relationship(back_populates="chunks")


class Document(SQLModel, table=True):
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    filename: str
    s3_key: str
    file_type: str
    status: str = "pending"  # pending, processing, completed, failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chunks: List["Chunk"] = Relationship(back_populates="document")


class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="document.id", index=True)
    content: str
    page_number: Optional[int] = None
    embedding: Optional[str] = None  # JSON string representation of vector
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    document: Optional[Document] = Relationship(back_populates="chunks")
