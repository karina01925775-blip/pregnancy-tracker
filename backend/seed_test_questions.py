# backend/seed_test_questions.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal, engine, Base
from backend.models import TestQuestion

# 10 вопросов для теста (последний — открытый)
TEST_QUESTIONS = [
    {
        "question_text": "Как вы оцениваете своё общее самочувствие сегодня?",
        "question_type": "multiple_choice",
        "options": "Отлично|Хорошо|Нормально|Плохо|Очень плохо",
        "order_index": 1,
        "category": "mood"
    },
    {
        "question_text": "Были ли у вас сегодня боли в животе?",
        "question_type": "multiple_choice",
        "options": "Нет|Лёгкие, не мешают|Умеренные, отвлекают|Сильные, мешают делать дела|Очень сильные, невыносимые",
        "order_index": 2,
        "category": "symptoms"
    },
    {
        "question_text": "Замечали ли вы сегодня необычные выделения?",
        "question_type": "multiple_choice",
        "options": "Нет|Прозрачные/белые, без запаха|Жёлтые/зелёные|С неприятным запахом|Кровянистые",
        "order_index": 3,
        "category": "symptoms"
    },
    {
        "question_text": "Как вы спали прошлой ночью?",
        "question_type": "multiple_choice",
        "options": "Отлично, выспалась|Хорошо|Нормально|Плохо, часто просыпалась|Очень плохо, почти не спала",
        "order_index": 4,
        "category": "sleep"
    },
    {
        "question_text": "Была ли у вас сегодня тошнота или рвота?",
        "question_type": "multiple_choice",
        "options": "Нет|Лёгкая тошнота|Тошнота с рвотой 1 раз|Рвота несколько раз|Постоянная тошнота и рвота",
        "order_index": 5,
        "category": "symptoms"
    },
    {
        "question_text": "Как вы оцениваете уровень своей энергии сегодня?",
        "question_type": "multiple_choice",
        "options": "Полна сил|Хороший уровень|Нормально|Усталость|Полное истощение",
        "order_index": 6,
        "category": "mood"
    },
    {
        "question_text": "Замечали ли вы отёки (ноги, руки, лицо)?",
        "question_type": "multiple_choice",
        "options": "Нет|Лёгкие, к вечеру|Умеренные, видны|Сильные, мешают|Очень сильные, болезненные",
        "order_index": 7,
        "category": "symptoms"
    },
    {
        "question_text": "Как вы питались сегодня?",
        "question_type": "multiple_choice",
        "options": "Полноценно и полезно|Нормально, но могли бы лучше|Перекусы, мало еды|Почти не ела|Ела вредное/запрещённое",
        "order_index": 8,
        "category": "nutrition"
    },
    {
        "question_text": "Чувствовали ли вы шевеления малыша сегодня?",
        "question_type": "multiple_choice",
        "options": "Да, активно|Да, нормально|Редко, слабо|Не чувствовала|Ещё рано чувствовать",
        "order_index": 9,
        "category": "baby_activity"
    },
    {
        "question_text": "Опишите своими словами, как вы себя чувствуете сегодня",
        "question_type": "text",
        "options": None,
        "order_index": 10,
        "category": "open_feedback",
        "is_required": False
    }
]


def seed_test_questions():
    print("🌱 Наполняем базу вопросами для теста...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        added = 0
        for item in TEST_QUESTIONS:
            exists = db.query(TestQuestion).filter(
                TestQuestion.question_text == item["question_text"]
            ).first()
            if not exists:
                q = TestQuestion(**item)
                db.add(q)
                added += 1
                print(f"✅ Добавлен вопрос: {item['question_text'][:50]}...")

        db.commit()
        print(f"\n🎉 Готово! Добавлено вопросов: {added}")
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_questions()