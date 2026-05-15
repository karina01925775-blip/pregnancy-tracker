from __future__ import annotations

import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.database import SessionLocal, engine, Base
from backend.models import KnowledgeBase
from backend.services.pdf_parser import extract_google_drive_file_id, parse_pdf_document


BASE_URL = "https://roag-portal.ru"
RECOMMENDATIONS_URL = f"{BASE_URL}/recommendations_obstetrics"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

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
    "под",
    "над",
    "без",
    "через",
    "или",
    "не",
    "ни",
    "поэтому",
    "также",
    "может",
    "быть",
    "если",
    "этой",
    "этого",
    "этот",
    "который",
    "которые",
    "беременности",
}

MEDICAL_KEYWORDS = (
    "беремен",
    "род",
    "плод",
    "акуш",
    "плацент",
    "гестац",
    "экламп",
    "выкидыш",
    "кров",
    "послерод",
    "преэкламп",
    "холестаз",
    "амниот",
    "период",
    "гипокси",
)

TOPIC_RULES = {
    "симптомы": ("симптом", "жалоб", "боль", "кровотеч", "выделен", "рвота", "головная боль"),
    "тревожные симптомы": ("кровотеч", "экламп", "судорог", "отходят воды", "нет шевелений"),
    "обследования": ("обследован", "диагностик", "скрининг", "узи", "анализ", "мониторинг"),
    "питание": ("питани", "диет", "кофеин", "витамин", "масса тела"),
    "активность": ("физическ", "активност", "нагруз", "упражнен", "ходьб"),
    "лечение": ("терап", "лечение", "препарат", "профилактик"),
    "роды": ("роды", "родоразрешение", "кесарев", "послеродов"),
}

UNWANTED_MARKERS = (
    "предложения по внесению изменений в действующие клинические рекомендации",
    "пользовательское соглашение",
    "политика конфиденциальности",
    "наверх",
    "вернуться назад",
)


