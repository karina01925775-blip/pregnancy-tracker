from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import KnowledgeBase, Pregnancy

try:
    import ollama
except ImportError:  # pragma: no cover - зависит от локальной установки
    ollama = None


CRITICAL_KEYWORDS = [
    "кровотечение",
    "кровь",
    "сильная боль",
    "невыносимая боль",
    "обморок",
    "потеря сознания",
    "температура 39",
    "высокая температура",
    "отходят воды",
    "подтекание вод",
    "схватки",
    "давление 140",
    "не чувствую шевелений",
    "нет шевелений",
    "преждевременные роды",
]

CONCERNING_KEYWORDS = [
    "головная боль",
    "отеки",
    "выделения",
    "тянет низ живота",
    "тошнота сильная",
    "рвота",
    "головокружение",
    "давление скачет",
]


def classify_user_message(message: str):
    message_lower = message.lower()
    for keyword in CRITICAL_KEYWORDS:
        if keyword in message_lower:
            return (
                "critical",
                "КРИТИЧЕСКИЙ СИМПТОМ. Немедленно вызовите скорую помощь (103) или обратитесь в стационар.",
            )
    for keyword in CONCERNING_KEYWORDS:
        if keyword in message_lower:
            return (
                "concerning",
                "Это настораживающий симптом. Рекомендуем связаться с вашим лечащим врачом в ближайшее время.",
            )
    return "normal", None


def build_pregnancy_context(db: Session, pregnancy_id: Optional[int]) -> str:
    if not pregnancy_id:
        return ""

    pregnancy = db.query(Pregnancy).filter(Pregnancy.id == pregnancy_id).first()
    if not pregnancy or not pregnancy.last_menstruation_date:
        return ""

    days = (date.today() - pregnancy.last_menstruation_date).days
    week = max(1, days // 7)
    return f"\n[Информация о пациенте: срок беременности {week} недель.]"


def find_best_article(db: Session, query: str) -> Optional[KnowledgeBase]:
    query_lower = query.lower()
    best_match = None
    best_score = 0

    for article in db.query(KnowledgeBase).all():
        score = 0

        if article.title and query_lower in article.title.lower():
            score += 5
        if article.keywords:
            keywords = [kw.strip().lower() for kw in article.keywords.split(",")]
            score += sum(2 for keyword in keywords if keyword and keyword in query_lower)
        if article.content and query_lower in article.content.lower():
            score += 1

        if score > best_score:
            best_score = score
            best_match = article

    return best_match if best_score > 0 else None


def ask_ollama(system_prompt: str, query: str) -> Optional[str]:
    if ollama is None:
        return None

    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
        )
    except Exception:
        return None

    return response.get("message", {}).get("content")


def search_knowledge_base(db: Session, query: str, pregnancy_id: int = None) -> str:
    context_info = build_pregnancy_context(db, pregnancy_id)
    best_match = find_best_article(db, query)

    if best_match:
        system_prompt = (
            "Ты медицинский ассистент проекта 'Мама Рядом'. "
            "Ответь на вопрос кратко, спокойно и используя только переданный текст базы знаний.\n\n"
            f"КОНТЕКСТ:\n{best_match.content}\n{context_info}"
        )
        llm_answer = ask_ollama(system_prompt, query)
        if llm_answer:
            return llm_answer
        return f"{best_match.content}{context_info}"

    system_prompt = (
        "Ты добрый медицинский ассистент для беременных. "
        "Отвечай кратко, профессионально и доброжелательно. "
        "Если точной информации нет, честно предупреди об этом.\n"
        f"{context_info}"
    )
    llm_answer = ask_ollama(system_prompt, query)
    if llm_answer:
        return (
            "⚠️ Этой информации нет в моей официальной базе, "
            "ответ основан на общих медицинских знаниях.\n\n"
            f"{llm_answer}"
        )

    return (
        "К сожалению, я не нашел информации по этому вопросу ни в базе, ни в локальной модели. "
        "Пожалуйста, обратитесь к врачу."
        f"{context_info}"
    )


def get_emergency_actions() -> str:
    return "\n".join(
        [
            "🚨 НЕМЕДЛЕННО вызовите скорую помощь: 103 или 112",
            "📍 Сообщите диспетчеру срок беременности, симптом и адрес",
            "🛌 Лягте на левый бок и постарайтесь сохранять спокойствие",
            "💊 Не принимайте лекарства без указания врача",
            "📋 Подготовьте паспорт, полис и обменную карту",
        ]
    )
