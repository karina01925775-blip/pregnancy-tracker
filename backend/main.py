from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import secrets
from pathlib import Path
import sys
from typing import Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend import models
from backend.services.pregnancy_utils import calculate_trimester_dates, calculate_week_and_due_date, get_pregnancy_period
from backend.auth import create_access_token, get_current_active_user, get_password_hash, router as auth_router
from backend.config import STATIC_DIR, TEMPLATES_DIR
from backend.database import SessionLocal, engine, get_db
from backend.schemas import (
    AIChatRequest,
    AcceptInviteRequest,
    ChatMessageCreate,
    EventCreate,
    InviteCreate,
    PartnerInviteCreate,
    PregnancyCreate,
    SymptomCreate,
    TestHistoryItem,
    TestQuestionResponse,
    TestSubmitRequest,
)
from backend.services.ai_assistant import classify_user_message, get_emergency_actions, search_knowledge_base
from backend.services.pregnancy_utils import calculate_trimester_dates, calculate_week_and_due_date
from backend.services.test_service import (
    ensure_test_questions_seeded,
    get_history_window,
    save_daily_test_answers,
    serialize_answer,
    serialize_question,
)


app = FastAPI(title="Мама рядом API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/app/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static-legacy")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.include_router(auth_router)


@app.on_event("startup")
def startup() -> None:
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_test_questions_seeded(db)
    finally:
        db.close()


def generate_invite_token(email: str, role: str, pregnancy_id: int) -> str:
    random_part = secrets.token_urlsafe(32)
    payload = f"{email}:{role}:{pregnancy_id}:{random_part}"
    return hashlib.sha256(payload.encode()).hexdigest()


def build_invite_link(request: Request, token: str) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/auth/register?token={token}"


def get_active_pregnancy_for_user(db: Session, user: models.User) -> Optional[models.Pregnancy]:
    if user.role == models.UserRole.PATIENT:
        return (
            db.query(models.Pregnancy)
            .filter(
                models.Pregnancy.patient_id == user.id,
                models.Pregnancy.status == models.PregnancyStatus.ACTIVE,
            )
            .first()
        )

    if user.role == models.UserRole.PARTNER:
        access = (
            db.query(models.PartnerAccess)
            .filter(models.PartnerAccess.partner_id == user.id, models.PartnerAccess.can_view.is_(True))
            .first()
        )
        if not access:
            return None
        return db.query(models.Pregnancy).filter(models.Pregnancy.id == access.pregnancy_id).first()

    if user.role == models.UserRole.DOCTOR:
        relation = db.query(models.DoctorPatient).filter(models.DoctorPatient.doctor_id == user.id).first()
        if not relation:
            return None
        return db.query(models.Pregnancy).filter(models.Pregnancy.id == relation.pregnancy_id).first()

    return None


def ensure_pregnancy_access(
    db: Session,
    user: models.User,
    pregnancy_id: int,
    *,
    write_access: bool = False,
) -> models.Pregnancy:
    pregnancy = db.query(models.Pregnancy).filter(models.Pregnancy.id == pregnancy_id).first()
    if pregnancy is None:
        raise HTTPException(status_code=404, detail="Беременность не найдена")

    if user.role == models.UserRole.PATIENT:
        if pregnancy.patient_id != user.id:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        return pregnancy

    if user.role == models.UserRole.PARTNER:
        access = (
            db.query(models.PartnerAccess)
            .filter(
                models.PartnerAccess.partner_id == user.id,
                models.PartnerAccess.pregnancy_id == pregnancy_id,
                models.PartnerAccess.can_view.is_(True),
            )
            .first()
        )
        if access is None:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        if write_access:
            raise HTTPException(status_code=403, detail="Партнёр может только просматривать данные")
        return pregnancy

    if user.role == models.UserRole.DOCTOR:
        relation = (
            db.query(models.DoctorPatient)
            .filter(
                models.DoctorPatient.doctor_id == user.id,
                models.DoctorPatient.pregnancy_id == pregnancy_id,
            )
            .first()
        )
        if relation is None:
            raise HTTPException(status_code=403, detail="Доступ запрещён")
        return pregnancy

    raise HTTPException(status_code=403, detail="Доступ запрещён")


def serialize_pregnancy(pregnancy: models.Pregnancy) -> dict:
    return {
        "id": pregnancy.id,
        "due_date": pregnancy.due_date.isoformat() if pregnancy.due_date else None,
        "status": pregnancy.status.value,
        "last_menstruation_date": pregnancy.last_menstruation_date.isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "name": "Гость",
            "email": "",
            "range_start": "",
            "range_end": "",
            "current_date": date.today().strftime("%d.%m.%Y"),
        },
    )


