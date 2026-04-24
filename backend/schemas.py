from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List

# ---------------- Онбординг ----------------
class OnboardingRequest(BaseModel):
    last_menstruation_date: date
    age: Optional[int] = None
    disclaimer_accepted: bool = True

class OnboardingResponse(BaseModel):
    user_id: int
    current_week: int
    due_date: date   # предполагаемая дата родов (40 недель от LMP)

# ---------------- Дашборд ----------------
class DashboardResponse(BaseModel):
    user_id: int
    current_week: int
    summary: str                     # краткая сводка из базы знаний
    upcoming_events: List[dict]      # ближайшие события
    quick_actions: dict

# ---------------- Календарь ----------------
class EventCreate(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None
    event_date: date
    week_of_pregnancy: int
    status: str = "pending"

class EventUpdate(BaseModel):
    status: str   # completed

class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    event_date: date
    week_of_pregnancy: int
    status: str

# ---------------- Симптомы ----------------
class SymptomRequest(BaseModel):
    user_id: int
    symptom_text: str

class SymptomResponse(BaseModel):
    classification: str  # informational, concerning, critical
    message: str
    emergency_actions: Optional[str] = None  # для critical

# ---------------- Тревожный режим ----------------
class CriticalActionsResponse(BaseModel):
    actions: List[str]

# ---------------- База знаний ----------------
class KnowledgeResponse(BaseModel):
    category: str
    title: str
    content: str

# ---------------- ИИ-ассистент ----------------
class ChatRequest(BaseModel):
    user_id: int
    question: str

class ChatResponse(BaseModel):
    answer: str
    critical_triggered: bool = False
    emergency_actions: Optional[str] = None