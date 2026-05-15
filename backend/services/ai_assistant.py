from __future__ import annotations

import re
from datetime import date
from typing import Optional

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from backend.models import KnowledgeBase, Pregnancy

try:
    import ollama
except ImportError:  # pragma: no cover - зависит от локальной установки
    ollama = None


STOP_WORDS = {
    "и",
    "в",
    "во",
    "на",
    "с",
    "со",
    "по",
    "о",
    "об",
    "а",
    "но",
    "ли",
    "же",
    "бы",
    "что",
    "как",
    "для",
    "при",
    "это",
    "так",
    "из",
    "к",
    "у",
    "от",
    "до",
    "без",
    "через",
    "или",
    "не",
    "ни",
    "меня",
    "мне",
    "есть",
    "очень",
    "сейчас",
    "сегодня",
}

CRITICAL_KEYWORDS = [
    "кровотечение",
    "кровь",
    "алые выделения",
    "обильные выделения",
    "сильная боль",
    "резкая боль",
    "невыносимая боль",
    "обморок",
    "потеря сознания",
    "судороги",
    "отходят воды",
    "подтекание вод",
    "схватки",
    "нет шевелений",
    "не чувствую шевелений",
    "боль в груди",
    "не хватает воздуха",
    "тяжело дышать",
]

CONCERNING_KEYWORDS = [
    "головная боль",
    "отеки",
    "отёки",
    "выделения",
    "тянет низ живота",
    "тянущая боль",
    "тошнота",
    "рвота",
    "головокружение",
    "давление",
    "жжение при мочеиспускании",
    "частое мочеиспускание",
    "температура",
    "меньше шевелений",
    "слабость",
]


def classify_user_message(message: str) -> tuple[str, Optional[str]]:
    normalized = normalize_text(message)

    if is_critical_symptom(normalized):
        return (
            "critical",
            "Критический симптом. Немедленно вызовите скорую помощь (103/112) или обратитесь в стационар.",
        )

    if is_concerning_symptom(normalized):
        return (
            "concerning",
            "Это настораживающий симптом. Рекомендуем связаться с вашим лечащим врачом как можно скорее.",
        )

    return "informational", None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def is_critical_symptom(text: str) -> bool:
    if any(keyword in text for keyword in CRITICAL_KEYWORDS):
        return True

    if "температур" in text and re.search(r"\b39([.,]\d+)?\b|\b40([.,]\d+)?\b", text):
        return True

    if re.search(r"\b(14\d|15\d|16\d|17\d)\s*/\s*(9\d|10\d|11\d)\b", text):
        return True

    if "давление" in text and any(value in text for value in ("140", "150", "160", "170")):
        return True

    return False


def is_concerning_symptom(text: str) -> bool:
    if any(keyword in text for keyword in CONCERNING_KEYWORDS):
        return True

    if "температур" in text and re.search(r"\b37[.,][89]\b|\b38([.,]\d+)?\b", text):
        return True

    if re.search(r"\b(13\d)\s*/\s*(8\d|9\d)\b", text):
        return True

    return False


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
    articles = find_best_articles(db, query, limit=1)
    return articles[0] if articles else None


def find_best_articles(db: Session, query: str, limit: int = 3) -> list[KnowledgeBase]:
    query_lower = normalize_text(query)
    query_tokens = tokenize(query_lower)
    if not query_tokens:
        return []

    conditions = []
    for token in query_tokens:
        conditions.append(func.lower(KnowledgeBase.keywords).contains(token))
        conditions.append(func.lower(KnowledgeBase.title).contains(token))

    candidates = db.query(KnowledgeBase).filter(or_(*conditions)).limit(50).all()

    ranked: list[tuple[int, KnowledgeBase]] = []
    for article in candidates:
        score = score_article(article, query_lower, set(query_tokens))
        if score > 0:
            ranked.append((score, article))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [article for _, article in ranked[:limit]]


def tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"\b[а-яёa-z0-9]{3,}\b", text.lower(), flags=re.IGNORECASE)
        if token not in STOP_WORDS
    ]


def score_article(article: KnowledgeBase, query_lower: str, query_tokens: set[str]) -> int:
    title = article.title or ""
    keywords = article.keywords or ""
    content = article.content or ""
    category = article.category or ""

    title_lower = title.lower()
    keywords_lower = keywords.lower()
    content_lower = content.lower()
    category_lower = category.lower()

    title_tokens = set(tokenize(title_lower))
    keyword_tokens = set(tokenize(keywords_lower))
    content_tokens = set(tokenize(content_lower[:12000]))
    category_tokens = set(tokenize(category_lower))

    score = 0

    if query_lower and query_lower in title_lower:
        score += 15
    if query_lower and query_lower in keywords_lower:
        score += 10
    if query_lower and query_lower in content_lower:
        score += 6

    score += len(query_tokens & title_tokens) * 6
    score += len(query_tokens & keyword_tokens) * 5
    score += len(query_tokens & category_tokens) * 4
    score += len(query_tokens & content_tokens) * 2

    return score


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
    matches = find_best_articles(db, query, limit=3)

    if matches:
        context_blocks = build_context_blocks(matches)
        system_prompt = (
            "Ты — медицинский ассистент проекта «Мама Рядом». "
            "Отвечай ТОЛЬКО на основе предоставленного КОНТЕКСТА. "
            "🚫 ЗАПРЕЩЕНО: добавлять внешние факты, советы, дозировки или данные, которых нет в тексте. "
            "✅ РАЗРЕШЕНО: улучшать читаемость, разбивать на абзацы/списки, добавлять умеренные эмодзи, "
            "делать тон профессиональным, спокойным и поддерживающим. "
            "Не меняй медицинские термины, цифры и формулировки. Сохраняй точность. "
            "Если в контексте нет прямого ответа, напиши: «В моей базе знаний нет точной информации по этому вопросу. Пожалуйста, проконсультируйтесь с врачом.»\n\n"
            f"КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:\n{context_blocks}\n"
            f"КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:{context_info}"
        )
        llm_answer = ask_ollama(system_prompt, query)
        if llm_answer:
            return llm_answer.strip()

        # Фоллбэк: если Ollama недоступен, возвращаем сырой текст из БД
        return f"{context_blocks}\n{context_info}".strip()

    # Если точных совпадений нет → обращаемся к общей базе знаний модели
    system_prompt_fallback = (
        "Ты добрый медицинский ассистент для беременных. "
        "Отвечай кратко, только на русском языке, профессионально и доброжелательно. "
        "Если точной информации нет, честно предупреди об этом.\n"
        f"{context_info}"
    )
    llm_answer = ask_ollama(system_prompt_fallback, query)
    if llm_answer:
        return (
            "⚠️ Этой информации нет в моей официальной базе, "
            "ответ основан на общих медицинских знаниях.\n\n"
            f"{llm_answer}"
        ).strip()

    return (
        "К сожалению, я не нашел информации по этому вопросу ни в базе, ни в локальной модели. "
        "Пожалуйста, обратитесь к врачу."
        f"{context_info}"
    ).strip()

def build_context_blocks(matches: list[KnowledgeBase], max_total_length: int = 7000) -> str:
    blocks: list[str] = []
    total_length = 0

    for article in matches:
        block = f"[{article.title}]\n{article.content.strip()}"
        if total_length + len(block) > max_total_length and blocks:
            break
        blocks.append(block)
        total_length += len(block)

    return "\n\n".join(blocks)


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
