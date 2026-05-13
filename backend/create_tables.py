from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import models
from backend.database import engine


def create_tables() -> None:
    models.Base.metadata.create_all(bind=engine)
    print("Таблицы базы данных созданы или уже существуют.")


if __name__ == "__main__":
    create_tables()
