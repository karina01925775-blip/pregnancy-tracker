import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
import secrets
import hashlib

# Импорты из бэкенда
from database import get_db, engine
import models
from auth import router as auth_router
from auth import get_current_active_user, get_password_hash
from ai_assistant import classify_user_message, search_knowledge_base, get_emergency_actions
from pregnancy_utils import calculate_week_and_due_date

# Создаём таблицы
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Мама рядом API", version="1.0.0")

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статику
static_path = Path(__file__).parent / "static"
if not static_path.exists():
    static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Подключаем шаблоны
templates = Jinja2Templates(directory="app/templates")

# Подключаем роутер аутентификации
app.include_router(auth_router)


# ========== Вспомогательные функции ==========
def generate_invite_token(email: str, role: str, pregnancy_id: int) -> str:
    random_part = secrets.token_urlsafe(32)
    data = f"{email}:{role}:{pregnancy_id}:{random_part}"
    return hashlib.sha256(data.encode()).hexdigest()


def create_invite_link(token: str) -> str:
    return f"https://mama-ryadom.ru/register/invite?token={token}"


# ========== HTML СТРАНИЦЫ ==========
context = {"name": "Диана", "range_start": "2026-04-05", "range_end": "2026-04-15"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "name": context["name"],
            "range_start": context["range_start"],
            "range_end": context["range_end"],
            "current_date": date.today().strftime("%d.%m.%Y")
        }
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")


# ========== API ЭНДПОИНТЫ ==========

