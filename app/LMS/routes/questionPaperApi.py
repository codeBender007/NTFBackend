from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.LMS.models.userModel import User
from app.LMS.schemas.questionPaperSchema import (
    QuestionPaperCreate,
    QuestionPaperResponse,
    QuestionPaperSubmissionCreate,
    QuestionPaperSubmissionResponse,
    QuestionPaperUpdate,
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


# 3. Submit Filled Question Paper Response (registered BEFORE /{paper_id} to avoid path conflict)
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


# 4. List / Filter Submitted Question Paper Responses (for upcoming/past tracking & admin review)
@router.get("/submissions", response_model=List[QuestionPaperSubmissionResponse])
def getQuestionPaperSubmissions(
    user_id: Optional[int] = Query(None, description="Filter by submitting user ID"),
    userId: Optional[int] = Query(None, include_in_schema=False),
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return questionPaperService.list_submissions(
        db=db,
        user_id=user_id if user_id is not None else userId,
        question_paper_id=question_paper_id if question_paper_id is not None else questionPaperId,
        day_type=day_type if day_type is not None else dayType,
        plant_id=plant_id if plant_id is not None else plantId,
        department_id=department_id if department_id is not None else departmentId,
        sub_department_id=sub_department_id if sub_department_id is not None else subDepartmentId,
        line_id=line_id if line_id is not None else lineId,
        machine_id=machine_id if machine_id is not None else machineId,
        skip=skip,
        limit=limit,
    )


# 5. Get Single Submission by ID
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


# 6. Get Single Question Paper Details by ID
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


# 7. Submit Filled Response for a Specific Paper ID (convenience route)
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


# 8. Update Question Paper
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


# 9. Soft Delete / Deactivate Question Paper
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
