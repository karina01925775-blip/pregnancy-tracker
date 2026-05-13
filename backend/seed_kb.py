from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.seed_kb_parser import seed_knowledge_base


if __name__ == "__main__":
    seed_knowledge_base()
