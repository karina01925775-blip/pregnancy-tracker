from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

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
    phone = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.PATIENT)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pregnancies = relationship("Pregnancy", back_populates="patient")
    doctor_relationships = relationship("DoctorPatient", back_populates="doctor")
    partner_access = relationship("PartnerAccess", back_populates="partner")
    sent_invites = relationship("Invite", foreign_keys="Invite.inviter_id")

    #Чаты
    ai_chat_rooms = relationship("ChatRoom", foreign_keys="ChatRoom.user_id")
    sent_messages = relationship("ChatMessage", foreign_keys="ChatMessage.sender_id")

# ================ Беременности ==================
class Pregnancy(Base):
    __tablename__ = "pregnancies"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_menstruation_date = Column(Date, nullable=False)  # дата последней менструации
    due_date = Column(Date, nullable=True)
    status = Column(Enum(PregnancyStatus), default=PregnancyStatus.ACTIVE)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("User", back_populates="pregnancies")
    events = relationship("Event", back_populates="pregnancy")
    symptoms = relationship("Symptom", back_populates="pregnancy")
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
    classification = Column(String)   # informational, concerning, critical
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    pregnancy = relationship("pregnancy", back_populates="symptoms")

# ==================== Врачи-Пациенты ========================
class DoctorPatient(Base):
    __tablename__ = "doctor_patients"
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pregnancy_id = Column(Integer, ForeignKey("pregnancies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("User", foreign_keys=[doctor_id], back_populates="doctor_relationships")
    patient = relationship("User", foreign_keys=[patient_id])
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

    inviter = relationship("User", foreign_keys=[inviter_id])
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
    sender = relationship("User", foreign_keys=[sender_id])

# ================== База знаний =============
class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)  # питание, активность, обследования
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(String, nullable=True)        # ключевые слова через запятую для поиска ИИ-ассистентом
