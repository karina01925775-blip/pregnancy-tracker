from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv('DATABASE_URL')

#🔹 Для SQLite нужен специальный флаг, отключаем pool_size
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

if not DATABASE_URL:
    print("ОШИБКА: DATABASE_URL не найден в файле .env")
    print(f"Ищем файл по пути: {env_path}")
    print("Создайте файл .env с содержимым:")
    print("DATABASE_URL=postgresql://postgres:mysecretpassword@localhost:5432/mama_ryadom")
    raise ValueError("DATABASE_URL не задан")

# Для SQLite
engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=True)
#engine = create_engine(DATABASE_URL, pool_size=10, echo=True)
Base = declarative_base()
# Для SQLite закоментчино
#se.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()