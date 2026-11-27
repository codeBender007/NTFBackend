"""
Idempotent MSSQL database setup & migration script for LMS Question Papers tables.

Creates / migrates:
  1. dbo.question_papers
  2. dbo.question_paper_submissions (plus idempotent grading column migration)
  3. dbo.question_paper_assignments

Usage (from NTFBackend/):
    python scripts/create_question_paper_tables.py
"""
import os
import sys

# Ensure NTFBackend root is on sys.path when invoked directly as `python scripts/create_question_paper_tables.py`
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy import inspect, text

from app.core.database import Base, engine
# Import all referenced parent models so SQLAlchemy resolves ForeignKey targets cleanly
from app.LMS.models import (  # noqa: F401
    Department,
    Line,
    Machine,
    Plant,
    QuestionPaper,
    QuestionPaperAssignment,
    QuestionPaperSubmission,
    SubDepartment,
    User,
)

TARGET_TABLES = [
    QuestionPaper.__table__,
    QuestionPaperSubmission.__table__,
    QuestionPaperAssignment.__table__,
]

# Columns added to question_paper_submissions for Supervisor Evaluation & Grading
SUBMISSION_GRADING_COLUMNS_MSSQL = [
    ("question_marks_json", "NVARCHAR(MAX) NULL"),
    ("is_graded", "BIT NOT NULL CONSTRAINT DF_qps_is_graded DEFAULT 0"),
    ("evaluation_status", "NVARCHAR(50) NOT NULL CONSTRAINT DF_qps_eval_status DEFAULT N'Pending Review'"),
    ("graded_by", "INT NULL"),
    ("graded_by_name", "NVARCHAR(150) NULL"),
    ("graded_at", "DATETIME NULL"),
]

SUBMISSION_GRADING_COLUMNS_SQLITE = [
    ("question_marks_json", "TEXT NULL"),
    ("is_graded", "BOOLEAN NOT NULL DEFAULT 0"),
    ("evaluation_status", "VARCHAR(50) NOT NULL DEFAULT 'Pending Review'"),
    ("graded_by", "INTEGER NULL"),
    ("graded_by_name", "VARCHAR(150) NULL"),
    ("graded_at", "DATETIME NULL"),
]


def _migrate_submission_grading_columns(bind_engine=engine) -> None:
    inspector = inspect(bind_engine)
    if "question_paper_submissions" not in set(inspector.get_table_names()):
        return

    existing_cols = {c["name"].lower() for c in inspector.get_columns("question_paper_submissions")}
    dialect_name = bind_engine.dialect.name
    col_specs = (
        SUBMISSION_GRADING_COLUMNS_MSSQL
        if dialect_name == "mssql"
        else SUBMISSION_GRADING_COLUMNS_SQLITE
    )

    added_cols = []
    with bind_engine.begin() as conn:
        for col_name, col_ddl in col_specs:
            if col_name.lower() in existing_cols:
                continue
            if dialect_name == "mssql":
                conn.execute(
                    text(f"ALTER TABLE dbo.question_paper_submissions ADD {col_name} {col_ddl}")
                )
            else:
                conn.execute(
                    text(f"ALTER TABLE question_paper_submissions ADD COLUMN {col_name} {col_ddl}")
                )
            added_cols.append(col_name)

        # Ensure FK + index for graded_by on MSSQL if column was just added or FK is missing
        if dialect_name == "mssql":
            fk_exists = conn.execute(
                text(
                    "SELECT 1 FROM sys.foreign_keys "
                    "WHERE name = 'FK_question_paper_submissions_graded_by_users'"
                )
            ).first()
            if not fk_exists:
                conn.execute(
                    text(
                        "ALTER TABLE dbo.question_paper_submissions "
                        "ADD CONSTRAINT FK_question_paper_submissions_graded_by_users "
                        "FOREIGN KEY (graded_by) REFERENCES dbo.users(id)"
                    )
                )
            idx_exists = conn.execute(
                text(
                    "SELECT 1 FROM sys.indexes "
                    "WHERE name = 'IX_question_paper_submissions_graded_by' "
                    "AND object_id = OBJECT_ID('dbo.question_paper_submissions')"
                )
            ).first()
            if not idx_exists:
                conn.execute(
                    text(
                        "CREATE INDEX IX_question_paper_submissions_graded_by "
                        "ON dbo.question_paper_submissions (graded_by)"
                    )
                )

    if added_cols:
        print(f"  [MIGRATED] Added grading column(s) to 'question_paper_submissions': {added_cols}")
    else:
        print("  [OK]       All grading columns already present on 'question_paper_submissions'.")


def create_question_paper_tables(bind_engine=engine) -> None:
    inspector = inspect(bind_engine)
    existing_before = set(inspector.get_table_names())

    print("=" * 64)
    print("  NTF LMS Question Papers & Assignments - Database Table Setup")
    print("=" * 64)

    # checkfirst=True makes table creation completely idempotent (CREATE TABLE IF NOT EXISTS behavior)
    Base.metadata.create_all(bind=bind_engine, tables=TARGET_TABLES, checkfirst=True)

    inspector_after = inspect(bind_engine)
    existing_after = set(inspector_after.get_table_names())

    for tbl in TARGET_TABLES:
        name = tbl.name
        if name in existing_before:
            print(f"  [EXISTS]   Table '{name}' already exists.")
        elif name in existing_after:
            cols = [c["name"] for c in inspector_after.get_columns(name)]
            print(f"  [CREATED]  Table '{name}' created successfully ({len(cols)} columns).")
        else:
            raise RuntimeError(f"Table '{name}' was not found after create_all.")

    _migrate_submission_grading_columns(bind_engine)

    print("=" * 64)
    print("  Question paper, submission, and assignment tables are ready.")
    print("=" * 64)


if __name__ == "__main__":
    create_question_paper_tables()
