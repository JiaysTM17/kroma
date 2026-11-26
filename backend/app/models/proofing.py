from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProofingFeedbackItem(BaseModel):
    id: str
    author: str
    action: str # approve, request_change, comment
    comment: str
    pin_x: Optional[float] = None
    pin_y: Optional[float] = None
    created_at: str

class ProofingSessionCreate(BaseModel):
    project_id: str
    title: str
    client_name: Optional[str] = "Client"
    allow_comments: bool = True

class ProofingFeedbackSubmit(BaseModel):
    author: str = Field(..., min_length=1)
    action: str = Field(..., pattern="^(approve|request_change|comment)$")
    comment: str
    pin_x: Optional[float] = None
    pin_y: Optional[float] = None

class ProofingSessionResponse(BaseModel):
    id: str
    project_id: str
    title: str
    client_name: Optional[str]
    status: str
    created_at: str
    allow_comments: bool
    feedback: List[Dict[str, Any]]
