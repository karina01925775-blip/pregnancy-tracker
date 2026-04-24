from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Boolean
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    last_menstruation_date = Column(Date, nullable=False)   # дата последней менструации
    age = Column(Integer, nullable=True)
    disclaimer_accepted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)        # например "Визит к врачу", "УЗИ"
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)     # дата события
    week_of_pregnancy = Column(Integer, nullable=False)  # срок беременности на момент события
    status = Column(String, default="pending")    # pending, completed, overdue
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SymptomEntry(Base):
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    symptom_text = Column(String, nullable=False)
    classification = Column(String)   # informational, concerning, critical
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)  # питание, активность, обследования
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    keywords = Column(String)        # ключевые слова через запятую для поиска ИИ-ассистентом

# Предзаполнение базы знаний (см. ниже)