from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class QuestionPaperCreate(BaseModel):
    """Schema for creating a unified Day 1 / Day 2 / custom question paper."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    day_type: str = Field(
        ...,
        validation_alias=AliasChoices("day_type", "dayType", "paper_type", "paperType"),
        description="Assessment type, e.g. DAY_1, DAY_2, L0, L1",
    )

    document_code: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("document_code", "documentCode"),
        max_length=100,
    )
    revision: Optional[str] = Field(None, max_length=50)
    duration_minutes: Optional[int] = Field(
        30,
        ge=1,
        validation_alias=AliasChoices("duration_minutes", "durationMinutes"),
    )
    duration_label: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("duration_label", "durationLabel"),
        max_length=100,
    )
    total_marks: Optional[int] = Field(
        20,
        ge=0,
        validation_alias=AliasChoices("total_marks", "totalMarks"),
    )
    pass_percentage: Optional[int] = Field(
        80,
        ge=0,
        le=100,
        validation_alias=AliasChoices("pass_percentage", "passPercentage"),
    )
    total_questions: Optional[int] = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("total_questions", "totalQuestions"),
    )
    passing_instruction: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("passing_instruction", "passingInstruction"),
        max_length=500,
    )

    # Full hierarchy IDs (accepts both snake_case and camelCase)
    plant_id: Optional[int] = Field(None, validation_alias=AliasChoices("plant_id", "plantId"))
    department_id: Optional[int] = Field(None, validation_alias=AliasChoices("department_id", "departmentId"))
    sub_department_id: Optional[int] = Field(
        None, validation_alias=AliasChoices("sub_department_id", "subDepartmentId")
    )
    line_id: Optional[int] = Field(None, validation_alias=AliasChoices("line_id", "lineId"))
    machine_id: Optional[int] = Field(None, validation_alias=AliasChoices("machine_id", "machineId"))

    # Supports Day 1 grouped object ({general:[...], safety:[...]}),
    # Day 2 numbered map ({"1": {q, options}, ...}), or structured list/sections array
    sections: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    questions: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = Field(
        None, validation_alias=AliasChoices("metadata", "meta")
    )

    is_active: Optional[bool] = Field(True, validation_alias=AliasChoices("is_active", "isActive"))
    created_by: Optional[int] = Field(None, validation_alias=AliasChoices("created_by", "createdBy"))


class QuestionPaperUpdate(BaseModel):
    """Schema for partially updating an existing question paper."""

    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    day_type: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("day_type", "dayType", "paper_type", "paperType"),
    )
    document_code: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("document_code", "documentCode"),
        max_length=100,
    )
    revision: Optional[str] = Field(None, max_length=50)
    duration_minutes: Optional[int] = Field(
        None,
        ge=1,
        validation_alias=AliasChoices("duration_minutes", "durationMinutes"),
    )
    duration_label: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("duration_label", "durationLabel"),
        max_length=100,
    )
    total_marks: Optional[int] = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("total_marks", "totalMarks"),
    )
    pass_percentage: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        validation_alias=AliasChoices("pass_percentage", "passPercentage"),
    )
    total_questions: Optional[int] = Field(
        None,
        ge=0,
        validation_alias=AliasChoices("total_questions", "totalQuestions"),
    )
    passing_instruction: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("passing_instruction", "passingInstruction"),
        max_length=500,
    )

    plant_id: Optional[int] = Field(None, validation_alias=AliasChoices("plant_id", "plantId"))
    department_id: Optional[int] = Field(None, validation_alias=AliasChoices("department_id", "departmentId"))
    sub_department_id: Optional[int] = Field(
        None, validation_alias=AliasChoices("sub_department_id", "subDepartmentId")
    )
    line_id: Optional[int] = Field(None, validation_alias=AliasChoices("line_id", "lineId"))
    machine_id: Optional[int] = Field(None, validation_alias=AliasChoices("machine_id", "machineId"))

    sections: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    questions: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = Field(
        None, validation_alias=AliasChoices("metadata", "meta")
    )
    is_active: Optional[bool] = Field(None, validation_alias=AliasChoices("is_active", "isActive"))


class QuestionPaperResponse(BaseModel):
    """Full question paper response including resolved hierarchy details and structured questions payload."""

    id: int
    title: str
    description: Optional[str] = None
    day_type: str
    document_code: Optional[str] = None
    revision: Optional[str] = None
    duration_minutes: Optional[int] = None
    duration_label: Optional[str] = None
    total_marks: Optional[int] = None
    pass_percentage: Optional[int] = None
    total_questions: int = 0
    passing_instruction: Optional[str] = None

    plant_id: Optional[int] = None
    plant_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    sub_department_id: Optional[int] = None
    sub_department_name: Optional[str] = None
    line_id: Optional[int] = None
    line_name: Optional[str] = None
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None

    sections: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    questions: Union[List[Dict[str, Any]], Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None

    is_active: bool = True
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QuestionPaperSubmissionCreate(BaseModel):
    """Schema for submitting a filled Day 1 / Day 2 / assessment question paper."""

    model_config = ConfigDict(populate_by_name=True)

    question_paper_id: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("question_paper_id", "questionPaperId", "paper_id", "paperId"),
    )
    user_id: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("user_id", "userId", "operator_id", "operatorId"),
        description="Defaults to authenticated user from JWT token if omitted",
    )
    day_type: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("day_type", "dayType", "paper_type", "paperType", "paperKey"),
        description="Auto-derived from question paper if omitted",
    )

    # Filled answers map (e.g. {"1": 0, "2": 2, ..., "14": "Maintenance keeps machines running"})
    answers: Union[Dict[str, Any], List[Dict[str, Any]]] = Field(default_factory=dict)

    # Header info filled on Day 1 / Day 2 sheet: {time, date, name, designation, qualification, unit}
    participant_info: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("participant_info", "participantInfo", "info"),
    )
    # Optional Step 2 Training Schedule data from UpcomingQuestionPapers workflow
    training_schedule: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("training_schedule", "trainingSchedule", "scheduleData"),
    )

    # Optional explicit evaluation metadata (auto-computed when paper has answer keys)
    score: Optional[Decimal] = None
    max_score: Optional[Decimal] = Field(
        None, validation_alias=AliasChoices("max_score", "maxScore")
    )
    percentage: Optional[Decimal] = None
    passed: Optional[bool] = None
    status: Optional[str] = None
    remarks: Optional[str] = Field(None, max_length=500)


class SubmissionGradeUpdate(BaseModel):
    """Supervisor evaluation & grading payload matching submissionGradingStorage.js & SubmittedPapersPanel.jsx."""

    model_config = ConfigDict(populate_by_name=True)

    question_marks: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("question_marks", "questionMarks"),
        description="Per-question marks map, e.g. {'1': 1, '2': 0.5}",
    )
    score: Optional[Decimal] = Field(
        None,
        validation_alias=AliasChoices("score", "total_marks_obtained", "totalMarksObtained"),
    )
    max_score: Optional[Decimal] = Field(
        None,
        validation_alias=AliasChoices("max_score", "maxScore", "max_marks", "maxMarks"),
    )
    percentage: Optional[Decimal] = None
    passed: Optional[bool] = None
    remarks: Optional[str] = Field(None, max_length=500)
    graded_by: Optional[int] = Field(None, validation_alias=AliasChoices("graded_by", "gradedById"))
    graded_by_name: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("graded_by_name", "gradedByName", "gradedBy"),
        max_length=150,
    )
    status: Optional[str] = Field(None, max_length=50)


class QuestionPaperSubmissionResponse(BaseModel):
    """Full submission response including supervisor grading for past papers & supervisor review."""

    id: int
    question_paper_id: int
    question_paper_title: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    user_pay_code: Optional[str] = None
    user_email: Optional[str] = None
    day_type: str

    plant_id: Optional[int] = None
    plant_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    sub_department_id: Optional[int] = None
    sub_department_name: Optional[str] = None
    line_id: Optional[int] = None
    line_name: Optional[str] = None
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None

    answers: Union[Dict[str, Any], List[Dict[str, Any]]]
    participant_info: Optional[Dict[str, Any]] = None
    training_schedule: Optional[Dict[str, Any]] = None

    answered_count: int = 0
    total_questions: int = 0
    score: Optional[Decimal] = None
    max_score: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    passed: Optional[bool] = None
    status: str = "SUBMITTED"
    remarks: Optional[str] = None

    # Supervisor evaluation & grading fields
    question_marks: Dict[str, Any] = Field(default_factory=dict)
    is_graded: bool = False
    evaluation_status: str = "Pending Review"
    graded_by: Optional[int] = None
    graded_by_name: Optional[str] = None
    graded_at: Optional[datetime] = None

    # Associated assignment metadata if this submission fulfilled a manual assignment
    assignment_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    assigned_by_name: Optional[str] = None

    submitted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QuestionPaperAssignmentCreate(BaseModel):
    """
    Supervisor assignment payload: assign one or multiple question papers
    to one or multiple selected operators.
    """

    model_config = ConfigDict(populate_by_name=True)

    question_paper_id: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("question_paper_id", "questionPaperId", "paper_id", "paperId"),
    )
    question_paper_ids: Optional[List[int]] = Field(
        None,
        validation_alias=AliasChoices("question_paper_ids", "questionPaperIds", "paper_ids", "paperIds"),
    )
    operator_id: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("operator_id", "operatorId", "user_id", "userId"),
    )
    operator_ids: Optional[List[int]] = Field(
        None,
        validation_alias=AliasChoices("operator_ids", "operatorIds", "user_ids", "userIds"),
    )
    assigned_by: Optional[int] = Field(
        None, validation_alias=AliasChoices("assigned_by", "assignedById")
    )
    assigned_by_name: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("assigned_by_name", "assignedByName", "assignedBy"),
        max_length=150,
    )
    due_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("due_at", "dueAt", "due_date", "dueDate")
    )
    notes: Optional[str] = Field(None, max_length=500)
    metadata: Optional[Dict[str, Any]] = None


class QuestionPaperAssignmentResponse(BaseModel):
    """Assignment record linking a question paper, an operator, and the assigning supervisor."""

    id: int
    question_paper_id: int
    question_paper_title: Optional[str] = None
    question_paper_description: Optional[str] = None
    day_type: str
    total_marks: Optional[int] = None
    total_questions: int = 0
    duration_minutes: Optional[int] = None
    pass_percentage: Optional[int] = None

    operator_id: int
    operator_name: Optional[str] = None
    operator_pay_code: Optional[str] = None
    operator_email: Optional[str] = None
    operator_designation: Optional[str] = None
    operator_department_name: Optional[str] = None
    operator_line_name: Optional[str] = None
    operator_machine_name: Optional[str] = None

    plant_id: Optional[int] = None
    plant_name: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    sub_department_id: Optional[int] = None
    sub_department_name: Optional[str] = None
    line_id: Optional[int] = None
    line_name: Optional[str] = None
    machine_id: Optional[int] = None
    machine_name: Optional[str] = None

    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None
    status: str = "ASSIGNED"
    submission_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class QuestionPaperAssignmentBulkResponse(BaseModel):
    """Result returned when a supervisor assigns paper(s) to operator(s)."""

    assigned_count: int
    reactivated_count: int = 0
    updated_count: int = 0
    assignments: List[QuestionPaperAssignmentResponse]


class OperatorUpcomingPaperResponse(BaseModel):
    """
    Single pending assigned paper returned by Operator Current/Upcoming Question Papers API.
    Includes assignment tracking fields plus the complete question paper details.
    """

    assignment_id: int
    status: str = "ASSIGNED"
    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    question_paper: QuestionPaperResponse
