from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Unicode,
    UnicodeText,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class QuestionPaper(Base):
    """Unified master table for all LMS/DOJO question papers (Day 1, Day 2, L0, L1, etc.)."""

    __tablename__ = "question_papers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(Unicode(255), nullable=False)
    description = Column(Unicode(1000), nullable=True)
    day_type = Column(Unicode(50), nullable=False, index=True)  # e.g., 'DAY_1', 'DAY_2', 'L0', 'L1'

    # Paper document & assessment metadata (matches Day1QuestionPaper / Day2QuestionPaper / Editor)
    document_code = Column(Unicode(100), nullable=True)         # e.g., 'F18(AMD-02)'
    revision = Column(Unicode(50), nullable=True)               # e.g., 'Rev. 00'
    duration_minutes = Column(Integer, nullable=True, default=30)
    duration_label = Column(Unicode(100), nullable=True)        # e.g., '30 मिनट' / '30 Mins'
    total_marks = Column(Integer, nullable=True, default=20)
    pass_percentage = Column(Integer, nullable=True, default=80)
    total_questions = Column(Integer, nullable=False, default=0)
    passing_instruction = Column(Unicode(500), nullable=True)

    # Full LMS hierarchy mapping (nullable so papers can be plant-, dept-, subdept-, line-, or machine-scoped)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    sub_department_id = Column(Integer, ForeignKey("subDepartments.id"), nullable=True, index=True)
    line_id = Column(Integer, ForeignKey("lines.id"), nullable=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)

    # JSON payloads stored as NVARCHAR(MAX) in MSSQL to preserve Hindi/Devanagari & multilingual text
    sections_json = Column(UnicodeText, nullable=True)
    questions_json = Column(UnicodeText, nullable=False)
    metadata_json = Column(UnicodeText, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.getdate(), nullable=False)
    updated_at = Column(DateTime, server_default=func.getdate(), onupdate=func.getdate(), nullable=False)

    # Relationships
    plant = relationship("Plant", foreign_keys=[plant_id])
    department = relationship("Department", foreign_keys=[department_id])
    sub_department = relationship("SubDepartment", foreign_keys=[sub_department_id])
    line = relationship("Line", foreign_keys=[line_id])
    machine = relationship("Machine", foreign_keys=[machine_id])
    creator = relationship("User", foreign_keys=[created_by])
    submissions = relationship(
        "QuestionPaperSubmission",
        back_populates="question_paper",
        foreign_keys="[QuestionPaperSubmission.question_paper_id]",
        cascade="all, delete-orphan",
    )
    assignments = relationship(
        "QuestionPaperAssignment",
        back_populates="question_paper",
        foreign_keys="[QuestionPaperAssignment.question_paper_id]",
        cascade="all, delete-orphan",
    )


class QuestionPaperSubmission(Base):
    """Stores filled question paper submissions by employees/users and supervisor evaluation/grading."""

    __tablename__ = "question_paper_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    question_paper_id = Column(Integer, ForeignKey("question_papers.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day_type = Column(Unicode(50), nullable=False, index=True)  # e.g., 'DAY_1', 'DAY_2', 'L0', 'L1'

    # Hierarchy references captured for fast filtered reporting (resolved from paper/user)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    sub_department_id = Column(Integer, ForeignKey("subDepartments.id"), nullable=True, index=True)
    line_id = Column(Integer, ForeignKey("lines.id"), nullable=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)

    # Filled response payloads stored as NVARCHAR(MAX)
    answers_json = Column(UnicodeText, nullable=False)          # e.g., {"1": 0, "2": 2, "14": "text answer"}
    participant_info_json = Column(UnicodeText, nullable=True)  # e.g., {"time","date","name","designation","qualification","unit"}
    training_schedule_json = Column(UnicodeText, nullable=True) # Optional Step 2 TrainingSchedule payload

    # Evaluation & Supervisor grading metadata (matches submissionGradingStorage.js & SubmittedPapersPanel.jsx)
    answered_count = Column(Integer, nullable=False, default=0)
    total_questions = Column(Integer, nullable=False, default=0)
    score = Column(Numeric(10, 2), nullable=True)
    max_score = Column(Numeric(10, 2), nullable=True)
    percentage = Column(Numeric(5, 2), nullable=True)
    passed = Column(Boolean, nullable=True)
    status = Column(Unicode(50), nullable=False, default="SUBMITTED")
    remarks = Column(Unicode(500), nullable=True)

    question_marks_json = Column(UnicodeText, nullable=True)    # Per-question marks map {"1": 1, "2": 0.5, ...}
    is_graded = Column(Boolean, nullable=False, default=False)
    evaluation_status = Column(Unicode(50), nullable=False, default="Pending Review")  # 'Pending Review' | 'Graded'
    graded_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    graded_by_name = Column(Unicode(150), nullable=True)
    graded_at = Column(DateTime, nullable=True)

    submitted_at = Column(DateTime, server_default=func.getdate(), nullable=False)
    updated_at = Column(DateTime, server_default=func.getdate(), onupdate=func.getdate(), nullable=False)

    # Relationships
    question_paper = relationship(
        "QuestionPaper",
        back_populates="submissions",
        foreign_keys=[question_paper_id],
    )
    user = relationship("User", foreign_keys=[user_id])
    grader = relationship("User", foreign_keys=[graded_by])
    plant = relationship("Plant", foreign_keys=[plant_id])
    department = relationship("Department", foreign_keys=[department_id])
    sub_department = relationship("SubDepartment", foreign_keys=[sub_department_id])
    line = relationship("Line", foreign_keys=[line_id])
    machine = relationship("Machine", foreign_keys=[machine_id])


class QuestionPaperAssignment(Base):
    """
    Tracks manual question paper assignments made by a Supervisor to specific Operators.
    Transitions automatically from ASSIGNED/PENDING -> COMPLETED upon operator submission.
    """

    __tablename__ = "question_paper_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    question_paper_id = Column(Integer, ForeignKey("question_papers.id"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_by_name = Column(Unicode(150), nullable=True)

    day_type = Column(Unicode(50), nullable=False, index=True)
    status = Column(Unicode(50), nullable=False, default="ASSIGNED", index=True)  # 'ASSIGNED' | 'PENDING' | 'COMPLETED'
    submission_id = Column(Integer, ForeignKey("question_paper_submissions.id"), nullable=True, index=True)

    assigned_at = Column(DateTime, server_default=func.getdate(), nullable=False)
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    notes = Column(Unicode(500), nullable=True)
    metadata_json = Column(UnicodeText, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, server_default=func.getdate(), onupdate=func.getdate(), nullable=False)

    # Relationships
    question_paper = relationship(
        "QuestionPaper",
        back_populates="assignments",
        foreign_keys=[question_paper_id],
    )
    operator = relationship("User", foreign_keys=[operator_id])
    assigner = relationship("User", foreign_keys=[assigned_by])
    submission = relationship("QuestionPaperSubmission", foreign_keys=[submission_id])
