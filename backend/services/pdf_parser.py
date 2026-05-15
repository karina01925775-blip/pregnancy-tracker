from __future__ import annotations

import html
import math
import re
from collections import Counter
from io import BytesIO
from typing import Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests

try:
    import pdfplumber
except ImportError:  # pragma: no cover - зависит от окружения
    pdfplumber = None


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def extract_google_drive_file_id(source: str) -> Optional[str]:
    """Возвращает ID файла Google Drive из ссылки или самого ID."""
    source = (source or "").strip()
    if not source:
        return None

    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", source):
        return source

    parsed = urlparse(source)
    if "drive.google.com" not in parsed.netloc and "drive.usercontent.google.com" not in parsed.netloc:
        return None

    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", parsed.path)
    if match:
        return match.group(1)

    ids = parse_qs(parsed.query).get("id")
    if ids:
        return ids[0]

    return None


def parse_google_drive_pdf(file_id: str) -> Optional[str]:
    """Совместимость со старым API: возвращает только текст PDF."""
    document = parse_pdf_document(file_id)
    return document["content"] if document else None


def parse_pdf_document(source: str, title: Optional[str] = None) -> Optional[dict]:
    """Скачивает PDF и возвращает очищенный текст с метаданными."""
    payload = download_pdf(source)
    if not payload:
        return None

    text = extract_text_from_pdf_bytes(payload["content"])
    if not text:
        return None

    resolved_title = title or _title_from_filename(payload["filename"]) or "PDF документ"
    return {
        "title": resolved_title,
        "content": text,
        "filename": payload["filename"],
        "source_url": payload["source_url"],
        "final_url": payload["final_url"],
    }


