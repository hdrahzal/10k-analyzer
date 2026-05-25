# backend/models.py
from pydantic import BaseModel
from typing import Literal


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    total_chunks: int
    filing_type: str
    already_processed: bool


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Citation(BaseModel):
    page: int
    section: str
    anchor_text: str
    doc_id: str


class ChatRequest(BaseModel):
    doc_id: str
    messages: list[Message]


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: Literal["up", "down"]
    comment: str | None = None
