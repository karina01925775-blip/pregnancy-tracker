from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
import enum, datetime

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    PARTNER = "partner"
    DOCTOR = "doctor"

class PregnancyStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    MISCARRIAGE = "miscarriage"
    BIRTH = "birth"

class InviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"

class ChatType(str, enum.Enum):
    DOCTOR_PATIENT = "doctor_patient"
    AI_ASSISTANT = "ai_assistant"

# ============== Пользлватели =============
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    phone = Column(String, nullable=False, default="")
    age = Column(Integer, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.PATIENT)
    is_active = Column(Boolean, default=True)
    disclaimer_accepted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    pregnancies = relationship("Pregnancy", back_populates="patient")


    doctor_relationships = relationship("DoctorPatient", foreign_keys="DoctorPatient.doctor_id", back_populates="doctor")
    patient_relationships = relationship("DoctorPatient", foreign_keys="DoctorPatient.patient_id", back_populates="patient")
    partner_access = relationship("PartnerAccess", back_populates="partner")
    sent_invites = relationship("Invite", foreign_keys="Invite.inviter_id", back_populates="inviter")

    # Чаты
    ai_chat_rooms = relationship("ChatRoom", foreign_keys="ChatRoom.user_id", back_populates="user")
    sent_messages = relationship("ChatMessage", foreign_keys="ChatMessage.sender_id", back_populates="sender")
# ================ Беременности ==================
class Pregnancy(Base):
    __tablename__ = "pregnancies"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_menstruation_date = Column(Date, nullable=False) # дата менструации
    second_trimester_date = Column(Date, nullable=False) # дата начала второго триместра
    third_trimester_date = Column(Date, nullable=False) # дата начала третьего триместра
    due_date = Column(Date, nullable=True) # предполагаемая дата родов
    status = Column(Enum(PregnancyStatus), default=PregnancyStatus.ACTIVE)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("User", back_populates="pregnancies")
    events = relationship("Event", back_populates="pregnancy")
    # ИСПРАВЛЕНО: было "Symptom", а нужно "SymptomEntry"
    symptoms = relationship("SymptomEntry", back_populates="pregnancy")
    doctors = relationship("DoctorPatient", back_populates="pregnancy")
    partners = relationship("PartnerAccess", back_populates="pregnancy")
# ================ События =======================
class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    title = Column(String, nullable=False)        # например "Визит к врачу", "УЗИ"
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)     # дата события
    time = Column(String, nullable=True)
    event_type = Column(String, default="other")
    week_of_pregnancy = Column(Integer, nullable=False)  # срок беременности на момент события
    status = Column(String, default="pending")    # pending, completed, overdue
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    pregnancy = relationship("Pregnancy", back_populates="events")

#======================= Симптомы =======================
class SymptomEntry(Base):
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, index=True)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    symptom_text = Column(String, nullable=False)
    classification = Column(String)  # informational, concerning, critical
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pregnancy = relationship("Pregnancy", back_populates="symptoms")
# ==================== Врачи-Пациенты ========================
class DoctorPatient(Base):
    __tablename__ = "doctor_patients"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_relationships")
    patient = relationship("User", foreign_keys=[patient_id], back_populates="patient_relationships")
    pregnancy = relationship("Pregnancy", back_populates="doctors")

    __table_args__ = (UniqueConstraint('doctor_id', 'patient_id', 'pregnancy_id', name='_doctor_patient_pregnancy_uc'),)

class PartnerAccess(Base):
    __tablename__ = "partner_access"
    id = Column(Integer, primary_key=True)
    partner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    can_view = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    partner = relationship("User", back_populates="partner_access")
    pregnancy = relationship("Pregnancy", back_populates="partners")

    __table_args__ = (UniqueConstraint('partner_id', 'pregnancy_id', name='_partner_pregnancy_uc'),)

#========================== Приглашения =================
class Invite(Base):
    __tablename__ = "invites"
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True, nullable=False)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invited_email = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    status = Column(Enum(InviteStatus), default=InviteStatus.PENDING)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="sent_invites")
    pregnancy = relationship("Pregnancy")

#==================== Чаты ==========================
class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    id = Column(Integer, primary_key=True, index=True)
    chat_type = Column(Enum(ChatType), nullable=False)

    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    doctor = relationship("User", foreign_keys=[doctor_id])
    patient = relationship("User", foreign_keys=[patient_id])
    pregnancy = relationship("Pregnancy")
    user = relationship("User", foreign_keys=[user_id], back_populates="ai_chat_rooms")
    messages = relationship("ChatMessage", back_populates="room")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    triggered_critical = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")

# ================== База знаний =============
class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)  # питание, активность, обследования
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(String, nullable=True)        # ключевые слова через запятую для поиска ИИ-ассистентом


# ===== ТАБЛИЦА ВОПРОСОВ ДЛЯ ТЕСТА =====
class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(String, nullable=False)  # Текст вопроса
    question_type = Column(String, default="multiple_choice")  # "multiple_choice" или "text"
    options = Column(String)  # Варианты ответов через | для multiple_choice
    order_index = Column(Integer, default=0)  # Порядок отображения
    is_required = Column(Boolean, default=True)
    category = Column(String, default="general")  # Категория: "mood", "symptoms", etc.

    created_at = Column(DateTime, default=func.now())


# ===== ТАБЛИЦА ОТВЕТОВ ПОЛЬЗОВАТЕЛЯ =====
class TestAnswer(Base):
    __tablename__ = "test_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("test_questions.id"), nullable=False)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=True)

    answer_text = Column(Text)  # Для открытых вопросов
    selected_option = Column(String)  # Для вопросов с выбором
    score = Column(Integer, default=0)  # Балл за ответ (для аналитики)

    created_at = Column(DateTime, default=func.now())

    # Связи
    # user = relationship("User", back_populates="test_answers")
    question = relationship("TestQuestion")
    pregnancy = relationship("Pregnancy")