def download_pdf(source: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    """Скачивает PDF по обычной ссылке или через Google Drive."""
    http = session or requests.Session()
    http.headers.update(DEFAULT_HEADERS)

    drive_file_id = extract_google_drive_file_id(source)

    try:
        if drive_file_id:
            response = _download_google_drive_file(http, drive_file_id)
        else:
            response = http.get(source, timeout=60, allow_redirects=True)
            response.raise_for_status()

        if not _looks_like_pdf_response(response):
            raise ValueError("Сервер вернул не PDF-файл")

        filename = _extract_filename(response) or _title_from_url(response.url) or "document.pdf"
        return {
            "content": response.content,
            "filename": filename,
            "source_url": source,
            "final_url": response.url,
        }
    except Exception as exc:
        print(f"❌ Ошибка загрузки PDF {source}: {exc}")
        return None


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Извлекает и очищает текст PDF."""
    if pdfplumber is None:
        raise RuntimeError(
            "Для парсинга PDF нужен пакет pdfplumber. "
            "Установите зависимости из requirements.txt."
        )

    page_texts: list[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if page_text.strip():
                page_texts.append(page_text)

    if not page_texts:
        return ""

    cleaned_pages = _remove_repeated_margins(page_texts)
    raw_text = "\n\n".join(cleaned_pages)
    return cleanup_pdf_text(raw_text)


def cleanup_pdf_text(text: str) -> str:
    """Чистит типовые артефакты PDF: переносы, мусорные строки, дубли."""
    text = text.replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = re.sub(r"(?<=[A-Za-zА-Яа-яЁё])-+\n(?=[A-Za-zА-Яа-яЁё])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if not line:
            _flush_paragraph(current, paragraphs)
            continue

        if _looks_like_page_number(line):
            continue

        if _looks_like_heading(line) or _looks_like_list_item(line):
            _flush_paragraph(current, paragraphs)
            paragraphs.append(line)
            continue

        current.append(line)

    _flush_paragraph(current, paragraphs)

    cleaned = "\n\n".join(paragraphs)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _download_google_drive_file(session: requests.Session, file_id: str) -> requests.Response:
    base_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = session.get(base_url, timeout=60, allow_redirects=True)
    response.raise_for_status()

    if _looks_like_pdf_response(response):
        return response

    confirm_url = _extract_drive_confirm_url(response.text, file_id)
    if not confirm_url:
        raise ValueError("Google Drive не отдал PDF и не вернул ссылку подтверждения")

    response = session.get(confirm_url, timeout=60, allow_redirects=True)
    response.raise_for_status()
    return response


def _extract_drive_confirm_url(page_html: str, file_id: str) -> Optional[str]:
    match = re.search(r'href="([^"]*confirm=[^"]+)"', page_html)
    if match:
        href = html.unescape(match.group(1).replace("&amp;", "&"))
        return urljoin("https://drive.google.com", href)

    match = re.search(r'confirm=([0-9A-Za-z_-]+)', page_html)
    if match:
        token = match.group(1)
        return f"https://drive.google.com/uc?export=download&confirm={token}&id={file_id}"

    return None


def _looks_like_pdf_response(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    return (
        "application/pdf" in content_type
        or "application/octet-stream" in content_type
        or response.content[:4] == b"%PDF"
    )


def _extract_filename(response: requests.Response) -> Optional[str]:
    disposition = response.headers.get("Content-Disposition") or ""
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
    if match:
        return requests.utils.unquote(match.group(1)).strip()
    return None


def _title_from_filename(filename: str) -> str:
    return re.sub(r"\.pdf$", "", filename.strip(), flags=re.IGNORECASE)


def _title_from_url(url: str) -> Optional[str]:
    path = urlparse(url).path.rstrip("/")
    if not path:
        return None
    return path.split("/")[-1]


def _remove_repeated_margins(page_texts: list[str]) -> list[str]:
    cleaned_pages: list[list[str]] = []
    top_counter: Counter[str] = Counter()
    bottom_counter: Counter[str] = Counter()

    for page_text in page_texts:
        lines = [_normalize_line(line) for line in page_text.splitlines()]
        lines = [line for line in lines if line]
        cleaned_pages.append(lines)
        top_counter.update(set(lines[:3]))
        bottom_counter.update(set(lines[-3:]))

    threshold = max(2, math.ceil(len(cleaned_pages) * 0.4))
    repeated_top = {line for line, count in top_counter.items() if count >= threshold}
    repeated_bottom = {line for line, count in bottom_counter.items() if count >= threshold}
    repeated_margin_lines = repeated_top | repeated_bottom

    result: list[str] = []
    for lines in cleaned_pages:
        page_lines = [
            line
            for line in lines
            if line not in repeated_margin_lines and not _looks_like_page_number(line)
        ]
        result.append("\n".join(page_lines).strip())

    return [page for page in result if page]


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def _looks_like_page_number(line: str) -> bool:
    candidate = line.strip().lower()
    return bool(
        re.fullmatch(r"(стр\.?\s*)?\d{1,4}(\s*(/|из)\s*\d{1,4})?", candidate)
        or re.fullmatch(r"\d{1,4}\s*-\s*\d{1,4}", candidate)
    )


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip().strip(":")
    if len(stripped) < 4 or len(stripped) > 160:
        return False

    if re.match(r"^\d+(\.\d+)*\.?\s+\S+", stripped):
        return True

    if line.endswith(":"):
        return True

    letters = [char for char in stripped if char.isalpha()]
    if not letters:
        return False

    upper_ratio = sum(char.isupper() for char in letters) / len(letters)
    return upper_ratio > 0.7 and len(stripped.split()) <= 14


def _looks_like_list_item(line: str) -> bool:
    return bool(re.match(r"^([-\u2022*]|\d+[.)]|[а-яa-z][)])\s+", line.strip(), re.IGNORECASE))


def _flush_paragraph(current: list[str], paragraphs: list[str]) -> None:
    if not current:
        return

    text = " ".join(current)
    text = re.sub(r"\s+", " ", text).strip()
    if text:
        paragraphs.append(text)
    current.clear()
