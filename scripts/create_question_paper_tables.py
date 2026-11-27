"""
Idempotent MSSQL database setup script for LMS Question Papers tables.

Creates:
  1. dbo.question_papers
  2. dbo.question_paper_submissions

Usage (from NTFBackend/):
    python scripts/create_question_paper_tables.py
"""
import os
import sys

# Ensure NTFBackend root is on sys.path when invoked directly as `python scripts/create_question_paper_tables.py`
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy import inspect

from app.core.database import Base, engine
# Import all referenced parent models so SQLAlchemy resolves ForeignKey targets cleanly
from app.LMS.models import (  # noqa: F401
    Department,
    Line,
    Machine,
    Plant,
    QuestionPaper,
    QuestionPaperSubmission,
    User,
)

TARGET_TABLES = [
    QuestionPaper.__table__,
    QuestionPaperSubmission.__table__,
]


def create_question_paper_tables() -> None:
    inspector = inspect(engine)
    existing_before = set(inspector.get_table_names())

    print("=" * 60)
    print("  NTF LMS Question Papers - Database Table Setup")
    print("=" * 60)

    # checkfirst=True makes table creation completely idempotent (CREATE TABLE IF NOT EXISTS behavior)
    Base.metadata.create_all(bind=engine, tables=TARGET_TABLES, checkfirst=True)

    inspector_after = inspect(engine)
    existing_after = set(inspector_after.get_table_names())

    for tbl in TARGET_TABLES:
        name = tbl.name
        if name in existing_before:
            print(f"  [EXISTS]  Table '{name}' already exists (no changes made).")
        elif name in existing_after:
            cols = [c["name"] for c in inspector_after.get_columns(name)]
            print(f"  [CREATED] Table '{name}' created successfully ({len(cols)} columns).")
        else:
            raise RuntimeError(f"Table '{name}' was not found after create_all.")

    print("=" * 60)
    print("  Question paper tables are ready.")
    print("=" * 60)


if __name__ == "__main__":
    create_question_paper_tables()
