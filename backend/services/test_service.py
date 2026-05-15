from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from backend import models


DEFAULT_TEST_QUESTIONS = [
    {
        "question_text": "Как вы оцениваете своё общее самочувствие сегодня?",
        "question_type": "multiple_choice",
        "options": "Отличное|Хорошее|Среднее|Плохое",
        "order_index": 1,
        "is_required": True,
        "category": "general",
    },
    {
        "question_text": "Какое у вас сегодня настроение?",
        "question_type": "multiple_choice",
        "options": "Спокойное|Немного тревожное|Тревожное|Подавленное",
        "order_index": 2,
        "is_required": True,
        "category": "mood",
    },
    {
        "question_text": "Есть ли сегодня боль или выраженный дискомфорт?",
        "question_type": "multiple_choice",
        "options": "Нет|Слабый дискомфорт|Умеренная боль|Сильная боль",
        "order_index": 3,
        "is_required": True,
        "category": "pain",
    },
    {
        "question_text": "Какой у вас сегодня уровень энергии?",
        "question_type": "multiple_choice",
        "options": "Высокий|Нормальный|Пониженный|Очень низкий",
        "order_index": 4,
        "is_required": True,
        "category": "energy",
    },
    {
        "question_text": "Как вы спали прошлой ночью?",
        "question_type": "multiple_choice",
        "options": "Хорошо|Просыпалась несколько раз|Спала плохо|Почти не спала",
        "order_index": 5,
        "is_required": True,
        "category": "sleep",
    },
    {
        "question_text": "Есть ли у вас сегодня тошнота или рвота?",
        "question_type": "multiple_choice",
        "options": "Нет|Лёгкая тошнота|Сильная тошнота|Была рвота",
        "order_index": 6,
        "is_required": True,
        "category": "symptoms",
    },
    {
        "question_text": "Замечали ли вы сегодня отёки, головную боль или скачки давления?",
        "question_type": "multiple_choice",
        "options": "Нет|Есть что-то одно|Несколько симптомов|Симптомы выраженные",
        "order_index": 7,
        "is_required": True,
        "category": "warning_signs",
    },
    {
        "question_text": "Как сегодня с аппетитом и питьевым режимом?",
        "question_type": "multiple_choice",
        "options": "Всё хорошо|Аппетит снижен|Пью мало воды|И аппетит, и вода хуже обычного",
        "order_index": 8,
        "is_required": True,
        "category": "nutrition",
    },
    {
        "question_text": "Если вы уже ощущаете шевеления, как они были сегодня?",
        "question_type": "multiple_choice",
        "options": "Пока не ощущаю сроком|Как обычно|Слабее обычного|Сильнее или необычно",
        "order_index": 9,
        "is_required": False,
        "category": "baby_movement",
    },
    {
        "question_text": "Опишите кратко, что вас больше всего беспокоит сегодня.",
        "question_type": "text",
        "options": None,
        "order_index": 10,
        "is_required": False,
        "category": "notes",
    },
]


def ensure_test_questions_seeded(db: Session) -> int:
    added_or_updated = 0

    for question_data in DEFAULT_TEST_QUESTIONS:
        question = (
            db.query(models.TestQuestion)
            .filter(models.TestQuestion.order_index == question_data["order_index"])
            .first()
        )

        if question is None:
            db.add(models.TestQuestion(**question_data))
            added_or_updated += 1
            continue

        for field_name, field_value in question_data.items():
            if getattr(question, field_name) != field_value:
                setattr(question, field_name, field_value)
                added_or_updated += 1

    if added_or_updated:
        db.commit()

    return added_or_updated


def get_history_window(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, time.min)
    end = start + timedelta(days=1)
    return start, end


def serialize_question(question: models.TestQuestion) -> dict:
    return {
        "id": question.id,
        "text": question.question_text,
        "type": question.question_type,
        "options": question.options.split("|") if question.options else [],
        "required": question.is_required,
        "category": question.category,
    }


def serialize_answer(answer: models.TestAnswer) -> dict:
    return {
        "id": answer.id,
        "question": answer.question.question_text,
        "answer": answer.answer_text or answer.selected_option or "",
        "date": answer.created_at.isoformat() if answer.created_at else None,
        "category": answer.question.category,
    }


def save_daily_test_answers(
    db: Session,
    *,
    user_id: int,
    pregnancy_id: Optional[int],
    answers: Iterable[dict],
    target_date: Optional[date] = None,
) -> int:
    submission_date = target_date or date.today()
    start, end = get_history_window(submission_date)
    saved_answers = 0

    for answer_data in answers:
        question = (
            db.query(models.TestQuestion)
            .filter(models.TestQuestion.id == answer_data["question_id"])
            .first()
        )
        if question is None:
            continue

        raw_answer = str(answer_data.get("answer", "")).strip()
        if not raw_answer:
            continue

        existing = (
            db.query(models.TestAnswer)
            .filter(
                models.TestAnswer.user_id == user_id,
                models.TestAnswer.question_id == question.id,
                models.TestAnswer.created_at >= start,
                models.TestAnswer.created_at < end,
            )
            .first()
        )

        answer_text = raw_answer if question.question_type == "text" else None
        selected_option = raw_answer if question.question_type != "text" else None

        if existing:
            existing.pregnancy_id = pregnancy_id
            existing.answer_text = answer_text
            existing.selected_option = selected_option
        else:
            db.add(
                models.TestAnswer(
                    user_id=user_id,
                    question_id=question.id,
                    pregnancy_id=pregnancy_id,
                    answer_text=answer_text,
                    selected_option=selected_option,
                    created_at=start + timedelta(seconds=question.order_index),
                )
            )

        saved_answers += 1

    db.commit()
    return saved_answers
