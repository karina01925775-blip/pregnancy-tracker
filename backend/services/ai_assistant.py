import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import re
import ollama  # <-- Добавляем импорт для работы с LLM
from sqlalchemy.orm import Session
from datetime import date
# from backend.services.pregnancy_utils import calculate_week_and_due_date
from backend.models import Pregnancy, KnowledgeBase
from backend.database import Base

CRITICAL_KEYWORDS = [
    "кровотечение", "кровь", "сильная боль", "невыносимая боль",
    "обморок", "потеря сознания", "температура 39", "высокая температура",
    "отходят воды", "подтекание вод", "схватки", "давление 140",
    "не чувствую шевелений", "нет шевелений", "преждевременные роды"
]

CONCERNING_KEYWORDS = [
    "головная боль", "отеки", "выделения", "тянет низ живота",
    "тошнота сильная", "рвота", "головокружение", "давление скачет"
]


def classify_user_message(message: str):
    message_lower = message.lower()
    for keyword in CRITICAL_KEYWORDS:
        if keyword in message_lower:
            return ("critical",
                    "КРИТИЧЕСКИЙ СИМПТОМ! Немедленно вызовите скорую помощь (103) или обратитесь в стационар.")
    for keyword in CONCERNING_KEYWORDS:
        if keyword in message_lower:
            return ("concerning",
                    "Это настораживающий симптом. Рекомендуем связаться с вашим лечащим врачом в ближайшее время.")
    return ("normal", None)

def search_knowledge_base(db: Session, query: str, pregnancy_id: int = None) -> str:
    """
    Ищет ответ в БД. Если не находит, спрашивает у Llama 3 с предупреждением.
    """
    # 🔹 Отладка: покажем, что видит SQLAlchemy
    print(f"🔍 Запрос к таблице: {KnowledgeBase.__tablename__}")
    print(f"🔍 Метаданные таблиц: {list(Base.metadata.tables.keys())}")

    query_lower = query.lower()
    articles = db.query(KnowledgeBase).all()

    print(f"🔍 Найдено статей: {len(articles)}")  # <-- Должно быть > 0
    query_lower = query.lower()
    articles = db.query(KnowledgeBase).all()
    best_match = None
    best_score = 0
    print("======== Получили сообщение ==========", len(articles))
    # 1. Поиск по базе знаний
    for article in articles:
        score = 0
        print(f"============= {article} ===========")
        if article.title and query_lower in article.title.lower():
            score += 5
        if article.keywords:
            keywords = [kw.strip().lower() for kw in article.keywords.split(', ')]
            for kw in keywords:
                if kw in query_lower:
                    score += 2
        if article.content and query_lower in article.content.lower():
            score += 1
        if score > best_score:
            best_score = score
            best_match = article

    # Получаем контекст беременности
    context_info = ""
    if pregnancy_id:
        pregnancy = db.query(Pregnancy).filter(Pregnancy.id == pregnancy_id).first()
        if pregnancy and pregnancy.last_menstruation_date:
            days = (date.today() - pregnancy.last_menstruation_date).days
            week = days // 7
            context_info = f"\n[Информация о пациенте: Срок беременности {week} недель.]"

    # 2. Если статья найдена — используем её + ИИ для формулировки
    if best_match and best_score > 0:
        system_prompt = f"""
        Ты — медицинский ассистент 'МамаРядом'. Ответь на вопрос, используя ТОЛЬКО этот текст из базы знаний.

        КОНТЕКСТ:
        {best_match.content}
        {context_info}
        """
        try:
            response = ollama.chat(model='llama3', messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': query},
            ])
            return response['message']['content']
        except Exception as e:
            print(f"Ошибка Ollama: {e}")
            return best_match.content + context_info  # Фоллбэк на сырой текст

    # 3. Если ничего не найдено — спрашиваем ИИ "от себя" с предупреждением
    else:
        system_prompt = f"""
        Ты — добрый медицинский ассистент для беременных.
        Отвечай кратко, профессионально и доброжелательно.

        ВАЖНО: В начале ответа обязательно добавь фразу: 
        "⚠️ *Этой информации нет в моей официальной базе, ответ основан на общих медицинских знаниях и может быть неточным.*"

        {context_info}
        """
        try:
            response = ollama.chat(model='llama3', messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': query},
            ])
            return response['message']['content']
        except Exception as e:
            return f"К сожалению, я не нашел информации по этому вопросу ни в базе, ни в своих знаниях. Пожалуйста, обратитесь к врачу.{context_info}"


def get_emergency_actions() -> str:
    return "\n".join([
        "🚨 НЕМЕДЛЕННО вызовите скорую помощь: 103 или 112",
        "📍 Сообщите диспетчеру: ваш срок беременности, что случилось, адрес",
        "🛌 Лягте на левый бок, не паникуйте, дышите ровно",
        "💊 Не принимайте никаких лекарств без указания врача",
        "📋 Соберите документы: паспорт, полис, обменную карту"
    ])