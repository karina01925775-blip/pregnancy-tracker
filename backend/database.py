import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ОШИБКА: DATABASE_URL не найден в файле .env")
    print(f"Ищем файл по пути: {env_path}")
    print("Создайте файл .env с содержимым:")
    print("DATABASE_URL=postgresql://postgres:mysecretpassword@localhost:5432/mama_ryadom")
    raise ValueError("DATABASE_URL не задан")

engine = create_engine(DATABASE_URL, pool_size=10, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()