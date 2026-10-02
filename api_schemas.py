"""
api_schemas.py
Pydantic-Modelle für alle HTTP-Endpunkte der Retourensupport-API.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: Optional[str] = None


class ResetRequest(BaseModel):
    session_id: Optional[str] = None


class TestConnectionRequest(BaseModel):
    api_key: str
    api_url: Optional[str] = None
    model: Optional[str] = None


class AuthLoginRequest(BaseModel):
    session_id: str
    login: str
    password: str


class AccountUpdateRequest(BaseModel):
    session_id: str
    updates: Dict[str, Any]


class CancelAuthRequest(BaseModel):
    session_id: str


class ReturnConfirmRequest(BaseModel):
    session_id: str
    order_id: str
    selected_items: List[str] = Field(default_factory=list)


class CancelReturnRequest(BaseModel):
    session_id: str
