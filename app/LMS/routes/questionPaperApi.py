from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.LMS.models.userModel import User
from app.LMS.schemas.questionPaperSchema import (
    OperatorUpcomingPaperResponse,
    QuestionPaperAssignmentBulkResponse,
    QuestionPaperAssignmentCreate,
    QuestionPaperAssignmentResponse,
    QuestionPaperCreate,
    QuestionPaperResponse,
    QuestionPaperSubmissionCreate,
    QuestionPaperSubmissionResponse,
    QuestionPaperUpdate,
    SubmissionGradeUpdate,
)
from app.LMS.services import questionPaperService
from app.core.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter(
    prefix="/question-papers",
    tags=["LMS - Question Papers"],
)


# 1. Create Question Paper (Day 1, Day 2, or custom assessment)
@router.post(
    "/",
    response_model=QuestionPaperResponse,
    status_code=status.HTTP_201_CREATED,
)
def createQuestionPaper(
    paperData: QuestionPaperCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return questionPaperService.create_question_paper(
        db=db,
        payload=paperData,
        current_user=current_user,
    )


# 2. List / Filter Question Papers by hierarchy and day_type
@router.get("/", response_model=List[QuestionPaperResponse])
def getQuestionPapers(
    plant_id: Optional[int] = Query(None, description="Filter by plant ID"),
    plantId: Optional[int] = Query(None, include_in_schema=False),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    departmentId: Optional[int] = Query(None, include_in_schema=False),
    sub_department_id: Optional[int] = Query(None, description="Filter by sub-department ID"),
    subDepartmentId: Optional[int] = Query(None, include_in_schema=False),
    line_id: Optional[int] = Query(None, description="Filter by line ID"),
    lineId: Optional[int] = Query(None, include_in_schema=False),
    machine_id: Optional[int] = Query(None, description="Filter by machine ID"),
    machineId: Optional[int] = Query(None, include_in_schema=False),
    day_type: Optional[str] = Query(None, description="Filter by day_type (e.g. DAY_1, DAY_2)"),
    dayType: Optional[str] = Query(None, include_in_schema=False),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return questionPaperService.list_question_papers(
        db=db,
        plant_id=plant_id if plant_id is not None else plantId,
        department_id=department_id if department_id is not None else departmentId,
        sub_department_id=sub_department_id if sub_department_id is not None else subDepartmentId,
        line_id=line_id if line_id is not None else lineId,
        machine_id=machine_id if machine_id is not None else machineId,
        day_type=day_type if day_type is not None else dayType,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


# -------------------------------------------------------------------------
# Supervisor Manual Assignment Endpoints (registered BEFORE /{paper_id})
# -------------------------------------------------------------------------

# 3. Assign Question Paper(s) to Operator(s)
@router.post(
    "/assignments",
    response_model=QuestionPaperAssignmentBulkResponse,
    status_code=status.HTTP_201_CREATED,
)
def assignQuestionPapers(
    assignmentData: QuestionPaperAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return questionPaperService.assign_question_papers(
        db=db,
        payload=assignmentData,
        current_user=current_user,
    )


# 4. List / Filter Question Paper Assignments
@router.get("/assignments", response_model=List[QuestionPaperAssignmentResponse])
def getQuestionPaperAssignments(
    question_paper_id: Optional[int] = Query(None, description="Filter by question paper ID"),
    questionPaperId: Optional[int] = Query(None, include_in_schema=False),
    paper_id: Optional[int] = Query(None, include_in_schema=False),
    paperId: Optional[int] = Query(None, include_in_schema=False),
    operator_id: Optional[int] = Query(None, description="Filter by operator user ID"),
    operatorId: Optional[int] = Query(None, include_in_schema=False),
    user_id: Optional[int] = Query(None, include_in_schema=False),
    userId: Optional[int] = Query(None, include_in_schema=False),
    assigned_by: Optional[int] = Query(None, description="Filter by assigning supervisor user ID"),
    assignedBy: Optional[int] = Query(None, include_in_schema=False),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by assignment status (ASSIGNED, PENDING, COMPLETED)",
    ),
    day_type: Optional[str] = Query(None, description="Filter by day_type (e.g. DAY_1, DAY_2)"),
    dayType: Optional[str] = Query(None, include_in_schema=False),
    plant_id: Optional[int] = Query(None, description="Filter by plant ID"),
    plantId: Optional[int] = Query(None, include_in_schema=False),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    departmentId: Optional[int] = Query(None, include_in_schema=False),
    sub_department_id: Optional[int] = Query(None, description="Filter by sub-department ID"),
    subDepartmentId: Optional[int] = Query(None, include_in_schema=False),
    line_id: Optional[int] = Query(None, description="Filter by line ID"),
    lineId: Optional[int] = Query(None, include_in_schema=False),
    machine_id: Optional[int] = Query(None, description="Filter by machine ID"),
    machineId: Optional[int] = Query(None, include_in_schema=False),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    resolved_paper_id = next(
        (v for v in (question_paper_id, questionPaperId, paper_id, paperId) if v is not None),
        None,
    )
    resolved_operator_id = next(
        (v for v in (operator_id, operatorId, user_id, userId) if v is not None),
        None,
    )
    return questionPaperService.list_assignments(
        db=db,
        question_paper_id=resolved_paper_id,
        operator_id=resolved_operator_id,
        assigned_by=assigned_by if assigned_by is not None else assignedBy,
        status_filter=status_filter,
        day_type=day_type if day_type is not None else dayType,
        plant_id=plant_id if plant_id is not None else plantId,
        department_id=department_id if department_id is not None else departmentId,
        sub_department_id=sub_department_id if sub_department_id is not None else subDepartmentId,
        line_id=line_id if line_id is not None else lineId,
        machine_id=machine_id if machine_id is not None else machineId,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


# 5. Unassign / Deactivate an Assignment
@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_200_OK)
def unassignQuestionPaper(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    removed = questionPaperService.unassign_question_paper(db, assignment_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper assignment not found",
        )
    return {"message": "Question paper assignment removed successfully"}


# -------------------------------------------------------------------------
# Operator Current / Upcoming & Past Question Papers Endpoints
# -------------------------------------------------------------------------

# 6. Operator Upcoming / Current Assigned Papers (ONLY assigned & not yet submitted)
@router.get("/operator/upcoming", response_model=List[OperatorUpcomingPaperResponse])
@router.get("/my/upcoming", response_model=List[OperatorUpcomingPaperResponse], include_in_schema=False)
def getOperatorUpcomingPapers(
    operator_id: Optional[int] = Query(None, description="Defaults to logged-in operator ID"),
    operatorId: Optional[int] = Query(None, include_in_schema=False),
    day_type: Optional[str] = Query(None, description="Optional day_type filter (e.g. DAY_1, DAY_2)"),
    dayType: Optional[str] = Query(None, include_in_schema=False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_operator_id = (
        operator_id
        if operator_id is not None
        else (operatorId if operatorId is not None else current_user.id)
    )
    return questionPaperService.get_operator_upcoming_papers(
        db=db,
        operator_id=target_operator_id,
        day_type=day_type if day_type is not None else dayType,
        skip=skip,
        limit=limit,
    )


# 7. Operator Past / Submitted Papers (ONLY already attempted/submitted, with grading & remarks)
@router.get("/operator/past", response_model=List[QuestionPaperSubmissionResponse])
@router.get("/my/past", response_model=List[QuestionPaperSubmissionResponse], include_in_schema=False)
def getOperatorPastPapers(
    operator_id: Optional[int] = Query(None, description="Defaults to logged-in operator ID"),
    operatorId: Optional[int] = Query(None, include_in_schema=False),
    day_type: Optional[str] = Query(None, description="Optional day_type filter (e.g. DAY_1, DAY_2)"),
    dayType: Optional[str] = Query(None, include_in_schema=False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_operator_id = (
        operator_id
        if operator_id is not None
        else (operatorId if operatorId is not None else current_user.id)
    )
    return questionPaperService.get_operator_past_papers(
        db=db,
        operator_id=target_operator_id,
        day_type=day_type if day_type is not None else dayType,
        skip=skip,
        limit=limit,
    )


# -------------------------------------------------------------------------
# Submission & Supervisor Grading Endpoints (registered BEFORE /{paper_id})
# -------------------------------------------------------------------------

# 8. Submit Filled Question Paper Response (auto-completes matching operator assignment)
@router.post(
    "/submissions",
    response_model=QuestionPaperSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submitQuestionPaper(
    submissionData: QuestionPaperSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return questionPaperService.submit_question_paper(
        db=db,
        payload=submissionData,
        current_user=current_user,
    )


# 9. List / Filter Submitted Question Paper Responses (for Supervisor review & Past papers)
@router.get("/submissions", response_model=List[QuestionPaperSubmissionResponse])
def getQuestionPaperSubmissions(
    user_id: Optional[int] = Query(None, description="Filter by submitting operator/user ID"),
    userId: Optional[int] = Query(None, include_in_schema=False),
    operator_id: Optional[int] = Query(None, include_in_schema=False),
    operatorId: Optional[int] = Query(None, include_in_schema=False),
    question_paper_id: Optional[int] = Query(None, description="Filter by question paper ID"),
    questionPaperId: Optional[int] = Query(None, include_in_schema=False),
    day_type: Optional[str] = Query(None, description="Filter by day_type (e.g. DAY_1, DAY_2)"),
    dayType: Optional[str] = Query(None, include_in_schema=False),
    plant_id: Optional[int] = Query(None, description="Filter by plant ID"),
    plantId: Optional[int] = Query(None, include_in_schema=False),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    departmentId: Optional[int] = Query(None, include_in_schema=False),
    sub_department_id: Optional[int] = Query(None, description="Filter by sub-department ID"),
    subDepartmentId: Optional[int] = Query(None, include_in_schema=False),
    line_id: Optional[int] = Query(None, description="Filter by line ID"),
    lineId: Optional[int] = Query(None, include_in_schema=False),
    machine_id: Optional[int] = Query(None, description="Filter by machine ID"),
    machineId: Optional[int] = Query(None, include_in_schema=False),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by evaluation/submission status (PENDING, GRADED, SUBMITTED, PASSED, FAILED)",
    ),
    is_graded: Optional[bool] = Query(None, description="Filter by whether supervisor has graded submission"),
    isGraded: Optional[bool] = Query(None, include_in_schema=False),
    search: Optional[str] = Query(None, description="Search by operator name, payCode, or paper title"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    resolved_user_id = next(
        (v for v in (user_id, userId, operator_id, operatorId) if v is not None),
        None,
    )
    return questionPaperService.list_submissions(
        db=db,
        user_id=resolved_user_id,
        question_paper_id=question_paper_id if question_paper_id is not None else questionPaperId,
        day_type=day_type if day_type is not None else dayType,
        plant_id=plant_id if plant_id is not None else plantId,
        department_id=department_id if department_id is not None else departmentId,
        sub_department_id=sub_department_id if sub_department_id is not None else subDepartmentId,
        line_id=line_id if line_id is not None else lineId,
        machine_id=machine_id if machine_id is not None else machineId,
        status_filter=status_filter,
        is_graded=is_graded if is_graded is not None else isGraded,
        search=search,
        skip=skip,
        limit=limit,
    )


# 10. Get Single Submission by ID
@router.get("/submissions/{submission_id}", response_model=QuestionPaperSubmissionResponse)
def getQuestionPaperSubmission(
    submission_id: int,
    db: Session = Depends(get_db),
):
    submission = questionPaperService.get_submission_by_id(db, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper submission not found",
        )
    return submission


# 11. Supervisor Grade / Evaluate a Submission
@router.put("/submissions/{submission_id}/grade", response_model=QuestionPaperSubmissionResponse)
@router.post(
    "/submissions/{submission_id}/grade",
    response_model=QuestionPaperSubmissionResponse,
    include_in_schema=False,
)
def gradeQuestionPaperSubmission(
    submission_id: int,
    gradeData: SubmissionGradeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    graded = questionPaperService.grade_submission(
        db=db,
        submission_id=submission_id,
        payload=gradeData,
        current_user=current_user,
    )
    if not graded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper submission not found",
        )
    return graded


# 12. Get Single Question Paper Details by ID
@router.get("/{paper_id}", response_model=QuestionPaperResponse)
def getQuestionPaper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    paper = questionPaperService.get_question_paper_by_id(db, paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper not found",
        )
    return paper


# 13. Submit Filled Response for a Specific Paper ID (convenience route)
@router.post(
    "/{paper_id}/submit",
    response_model=QuestionPaperSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submitQuestionPaperById(
    paper_id: int,
    submissionData: QuestionPaperSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return questionPaperService.submit_question_paper(
        db=db,
        payload=submissionData,
        current_user=current_user,
        path_paper_id=paper_id,
    )


# 14. Update Question Paper
@router.put("/{paper_id}", response_model=QuestionPaperResponse)
def updateQuestionPaper(
    paper_id: int,
    paperData: QuestionPaperUpdate,
    db: Session = Depends(get_db),
):
    paper = questionPaperService.update_question_paper(db, paper_id, paperData)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper not found",
        )
    return paper


# 15. Soft Delete / Deactivate Question Paper
@router.delete("/{paper_id}", status_code=status.HTTP_200_OK)
def deleteQuestionPaper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    deleted = questionPaperService.delete_question_paper(db, paper_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper not found",
        )
    return {"message": "Question paper deactivated successfully"}