# ---------- Приглашения ----------
@app.post("/api/invite")
def create_invite(
        invite_data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут приглашать")

    pregnancy = db.query(models.Pregnancy).filter(
        models.Pregnancy.id == invite_data.get("pregnancy_id"),
        models.Pregnancy.patient_id == current_user.id
    ).first()
    if not pregnancy:
        raise HTTPException(status_code=404, detail="Беременность не найдена")

    token = generate_invite_token(
        invite_data["email"],
        invite_data["role"],
        invite_data["pregnancy_id"]
    )
    expires_at = datetime.utcnow() + timedelta(days=7)

    invite = models.Invite(
        token=token,
        inviter_id=current_user.id,
        invited_email=invite_data["email"],
        role=invite_data["role"],
        pregnancy_id=invite_data["pregnancy_id"],
        expires_at=expires_at
    )
    db.add(invite)
    db.commit()

    return {"invite_link": create_invite_link(token), "expires_at": expires_at}


@app.post("/api/invite/accept")
def accept_invite(
        data: dict,
        db: Session = Depends(get_db)
):
    invite = db.query(models.Invite).filter(
        models.Invite.token == data["token"],
        models.Invite.status == models.InviteStatus.PENDING
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    if invite.expires_at < datetime.utcnow():
        invite.status = models.InviteStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="Срок приглашения истёк")

    existing_user = db.query(models.User).filter(models.User.email == invite.invited_email).first()

    if invite.role == models.UserRole.DOCTOR:
        if not existing_user:
            raise HTTPException(status_code=400, detail=f"Врач с почтой {invite.invited_email} не зарегистрирован")

        doctor_link = models.DoctorPatient(
            doctor_id=existing_user.id,
            patient_id=invite.inviter_id,
            pregnancy_id=invite.pregnancy_id
        )
        db.add(doctor_link)
        invite.status = models.InviteStatus.ACCEPTED
        db.commit()
        return {"message": "Врач добавлен к беременности"}

    elif invite.role == models.UserRole.PARTNER:
        if existing_user:
            access = models.PartnerAccess(
                partner_id=existing_user.id,
                pregnancy_id=invite.pregnancy_id,
                can_view=True
            )
            db.add(access)
        else:
            if not data.get("password") or not data.get("full_name"):
                raise HTTPException(status_code=400, detail="Укажите password и full_name")

            hashed = get_password_hash(data["password"])
            new_partner = models.User(
                email=invite.invited_email,
                hashed_password=hashed,
                full_name=data["full_name"],
                role=models.UserRole.PARTNER,
                phone=""
            )
            db.add(new_partner)
            db.flush()

            access = models.PartnerAccess(
                partner_id=new_partner.id,
                pregnancy_id=invite.pregnancy_id,
                can_view=True
            )
            db.add(access)

        invite.status = models.InviteStatus.ACCEPTED
        db.commit()
        return {"message": "Доступ для партнёра добавлен"}

    raise HTTPException(status_code=400, detail="Неверный тип приглашения")


# ---------- Беременности ----------
@app.post("/api/pregnancies")
def create_pregnancy(
        data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут создавать беременности")

    due_date = datetime.strptime(data["last_menstruation_date"], "%Y-%m-%d").date() + timedelta(days=280)
    pregnancy = models.Pregnancy(
        patient_id=current_user.id,
        last_menstruation_date=data["last_menstruation_date"],
        due_date=due_date
    )
    db.add(pregnancy)
    db.commit()
    db.refresh(pregnancy)
    return {"id": pregnancy.id, "due_date": pregnancy.due_date, "status": pregnancy.status}


@app.get("/api/pregnancies")
def get_pregnancies(
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if current_user.role == models.UserRole.PATIENT:
        pregnancies = db.query(models.Pregnancy).filter(models.Pregnancy.patient_id == current_user.id).all()
    elif current_user.role == models.UserRole.PARTNER:
        pregnancies = db.query(models.Pregnancy).join(models.PartnerAccess).filter(
            models.PartnerAccess.partner_id == current_user.id
        ).all()
    elif current_user.role == models.UserRole.DOCTOR:
        pregnancies = db.query(models.Pregnancy).join(models.DoctorPatient).filter(
            models.DoctorPatient.doctor_id == current_user.id
        ).all()
    else:
        pregnancies = []

    return [{"id": p.id, "due_date": p.due_date, "status": p.status} for p in pregnancies]


# ---------- События ----------
@app.post("/api/pregnancies/{pregnancy_id}/events")
def create_event(
        pregnancy_id: int,
        data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    pregnancy = db.query(models.Pregnancy).filter(models.Pregnancy.id == pregnancy_id).first()
    if not pregnancy:
        raise HTTPException(status_code=404, detail="Беременность не найдена")

    if current_user.role == models.UserRole.PATIENT and pregnancy.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    event = models.Event(
        pregnancy_id=pregnancy_id,
        title=data["title"],
        description=data.get("description"),
        event_date=data["event_date"],
        week_of_pregnancy=data["week_of_pregnancy"]
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"id": event.id, "title": event.title, "event_date": event.event_date}


@app.get("/api/pregnancies/{pregnancy_id}/events")
def get_events(
        pregnancy_id: int,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    events = db.query(models.Event).filter(models.Event.pregnancy_id == pregnancy_id).all()
    return [
        {"id": e.id, "title": e.title, "description": e.description,
         "event_date": e.event_date, "week_of_pregnancy": e.week_of_pregnancy}
        for e in events
    ]


# ---------- Симптомы ----------
@app.post("/api/pregnancies/{pregnancy_id}/symptoms")
def create_symptom(
        pregnancy_id: int,
        data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Только пациентки могут добавлять симптомы")

    text_lower = data["symptom_text"].lower()
    critical = ["кровотечение", "кровь", "сильная боль", "обморок", "температура 39"]
    concerning = ["головная боль", "отеки", "выделения", "тошнота", "давление"]

    if any(kw in text_lower for kw in critical):
        classification = "critical"
    elif any(kw in text_lower for kw in concerning):
        classification = "concerning"
    else:
        classification = "informational"

    symptom = models.SymptomEntry(
        pregnancy_id=pregnancy_id,
        symptom_text=data["symptom_text"],
        classification=classification
    )
    db.add(symptom)
    db.commit()
    return {"id": symptom.id, "classification": classification}


# ---------- Чат с врачом ----------
@app.post("/api/chat/doctor/create/{pregnancy_id}")
def create_doctor_chat(
        pregnancy_id: int,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    pregnancy = db.query(models.Pregnancy).filter(models.Pregnancy.id == pregnancy_id).first()
    if not pregnancy:
        raise HTTPException(status_code=404, detail="Беременность не найдена")

    if current_user.role == models.UserRole.PATIENT:
        patient_id = current_user.id
        doctor_link = db.query(models.DoctorPatient).filter(
            models.DoctorPatient.pregnancy_id == pregnancy_id
        ).first()
        if not doctor_link:
            raise HTTPException(status_code=404, detail="Врач не привязан")
        doctor_id = doctor_link.doctor_id
    elif current_user.role == models.UserRole.DOCTOR:
        doctor_id = current_user.id
        doctor_link = db.query(models.DoctorPatient).filter(
            models.DoctorPatient.doctor_id == doctor_id,
            models.DoctorPatient.pregnancy_id == pregnancy_id
        ).first()
        if not doctor_link:
            raise HTTPException(status_code=403, detail="Вы не привязаны")
        patient_id = doctor_link.patient_id
    else:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    existing_room = db.query(models.ChatRoom).filter(
        models.ChatRoom.chat_type == models.ChatType.DOCTOR_PATIENT,
        models.ChatRoom.doctor_id == doctor_id,
        models.ChatRoom.patient_id == patient_id,
        models.ChatRoom.pregnancy_id == pregnancy_id
    ).first()

    if existing_room:
        return {"room_id": existing_room.id}

    room = models.ChatRoom(
        chat_type=models.ChatType.DOCTOR_PATIENT,
        doctor_id=doctor_id,
        patient_id=patient_id,
        pregnancy_id=pregnancy_id
    )
    db.add(room)
    db.commit()
    return {"room_id": room.id}


@app.post("/api/chat/room/{room_id}/send")
def send_message(
        room_id: int,
        data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    room = db.query(models.ChatRoom).filter(models.ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Чат не найден")

    message = models.ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        message=data["message"]
    )
    db.add(message)
    db.commit()
    return {"message_id": message.id, "created_at": message.created_at}


@app.get("/api/chat/room/{room_id}/messages")
def get_messages(
        room_id: int,
        limit: int = 50,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.room_id == room_id
    ).order_by(models.ChatMessage.created_at).limit(limit).all()

    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "message": m.message,
            "created_at": m.created_at
        } for m in messages
    ]


# ---------- ИИ-ассистент ----------
@app.post("/api/chat/ai/create")
def create_ai_chat(
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    existing_room = db.query(models.ChatRoom).filter(
        models.ChatRoom.chat_type == models.ChatType.AI_ASSISTANT,
        models.ChatRoom.user_id == current_user.id,
        models.ChatRoom.is_active == True
    ).first()

    if existing_room:
        return {"room_id": existing_room.id}

    room = models.ChatRoom(
        chat_type=models.ChatType.AI_ASSISTANT,
        user_id=current_user.id
    )
    db.add(room)
    db.commit()
    return {"room_id": room.id}


@app.post("/api/chat/ai/{room_id}/ask")
def ask_ai(
        room_id: int,
        data: dict,
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    room = db.query(models.ChatRoom).filter(
        models.ChatRoom.id == room_id,
        models.ChatRoom.user_id == current_user.id
    ).first()

    if not room:
        raise HTTPException(status_code=404, detail="ИИ-чат не найден")

    # Сохраняем сообщение пользователя
    user_message = models.ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        message=data["message"]
    )
    db.add(user_message)
    db.commit()

    # Классифицируем и ищем ответ
    classification, recommendation = classify_user_message(data["message"])

    if classification == "critical":
        answer = f"🚨 {recommendation}\n\n{get_emergency_actions()}"
        triggered_critical = True
    elif classification == "concerning":
        answer = f"⚠️ {recommendation}\n\nРекомендуем обратиться к врачу."
        triggered_critical = False
    else:
        # Ищем в базе знаний
        pregnancy_id = data.get("pregnancy_id")
        if not pregnancy_id:
            active_pregnancy = db.query(models.Pregnancy).filter(
                models.Pregnancy.patient_id == current_user.id,
                models.Pregnancy.status == models.PregnancyStatus.ACTIVE
            ).first()
            if active_pregnancy:
                pregnancy_id = active_pregnancy.id
        answer = search_knowledge_base(db, data["message"], pregnancy_id)
        triggered_critical = False

    ai_message = models.ChatMessage(
        room_id=room_id,
        sender_id=current_user.id,
        message=answer,
        triggered_critical=triggered_critical
    )
    db.add(ai_message)
    db.commit()

    return {"reply": answer, "triggered_critical": triggered_critical}


# ---------- Дашборд ----------
@app.get("/api/dashboard")
def dashboard(
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    active_pregnancy = None
    if current_user.role == models.UserRole.PATIENT:
        active_pregnancy = db.query(models.Pregnancy).filter(
            models.Pregnancy.patient_id == current_user.id,
            models.Pregnancy.status == models.PregnancyStatus.ACTIVE
        ).first()

    current_week = None
    if active_pregnancy:
        days_since_lmp = (date.today() - active_pregnancy.last_menstruation_date).days
        current_week = max(1, (days_since_lmp // 7) + 1)

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": current_user.role.value
        },
        "active_pregnancy": {
            "id": active_pregnancy.id,
            "current_week": current_week,
            "due_date": active_pregnancy.due_date
        } if active_pregnancy else None
    }


# ---------- Врач: мои пациентки ----------
@app.get("/api/my-patients")
def get_my_patients(
        current_user: models.User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if current_user.role != models.UserRole.DOCTOR:
        raise HTTPException(status_code=403, detail="Доступно только врачам")

    patients = db.query(models.User).join(models.DoctorPatient).filter(
        models.DoctorPatient.doctor_id == current_user.id
    ).distinct().all()

    return [
        {
            "id": p.id,
            "full_name": p.full_name,
            "email": p.email,
            "phone": p.phone
        } for p in patients
    ]


# ---------- Health check ----------
@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)