@app.get("/login")
async def login_redirect():
    return RedirectResponse(url="/auth/login", status_code=307)


@app.get("/register")
async def register_redirect():
    return RedirectResponse(url="/auth/register", status_code=307)


@app.get("/auth/login", response_class=HTMLResponse, name="login_page")
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/auth/register", response_class=HTMLResponse, name="register_page")
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/profile")
async def profile_redirect():
    return RedirectResponse(url="/", status_code=307)

@app.get("/disclaimer")
async def disclaimer_page():
    return RedirectResponse(url="disclaimer.html", status_code=307)

@app.post("/api/invite")
def create_invite(
    invite_data: InviteCreate,
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут приглашать")

    pregnancy = ensure_pregnancy_access(db, current_user, invite_data.pregnancy_id, write_access=True)

    token = generate_invite_token(invite_data.email, invite_data.role.value, pregnancy.id)
    expires_at = datetime.utcnow() + timedelta(days=7)

    invite = models.Invite(
        token=token,
        inviter_id=current_user.id,
        invited_email=invite_data.email,
        role=invite_data.role,
        pregnancy_id=invite_data.pregnancy_id,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {"invite_link": build_invite_link(request, token), "expires_at": expires_at.isoformat()}


@app.get("/api/partner-invites")
def get_partner_invites(
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Доступ только для пациенток")

    pregnancy = get_active_pregnancy_for_user(db, current_user)
    if pregnancy is None:
        raise HTTPException(status_code=400, detail="Активная беременность не найдена")

    invites = (
        db.query(models.Invite)
        .filter(
            models.Invite.inviter_id == current_user.id,
            models.Invite.pregnancy_id == pregnancy.id,
            models.Invite.role == models.UserRole.PARTNER,
            models.Invite.status == models.InviteStatus.PENDING,
        )
        .order_by(models.Invite.created_at.desc())
        .all()
    )

    return [
        {
            "id": invite.id,
            "token": invite.token,
            "status": invite.status.value,
            "expires_at": invite.expires_at.isoformat(),
            "link": build_invite_link(request, invite.token),
        }
        for invite in invites
    ]


@app.post("/api/partner-invites")
def create_partner_invite(
    request: Request,
    data: Optional[PartnerInviteCreate] = None,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Доступ только для пациенток")

    pregnancy = get_active_pregnancy_for_user(db, current_user)
    if pregnancy is None:
        raise HTTPException(status_code=400, detail="Активная беременность не найдена")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    invited_email = data.email if data and data.email else f"partner_{token[:8]}@invite.mama-ryadom.ru"

    invite = models.Invite(
        token=token,
        inviter_id=current_user.id,
        invited_email=invited_email,
        role=models.UserRole.PARTNER,
        pregnancy_id=pregnancy.id,
        status=models.InviteStatus.PENDING,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "token": invite.token,
        "status": invite.status.value,
        "link": build_invite_link(request, invite.token),
        "expires_at": invite.expires_at.isoformat(),
    }


@app.delete("/api/partner-invites/{invite_id}")
def revoke_partner_invite(
    invite_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    invite = (
        db.query(models.Invite)
        .filter(models.Invite.id == invite_id, models.Invite.inviter_id == current_user.id)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    if invite.status == models.InviteStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="Нельзя отозвать уже принятое приглашение")

    invite.status = models.InviteStatus.EXPIRED
    db.commit()
    return {"message": "Приглашение успешно отозвано"}


@app.post("/api/invite/accept")
def accept_invite(data: AcceptInviteRequest, db: Session = Depends(get_db)):
    invite = (
        db.query(models.Invite)
        .filter(models.Invite.token == data.token, models.Invite.status == models.InviteStatus.PENDING)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Приглашение не найдено или уже использовано")
    if invite.expires_at < datetime.utcnow():
        invite.status = models.InviteStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="Срок приглашения истёк")

    if invite.role != models.UserRole.PARTNER:
        raise HTTPException(status_code=400, detail="Этот тип приглашения обрабатывается иначе")

    full_name = (data.full_name or "Партнёр").strip()
    technical_email = f"partner_{invite.token[:8]}_{invite.id}@invite.mama-ryadom.ru"
    technical_password = secrets.token_urlsafe(12) + "A1!"

    user = db.query(models.User).filter(models.User.email == technical_email).first()
    if user is None:
        user = models.User(
            email=technical_email,
            hashed_password=get_password_hash(technical_password),
            full_name=full_name,
            phone="",
            role=models.UserRole.PARTNER,
        )
        db.add(user)
        db.flush()

    existing_access = (
        db.query(models.PartnerAccess)
        .filter(
            models.PartnerAccess.partner_id == user.id,
            models.PartnerAccess.pregnancy_id == invite.pregnancy_id,
        )
        .first()
    )
    if existing_access is None:
        db.add(
            models.PartnerAccess(
                partner_id=user.id,
                pregnancy_id=invite.pregnancy_id,
                can_view=True,
            )
        )

    invite.status = models.InviteStatus.ACCEPTED
    db.commit()

    return {"access_token": create_access_token(data={"sub": str(user.id)}), "token_type": "bearer"}


@app.post("/api/pregnancies")
def create_pregnancy(
    data: PregnancyCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут создавать беременности")

    existing_active = get_active_pregnancy_for_user(db, current_user)
    if existing_active is not None:
        raise HTTPException(status_code=400, detail="У вас уже есть активная беременность")

    lmp = data.last_menstruation_date
    if lmp is None and data.gestational_week:
        lmp = date.today() - timedelta(days=data.gestational_week * 7)
    if lmp is None:
        raise HTTPException(status_code=400, detail="Укажите дату последней менструации или срок в неделях")

    _, due_date = calculate_week_and_due_date(lmp)
    second_trimester, third_trimester = calculate_trimester_dates(lmp)

    pregnancy = models.Pregnancy(
        patient_id=current_user.id,
        last_menstruation_date=lmp,
        second_trimester_date=second_trimester,
        third_trimester_date=third_trimester,
        due_date=due_date,
        status=models.PregnancyStatus.ACTIVE,
    )
    db.add(pregnancy)
    db.commit()
    db.refresh(pregnancy)

    current_week, _ = calculate_week_and_due_date(lmp)
    period = get_pregnancy_period(current_week)

    return {
        "id": pregnancy.id,
        "due_date": due_date.isoformat() if due_date else None,
        "status": pregnancy.status.value,
        "last_menstruation_date": lmp.isoformat(),
        "current_week": current_week,
        "period": period
    }


@app.get("/api/pregnancies")
def get_pregnancies(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role == models.UserRole.PATIENT:
        pregnancies = db.query(models.Pregnancy).filter(models.Pregnancy.patient_id == current_user.id).all()
    elif current_user.role == models.UserRole.PARTNER:
        pregnancies = (
            db.query(models.Pregnancy)
            .join(models.PartnerAccess, models.PartnerAccess.pregnancy_id == models.Pregnancy.id)
            .filter(models.PartnerAccess.partner_id == current_user.id)
            .all()
        )
    elif current_user.role == models.UserRole.DOCTOR:
        pregnancies = (
            db.query(models.Pregnancy)
            .join(models.DoctorPatient, models.DoctorPatient.pregnancy_id == models.Pregnancy.id)
            .filter(models.DoctorPatient.doctor_id == current_user.id)
            .all()
        )
    else:
        pregnancies = []

    return [serialize_pregnancy(pregnancy) for pregnancy in pregnancies]


@app.post("/api/pregnancies/{pregnancy_id}/events")
def create_event(
    pregnancy_id: int,
    data: EventCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ensure_pregnancy_access(db, current_user, pregnancy_id, write_access=True)

    event = models.Event(
        pregnancy_id=pregnancy_id,
        title=data.title,
        description=data.description,
        event_date=data.event_date,
        week_of_pregnancy=data.week_of_pregnancy,
        time=data.time,
        event_type=data.event_type,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "event_date": event.event_date.isoformat(),
        "week_of_pregnancy": event.week_of_pregnancy,
        "time": event.time,
        "event_type": event.event_type,
        "status": event.status
    }


@app.get("/api/pregnancies/{pregnancy_id}/events")
def get_events(
    pregnancy_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ensure_pregnancy_access(db, current_user, pregnancy_id)
    events = (
        db.query(models.Event)
        .filter(models.Event.pregnancy_id == pregnancy_id)
        .order_by(models.Event.event_date.asc())
        .all()
    )

    return [
        {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "event_date": event.event_date.isoformat(),
            "week_of_pregnancy": event.week_of_pregnancy,
            "status": event.status,
        }
        for event in events
    ]


@app.post("/api/pregnancies/{pregnancy_id}/symptoms")
def create_symptom(
    pregnancy_id: int,
    data: SymptomCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут добавлять симптомы")

    ensure_pregnancy_access(db, current_user, pregnancy_id, write_access=True)

    classification, recommendation = classify_user_message(data.symptom_text)

    symptom = models.SymptomEntry(
        pregnancy_id=pregnancy_id,
        symptom_text=data.symptom_text,
        classification=classification,
    )
    db.add(symptom)
    db.commit()
    db.refresh(symptom)

    return {
        "id": symptom.id,
        "classification": classification,
        "recommendation": recommendation,
    }


@app.post("/api/chat/doctor/create/{pregnancy_id}")
def create_doctor_chat(
    pregnancy_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    pregnancy = ensure_pregnancy_access(db, current_user, pregnancy_id)

    if current_user.role == models.UserRole.PATIENT:
        patient_id = current_user.id
        relation = (
            db.query(models.DoctorPatient)
            .filter(models.DoctorPatient.pregnancy_id == pregnancy_id)
            .first()
        )
        if relation is None:
            raise HTTPException(status_code=404, detail="Врач не привязан")
        doctor_id = relation.doctor_id
    elif current_user.role == models.UserRole.DOCTOR:
        doctor_id = current_user.id
        relation = (
            db.query(models.DoctorPatient)
            .filter(
                models.DoctorPatient.doctor_id == doctor_id,
                models.DoctorPatient.pregnancy_id == pregnancy_id,
            )
            .first()
        )
        if relation is None:
            raise HTTPException(status_code=403, detail="Вы не привязаны к этой беременности")
        patient_id = relation.patient_id
    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    existing_room = (
        db.query(models.ChatRoom)
        .filter(
            models.ChatRoom.chat_type == models.ChatType.DOCTOR_PATIENT,
            models.ChatRoom.doctor_id == doctor_id,
            models.ChatRoom.patient_id == patient_id,
            models.ChatRoom.pregnancy_id == pregnancy.id,
        )
        .first()
    )
    if existing_room:
        return {"room_id": existing_room.id}

    room = models.ChatRoom(
        chat_type=models.ChatType.DOCTOR_PATIENT,
        doctor_id=doctor_id,
        patient_id=patient_id,
        pregnancy_id=pregnancy.id,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"room_id": room.id}


def ensure_room_access(db: Session, room_id: int, current_user: models.User) -> models.ChatRoom:
    room = db.query(models.ChatRoom).filter(models.ChatRoom.id == room_id).first()
    if room is None:
        raise HTTPException(status_code=404, detail="Чат не найден")

    if room.chat_type == models.ChatType.AI_ASSISTANT and room.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if room.chat_type == models.ChatType.DOCTOR_PATIENT and current_user.id not in {room.patient_id, room.doctor_id}:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return room


@app.post("/api/chat/room/{room_id}/send")
def send_message(
    room_id: int,
    data: ChatMessageCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ensure_room_access(db, room_id, current_user)

    message = models.ChatMessage(room_id=room_id, sender_id=current_user.id, message=data.message)
    db.add(message)
    db.commit()
    db.refresh(message)

    return {"message_id": message.id, "created_at": message.created_at.isoformat()}


@app.get("/api/chat/room/{room_id}/messages")
def get_messages(
    room_id: int,
    limit: int = 50,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ensure_room_access(db, room_id, current_user)

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.room_id == room_id)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": message.id,
            "sender_id": message.sender_id,
            "message": message.message,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }
        for message in messages
    ]


@app.post("/api/chat/ai/create")
def create_ai_chat(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    existing_room = (
        db.query(models.ChatRoom)
        .filter(
            models.ChatRoom.chat_type == models.ChatType.AI_ASSISTANT,
            models.ChatRoom.user_id == current_user.id,
            models.ChatRoom.is_active.is_(True),
        )
        .first()
    )
    if existing_room:
        return {"room_id": existing_room.id}

    room = models.ChatRoom(chat_type=models.ChatType.AI_ASSISTANT, user_id=current_user.id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return {"room_id": room.id}


@app.post("/api/chat/ai/{room_id}/ask")
def ask_ai(
    room_id: int,
    data: AIChatRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    ensure_room_access(db, room_id, current_user)

    user_message = models.ChatMessage(room_id=room_id, sender_id=current_user.id, message=data.message)
    db.add(user_message)
    db.commit()

    classification, recommendation = classify_user_message(data.message)
    if classification == "critical":
        answer = f"🚨 {recommendation}\n\n{get_emergency_actions()}"
        triggered_critical = True
    elif classification == "concerning":
        answer = f"⚠️ {recommendation}\n\nРекомендуем обратиться к врачу."
        triggered_critical = False
    else:
        pregnancy_id = data.pregnancy_id
        if pregnancy_id is None:
            active_pregnancy = get_active_pregnancy_for_user(db, current_user)
            if active_pregnancy is not None:
                pregnancy_id = active_pregnancy.id

        answer = search_knowledge_base(db, data.message, pregnancy_id)
        triggered_critical = False

    ai_message = models.ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        message=answer,
        triggered_critical=triggered_critical,
    )
    db.add(ai_message)
    db.commit()

    return {"reply": answer, "triggered_critical": triggered_critical}

@app.delete("/api/pregnancies/{pregnancy_id}/events/{event_id}")
def delete_event(
        pregnancy_id: int,
        event_id: int,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
):
    """Удаление события"""
    ensure_pregnancy_access(db, current_user, pregnancy_id, write_access=True)

    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.pregnancy_id == pregnancy_id
    ).first()

    if event is None:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    db.delete(event)
    db.commit()

    return {"message": "Событие успешно удалено"}

@app.get("/api/dashboard")
def dashboard(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    active_pregnancy = get_active_pregnancy_for_user(db, current_user)
    current_week = None
    followed_patient_name = None

    if active_pregnancy is not None:
        current_week, _ = calculate_week_and_due_date(active_pregnancy.last_menstruation_date)

    if current_user.role == models.UserRole.PARTNER and active_pregnancy is not None:
        patient = db.query(models.User).filter(models.User.id == active_pregnancy.patient_id).first()
        followed_patient_name = patient.full_name if patient else None

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": current_user.role.value,
        },
        "active_pregnancy": {
            "id": active_pregnancy.id,
            "current_week": current_week,
            "last_menstruation_date": active_pregnancy.last_menstruation_date.isoformat(),
            "due_date": active_pregnancy.due_date.isoformat() if active_pregnancy.due_date else None,
        }
        if active_pregnancy
        else None,
        "followed_patient_name": followed_patient_name,
    }


@app.get("/api/my-patients")
def get_my_patients(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Доступно только врачам")

    patients = (
        db.query(models.User)
        .join(models.DoctorPatient, models.DoctorPatient.patient_id == models.User.id)
        .filter(models.DoctorPatient.doctor_id == current_user.id)
        .distinct()
        .all()
    )

    return [
        {"id": patient.id, "full_name": patient.full_name, "email": patient.email, "phone": patient.phone}
        for patient in patients
    ]


@app.get("/api/test/questions", response_model=list[TestQuestionResponse])
def get_test_questions(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    ensure_test_questions_seeded(db)
    questions = db.query(models.TestQuestion).order_by(models.TestQuestion.order_index.asc()).all()
    return [serialize_question(question) for question in questions]


@app.post("/api/test/submit")
def submit_test_answers(
    data: TestSubmitRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Тест самочувствия доступен только пациентке")

    pregnancy_id = data.pregnancy_id
    if pregnancy_id is None:
        active_pregnancy = get_active_pregnancy_for_user(db, current_user)
        if active_pregnancy is None:
            raise HTTPException(status_code=400, detail="Сначала укажите дату беременности")
        pregnancy_id = active_pregnancy.id
    else:
        ensure_pregnancy_access(db, current_user, pregnancy_id, write_access=True)

    saved_count = save_daily_test_answers(
        db,
        user_id=current_user.id,
        pregnancy_id=pregnancy_id,
        answers=[answer.dict() for answer in data.answers],
    )
    if saved_count == 0:
        raise HTTPException(status_code=400, detail="Не удалось сохранить ответы")

    return {"message": "Ответы успешно сохранены", "saved_count": saved_count}


@app.get("/api/test/history", response_model=list[TestHistoryItem])
def get_test_history(
    target_date: Optional[date] = Query(default=None, alias="date"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.TestAnswer)
        .join(models.TestQuestion, models.TestQuestion.id == models.TestAnswer.question_id)
        .filter(models.TestAnswer.user_id == current_user.id)
    )

    if target_date is not None:
        start, end = get_history_window(target_date)
        query = query.filter(models.TestAnswer.created_at >= start, models.TestAnswer.created_at < end)

    answers = query.order_by(models.TestAnswer.created_at.desc()).limit(limit).all()
    return [serialize_answer(answer) for answer in answers]


@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/symptom/analyze")
def analyze_symptom(
        data: SymptomCreate,
        current_user: models.User = Depends(get_current_active_user)
):
    classification, recommendation = classify_user_message(data.symptom_text)

    result = {
        "classification": classification,
        "recommendation": recommendation or "Симптом не требует срочного вмешательства. При усилении обратитесь к врачу."
    }

    if classification == "critical":
        result["actions"] = get_emergency_actions()

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
