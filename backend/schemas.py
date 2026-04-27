from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional, List
from backend.models import UserRole, PregnancyStatus, ChatType

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.PATIENT

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    class Config:
        from_attributes = True

class PregnancyCreate(BaseModel):
    last_menstruation_date: date

class PregnancyResponse(BaseModel):
    id: int
    patient_id: int
    last_menstruation_date: date
    due_date: Optional[date]
    status: PregnancyStatus
    notes: Optional[str]
    class Config:
        from_attributes = True

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_date: date
    week_of_pregnancy: int

class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    event_date: date
    week_of_pregnancy: int
    status: str
    class Config:
        from_attributes = True

class SymptomCreate(BaseModel):
    symptom_text: str

class SymptomResponse(BaseModel):
    id: int
    symptom_text: str
    classification: str
    created_at: datetime
    class Config:
        from_attributes = True

class InviteCreate(BaseModel):
    email: EmailStr
    role: UserRole
    pregnancy_id: int

class InviteResponse(BaseModel):  # нужен для ответа на создание приглашения
    invite_link: str
    expires_at: datetime

class AcceptInviteRequest(BaseModel):
    token: str
    password: Optional[str] = None
    full_name: Optional[str] = None

class ChatMessageCreate(BaseModel):
    message: str

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    message: str
    is_read: bool
    created_at: datetime
    triggered_critical: bool = False
    class Config:
        from_attributes = True

class ChatRoomResponse(BaseModel):
    id: int
    chat_type: str
    participant_name: str
    participant_id: int
    last_message: Optional[str]
    last_message_time: Optional[datetime]
    unread_count: int

class AIChatRequest(BaseModel):
    message: str
    pregnancy_id: Optional[int] = None

class AIChatResponse(BaseModel):
    reply: str
    triggered_critical: bool = False
    emergency_actions: Optional[str] = None