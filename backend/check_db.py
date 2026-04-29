# check_db.py
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Загружаем .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL не найден в .env")
    print(f"Ищем файл: {env_path.absolute()}")
    exit(1)

print(f"Подключение к БД: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
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