def fetch_page(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Скачивает HTML-страницу с обработкой кодировки и ошибок."""
    http = session or requests.Session()
    http.headers.update(HEADERS)

    try:
        response = http.get(url, timeout=30)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response.text
    except Exception as exc:
        print(f"❌ Ошибка загрузки {url}: {exc}")
        return None


def parse_recommendations_list(html: str) -> list[dict]:
    """Извлекает рекомендации со страницы РОАГ."""
    soup = BeautifulSoup(html, "html.parser")
    recommendations: list[dict] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        title = normalize_title(anchor.get_text(" ", strip=True))
        href = anchor["href"].strip()
        url = normalize_url(href)
        if not title or not url:
            continue

        if title.lower() == "подробнее":
            continue

        if is_pdf_link(url):
            key = extract_google_drive_file_id(url) or url
            if key in seen:
                continue
            seen.add(key)
            recommendations.append({"title": title, "url": url, "source_type": "pdf"})
            continue

        if is_roag_recommendation_link(title, url):
            if url in seen:
                continue
            seen.add(url)
            recommendations.append({"title": title, "url": url, "source_type": "html"})

    return recommendations


def parse_recommendation_page(html: str, source_title: str) -> Optional[dict]:
    """Извлекает структурированный контент с HTML-страницы рекомендации."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "form", "noscript", "svg"]):
        tag.decompose()

    candidate_selectors = [
        "article",
        "main",
        ".t-redactor__text",
        ".t-card__descr",
        ".t-container",
        ".t-col",
        "body",
    ]

    content_text = ""
    for selector in candidate_selectors:
        nodes = soup.select(selector)
        for node in nodes:
            text = clean_document_text(node.get_text("\n", strip=True))
            if len(text) > len(content_text):
                content_text = text

    if not content_text:
        return None

    return build_document_payload(source_title, content_text)


def build_document_payload(title: str, content: str) -> Optional[dict]:
    cleaned_title = normalize_title(title)
    cleaned_content = clean_document_text(content)

    if not cleaned_title or len(cleaned_content) < 300:
        return None

    sections = split_into_sections(cleaned_title, cleaned_content)
    if not sections:
        return None

    structured_content = "\n\n".join(
        f"### {section['title']}\n{section['content']}"
        for section in sections
        if section["content"].strip()
    )

    keywords = extract_keywords(cleaned_title, structured_content)
    return {
        "title": cleaned_title,
        "content": structured_content,
        "category": infer_category(cleaned_title, structured_content),
        "keywords": keywords,
    }


def normalize_url(href: str) -> Optional[str]:
    href = (href or "").strip()
    if not href or href.startswith("#") or href.startswith("javascript:"):
        return None
    return href if href.startswith("http") else urljoin(BASE_URL, href)


def normalize_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    title = re.sub(r"\s*подробнее\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\.pdf$", "", title, flags=re.IGNORECASE)
    return title.strip(" -")


def is_pdf_link(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.path.lower().endswith(".pdf")
        or "drive.google.com" in parsed.netloc
        or "drive.usercontent.google.com" in parsed.netloc
    )


def is_roag_recommendation_link(title: str, url: str) -> bool:
    parsed = urlparse(url)
    if "roag-portal.ru" not in parsed.netloc:
        return False

    title_lower = title.lower()
    if len(title_lower) < 20:
        return False

    if url.rstrip("/") == RECOMMENDATIONS_URL.rstrip("/"):
        return False

    if title_lower == "клинические рекомендации":
        return False

    return "recommend" in parsed.path.lower() or any(keyword in title_lower for keyword in MEDICAL_KEYWORDS)


def clean_document_text(text: str) -> str:
    text = text.replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lower_text = text.lower()
    cut_positions = [lower_text.find(marker) for marker in UNWANTED_MARKERS if marker in lower_text]
    cut_positions = [position for position in cut_positions if position >= 200]
    if cut_positions:
        text = text[: min(cut_positions)]

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if looks_like_heading(line):
            flush_paragraph(current, paragraphs)
            paragraphs.append(line)
            continue

        current.append(line)

    flush_paragraph(current, paragraphs)
    return "\n\n".join(paragraphs).strip()


def split_into_sections(title: str, content: str) -> list[dict]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", content) if paragraph.strip()]
    if not paragraphs:
        return []

    sections: list[dict] = []
    current_title = title
    current_content: list[str] = []

    for paragraph in paragraphs:
        if paragraph == title:
            continue

        if looks_like_heading(paragraph):
            if current_content:
                sections.append(
                    {
                        "title": current_title,
                        "content": " ".join(current_content).strip(),
                    }
                )
            current_title = paragraph
            current_content = []
            continue

        current_content.append(paragraph)

    if current_content:
        sections.append(
            {
                "title": current_title,
                "content": " ".join(current_content).strip(),
            }
        )

    return [section for section in sections if len(section["content"]) >= 80]


def looks_like_heading(text: str) -> bool:
    candidate = text.strip().strip(":")
    if len(candidate) < 4 or len(candidate) > 160:
        return False

    if re.match(r"^\d+(\.\d+)*\.?\s+\S+", candidate):
        return True

    if text.endswith(":"):
        return True

    letters = [char for char in candidate if char.isalpha()]
    if not letters:
        return False

    upper_ratio = sum(char.isupper() for char in letters) / len(letters)
    return upper_ratio > 0.7 and len(candidate.split()) <= 14


def extract_keywords(title: str, text: str, max_keywords: int = 20) -> str:
    sample = f"{title}\n{text[:8000]}"
    words = re.findall(r"\b[а-яёa-z]{3,}\b", sample.lower(), flags=re.IGNORECASE)
    freq = Counter(word for word in words if word not in STOP_WORDS)

    keywords: list[str] = []
    for topic in infer_topics(title, text):
        keywords.append(topic)

    for word, _ in freq.most_common(max_keywords):
        keywords.append(word)

    keywords.append("source:roag")

    unique_keywords: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = keyword.strip().lower()
        if normalized and normalized not in seen:
            unique_keywords.append(normalized)
            seen.add(normalized)

    return ", ".join(unique_keywords)


def infer_topics(title: str, text: str) -> list[str]:
    haystack = f"{title} {text}".lower()
    topics = [
        topic
        for topic, markers in TOPIC_RULES.items()
        if any(marker in haystack for marker in markers)
    ]
    return topics or ["клинические рекомендации"]


def infer_category(title: str, text: str) -> str:
    topics = infer_topics(title, text)
    if "обследования" in topics:
        return "Обследования"
    if "питание" in topics:
        return "Питание"
    if "активность" in topics:
        return "Активность"
    if "симптомы" in topics or "тревожные симптомы" in topics:
        return "Симптомы"
    return "Клинические рекомендации"


def chunk_content(content: str, chunk_size: int = 1800, overlap: int = 300) -> list[str]:
    """Разбивает длинный текст на крупные смысловые чанки для RAG."""
    blocks = [block.strip() for block in re.split(r"\n{2,}", content) if block.strip()]
    if not blocks:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for block in blocks:
        block_length = len(block) + 2
        if current and current_length + block_length > chunk_size:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append(chunk)

            overlap_blocks = collect_overlap_blocks(current, overlap)
            current = overlap_blocks + [block] if overlap_blocks else [block]
            current_length = sum(len(item) + 2 for item in current)
            continue

        current.append(block)
        current_length += block_length

    if current:
        chunk = "\n\n".join(current).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def collect_overlap_blocks(blocks: list[str], overlap: int) -> list[str]:
    if overlap <= 0:
        return []

    collected: list[str] = []
    collected_length = 0

    for block in reversed(blocks):
        block_length = len(block) + 2
        if collected and collected_length + block_length > overlap:
            break
        collected.insert(0, block)
        collected_length += block_length

    return collected


def save_to_database(db: Session, data: dict) -> int:
    """Сохраняет данные в KnowledgeBase с обновлением старых чанков РОАГ."""
    delete_existing_roag_entries(db, data["title"])

    chunks = chunk_content(data["content"]) if len(data["content"]) > 1800 else [data["content"]]
    added = 0

    for index, chunk in enumerate(chunks, start=1):
        title = data["title"] if len(chunks) == 1 else f"{data['title']} (часть {index}/{len(chunks)})"
        db.add(
            KnowledgeBase(
                category=data["category"],
                title=title,
                content=chunk,
                keywords=data["keywords"],
            )
        )
        added += 1
        print(f"✅ Добавлено: {title[:90]}")

    return added


def delete_existing_roag_entries(db: Session, base_title: str) -> None:
    existing_entries = (
        db.query(KnowledgeBase)
        .filter(
            or_(
                KnowledgeBase.title == base_title,
                KnowledgeBase.title.like(f"{base_title} (часть %"),
            ),
            KnowledgeBase.keywords.contains("source:roag"),
        )
        .all()
    )

    for entry in existing_entries:
        db.delete(entry)


def process_recommendation(recommendation: dict, session: requests.Session) -> Optional[dict]:
    if recommendation["source_type"] == "pdf":
        pdf_document = parse_pdf_document(recommendation["url"], title=recommendation["title"])
        if not pdf_document:
            return None
        return build_document_payload(recommendation["title"], pdf_document["content"])

    html = fetch_page(recommendation["url"], session=session)
    if not html:
        return None
    return parse_recommendation_page(html, recommendation["title"])


def seed_roag_recommendations(limit: Optional[int] = None, delay_seconds: float = 1.0) -> None:
    """Основная функция парсинга клинических рекомендаций РОАГ."""
    print("🔍 Начинаем парсинг клинических рекомендаций РОАГ...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        html = fetch_page(RECOMMENDATIONS_URL, session=session)
        if not html:
            print("❌ Не удалось загрузить главную страницу РОАГ")
            return

        recommendations = parse_recommendations_list(html)
        if limit is not None:
            recommendations = recommendations[:limit]

        print(f"📋 Найдено рекомендаций: {len(recommendations)}")

        added_chunks = 0
        processed = 0
        failed = 0

        for index, recommendation in enumerate(recommendations, start=1):
            print(f"\n[{index}/{len(recommendations)}] Обработка: {recommendation['title']}")
            try:
                data = process_recommendation(recommendation, session)
                if not data:
                    failed += 1
                    print("⚠️ Не удалось получить полезный контент")
                    continue

                added_chunks += save_to_database(db, data)
                db.commit()
                processed += 1
            except Exception as exc:
                db.rollback()
                failed += 1
                print(f"❌ Ошибка обработки {recommendation['title']}: {exc}")

            time.sleep(delay_seconds)

        print(
            "\n🎉 Парсинг завершён. "
            f"Документов обработано: {processed}, ошибок: {failed}, чанков добавлено: {added_chunks}"
        )
    finally:
        db.close()
        session.close()


def flush_paragraph(current: list[str], paragraphs: list[str]) -> None:
    if not current:
        return
    text = re.sub(r"\s+", " ", " ".join(current)).strip()
    if text:
        paragraphs.append(text)
    current.clear()


if __name__ == "__main__":
    seed_roag_recommendations()
