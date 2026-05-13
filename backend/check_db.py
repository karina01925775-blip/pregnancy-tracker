from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from sqlalchemy import create_engine, inspect
from backend.config import load_environment, normalize_database_url

load_environment()

DATABASE_URL = normalize_database_url(os.getenv('DATABASE_URL'))

print(f"Подключение к БД: {DATABASE_URL}")

try:
    # Для SQLite
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not tables:
        print("\n⚠️ Таблицы не найдены в базе данных")
        print("Убедитесь, что:")
        print("1. Вы запустили приложение (создание таблиц происходит при старте)")
        print("2. В models.py правильно определены модели")
        print("3. Вы импортировали все модели перед вызовом create_all()")
    else:
        print(f"\n✅ Найдено таблиц: {len(tables)}")
        for table in tables:
            # Считаем количество записей в каждой таблице
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"  📊 {table}: {count} записей")

except Exception as e:
    print(f"\n❌ Ошибка при подключении к БД: {e}")

