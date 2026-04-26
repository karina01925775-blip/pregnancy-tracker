import re
from sqlalchemy.orm import Session
from datetime import date
from services.pregnancy_utils import calculate_week_and_due_date
from models import Pregnancy, KnowledgeBase

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

def classify_user_message(message:str):
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

def search_knowledge_base(db: Session, query: pregnancy_id: int = None) -> str:
    query_lower = query.lower()

    articles = db.query(KnowledgeBase).all()
    best_match = None
    best_score = 0

    for article in articles:
        score = 0
        if articles.title and query_lower in article.title.lower:
            score += 5
        if article.keywords:
            keywords = [kw.strip().lower() for kw in article.keywords.split(',')]
            for kw in leywords:
                if kw in query_lower:
                    score += 2
        if article.content and query_lower in article.content.lower():
            score += 1
        if score > best_score:
            best_score = score
            best_match = article

    context = ""

    if pregnancy_id:
        pregnancy_ = db.query(Pregnancy).filter(Pregnancy.id == pregnancy_id).first()
        if pregnancy and pregnancy.last_menstruation_date:
            current_week, _ = calculate_week_and_due_date(pregnancy.last_menstruation_date)
            context = f"\n\n[Контекст: Ваш срок беременности - {current_week} неделя.]"

    if best_match and best_score > 0:
        return best_match.content + context
    return f"Спасибо за ваш вопрос. Для точного ответа рекомендую проконсультироваться с вашим лечащим врачом.{context}"

def get_emergency_actions() -> str:
    return "/n".join([
        "🚨 НЕМЕДЛЕННО вызовите скорую помощь: 103 или 112",
        "📍 Сообщите диспетчеру: ваш срок беременности, что случилось, адрес",
        "🛌 Лягте на левый бок, не паникуйте, дышите ровно",
        "💊 Не принимайте никаких лекарств без указания врача",
        "📋 Соберите документы: паспорт, полис, обменную карту"
    ])