import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.LMS.models.departmentsModel import Department
from app.LMS.models.linesModel import Line
from app.LMS.models.machineModel import Machine
from app.LMS.models.plantsModel import Plant
from app.LMS.models.questionPaperModel import (
    QuestionPaper,
    QuestionPaperAssignment,
    QuestionPaperSubmission,
)
from app.LMS.models.subDepartmentsModel import SubDepartment
from app.LMS.models.userModel import User
from app.LMS.schemas.questionPaperSchema import (
    QuestionPaperAssignmentCreate,
    QuestionPaperCreate,
    QuestionPaperSubmissionCreate,
    QuestionPaperUpdate,
    SubmissionGradeUpdate,
)


def normalize_day_type(raw: Optional[str]) -> Optional[str]:
    """Normalize paper/day type variants (e.g. 'day1', 'Day 1', 'DAY-1' -> 'DAY_1')."""
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    compact = re.sub(r"[\s\-_]+", "", cleaned).upper()
    if compact in {"DAY1", "1"}:
        return "DAY_1"
    if compact in {"DAY2", "2"}:
        return "DAY_2"
    day_match = re.fullmatch(r"DAY(\d+)", compact)
    if day_match:
        return f"DAY_{day_match.group(1)}"
    return re.sub(r"[\s\-]+", "_", cleaned).upper()


def _to_json(data: Any) -> Optional[str]:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False)


def _from_json(raw: Optional[str], default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def _extract_flat_questions(questions: Any, sections: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Extract normalized (question_key, question_dict) pairs across all supported frontend formats:
    1. Day 1 grouped object: { general: [{q, options}, ...], safety: [...], ... }
    2. Day 2 numbered object: { "1": {q, options}, "2": {q, options}, ... }
    3. Flat list of questions: [ {number/id, q/question, options}, ... ]
    4. Sections array (Editor/L0/L1): [ {id, name, questions: [{id, question, options, ...}]} ]
    """
    items: List[Tuple[str, Dict[str, Any]]] = []

    if isinstance(questions, list):
        for idx, q in enumerate(questions, start=1):
            if isinstance(q, dict):
                key = str(q.get("number") or q.get("id") or idx)
                items.append((key, q))
        return items

    if isinstance(questions, dict):
        # Day 2 numbered format: keys are numeric strings and values are question dicts
        if questions and all(isinstance(v, dict) for v in questions.values()):
            def _sort_key(pair):
                k = str(pair[0])
                return (0, int(k)) if k.isdigit() else (1, k)

            for k, v in sorted(questions.items(), key=_sort_key):
                items.append((str(k), v))
            return items

        # Day 1 grouped format: keys are section names and values are lists of question dicts
        counter = 1
        for group_val in questions.values():
            if isinstance(group_val, list):
                for q in group_val:
                    if isinstance(q, dict):
                        key = str(q.get("number") or q.get("id") or counter)
                        items.append((key, q))
                        counter += 1
        if items:
            return items

    if isinstance(sections, list):
        counter = 1
        for sec in sections:
            if isinstance(sec, dict) and isinstance(sec.get("questions"), list):
                for q in sec["questions"]:
                    if isinstance(q, dict):
                        key = str(q.get("number") or q.get("id") or counter)
                        items.append((key, q))
                        counter += 1

    return items


def _count_questions(questions: Any, sections: Any) -> int:
    return len(_extract_flat_questions(questions, sections))


def _resolve_and_validate_hierarchy(
    db: Session,
    plant_id: Optional[int],
    department_id: Optional[int],
    sub_department_id: Optional[int],
    line_id: Optional[int],
    machine_id: Optional[int],
) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Validate provided hierarchy IDs, enforce parent-child consistency, and auto-infer missing parents."""
    machine = None
    line = None
    sub_dept = None
    dept = None
    plant = None

    if machine_id is not None:
        machine = db.query(Machine).filter(Machine.id == machine_id).first()
        if not machine:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Machine with id {machine_id} does not exist",
            )
        if line_id is not None and line_id != machine.lineId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Machine {machine_id} belongs to Line {machine.lineId}, not Line {line_id}",
            )
        if sub_department_id is not None and sub_department_id != machine.subDepartmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Machine {machine_id} belongs to SubDepartment {machine.subDepartmentId}, "
                    f"not SubDepartment {sub_department_id}"
                ),
            )
        if department_id is not None and department_id != machine.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Machine {machine_id} belongs to Department {machine.departmentId}, "
                    f"not Department {department_id}"
                ),
            )
        if plant_id is not None and plant_id != machine.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Machine {machine_id} belongs to Plant {machine.plantId}, not Plant {plant_id}",
            )
        line_id = machine.lineId
        sub_department_id = machine.subDepartmentId
        department_id = machine.departmentId
        plant_id = machine.plantId

    if line_id is not None:
        line = db.query(Line).filter(Line.id == line_id).first()
        if not line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line with id {line_id} does not exist",
            )
        if sub_department_id is not None and sub_department_id != line.subDepartmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Line {line_id} belongs to SubDepartment {line.subDepartmentId}, "
                    f"not SubDepartment {sub_department_id}"
                ),
            )
        if department_id is not None and department_id != line.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Line {line_id} belongs to Department {line.departmentId}, "
                    f"not Department {department_id}"
                ),
            )
        if plant_id is not None and plant_id != line.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Line {line_id} belongs to Plant {line.plantId}, not Plant {plant_id}",
            )
        sub_department_id = line.subDepartmentId
        department_id = line.departmentId
        plant_id = line.plantId

    if sub_department_id is not None:
        sub_dept = db.query(SubDepartment).filter(SubDepartment.id == sub_department_id).first()
        if not sub_dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"SubDepartment with id {sub_department_id} does not exist",
            )
        if department_id is not None and department_id != sub_dept.departmentId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"SubDepartment {sub_department_id} belongs to Department {sub_dept.departmentId}, "
                    f"not Department {department_id}"
                ),
            )
        if plant_id is not None and plant_id != sub_dept.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"SubDepartment {sub_department_id} belongs to Plant {sub_dept.plantId}, "
                    f"not Plant {plant_id}"
                ),
            )
        department_id = sub_dept.departmentId
        plant_id = sub_dept.plantId

    if department_id is not None:
        dept = db.query(Department).filter(Department.id == department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {department_id} does not exist",
            )
        if plant_id is not None and plant_id != dept.plantId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department {department_id} belongs to Plant {dept.plantId}, not Plant {plant_id}",
            )
        plant_id = dept.plantId

    if plant_id is not None:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plant with id {plant_id} does not exist",
            )

    return plant_id, department_id, sub_department_id, line_id, machine_id


def _serialize_paper(paper: QuestionPaper) -> Dict[str, Any]:
    return {
        "id": paper.id,
        "title": paper.title,
        "description": paper.description,
        "day_type": paper.day_type,
        "document_code": paper.document_code,
        "revision": paper.revision,
        "duration_minutes": paper.duration_minutes,
        "duration_label": paper.duration_label,
        "total_marks": paper.total_marks,
        "pass_percentage": paper.pass_percentage,
        "total_questions": paper.total_questions,
        "passing_instruction": paper.passing_instruction,
        "plant_id": paper.plant_id,
        "plant_name": paper.plant.plantName if paper.plant else None,
        "department_id": paper.department_id,
        "department_name": paper.department.departmentName if paper.department else None,
        "sub_department_id": paper.sub_department_id,
        "sub_department_name": paper.sub_department.subDepartmentName if paper.sub_department else None,
        "line_id": paper.line_id,
        "line_name": paper.line.lineName if paper.line else None,
        "machine_id": paper.machine_id,
        "machine_name": paper.machine.machineName if paper.machine else None,
        "sections": _from_json(paper.sections_json, None),
        "questions": _from_json(paper.questions_json, {}),
        "metadata": _from_json(paper.metadata_json, None),
        "is_active": bool(paper.is_active),
        "created_by": paper.created_by,
        "created_by_name": paper.creator.empName if paper.creator else None,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at,
    }


def _serialize_submission(
    sub: QuestionPaperSubmission,
    assignment: Optional[QuestionPaperAssignment] = None,
) -> Dict[str, Any]:
    return {
        "id": sub.id,
        "question_paper_id": sub.question_paper_id,
        "question_paper_title": sub.question_paper.title if sub.question_paper else None,
        "user_id": sub.user_id,
        "user_name": sub.user.empName if sub.user else None,
        "user_pay_code": sub.user.payCode if sub.user else None,
        "user_email": sub.user.email if sub.user else None,
        "day_type": sub.day_type,
        "plant_id": sub.plant_id,
        "plant_name": sub.plant.plantName if sub.plant else None,
        "department_id": sub.department_id,
        "department_name": sub.department.departmentName if sub.department else None,
        "sub_department_id": sub.sub_department_id,
        "sub_department_name": sub.sub_department.subDepartmentName if sub.sub_department else None,
        "line_id": sub.line_id,
        "line_name": sub.line.lineName if sub.line else None,
        "machine_id": sub.machine_id,
        "machine_name": sub.machine.machineName if sub.machine else None,
        "answers": _from_json(sub.answers_json, {}),
        "participant_info": _from_json(sub.participant_info_json, None),
        "training_schedule": _from_json(sub.training_schedule_json, None),
        "answered_count": sub.answered_count,
        "total_questions": sub.total_questions,
        "score": sub.score,
        "max_score": sub.max_score,
        "percentage": sub.percentage,
        "passed": sub.passed,
        "status": sub.status,
        "remarks": sub.remarks,
        "question_marks": _from_json(sub.question_marks_json, {}),
        "is_graded": bool(sub.is_graded),
        "evaluation_status": sub.evaluation_status or ("Graded" if sub.is_graded else "Pending Review"),
        "graded_by": sub.graded_by,
        "graded_by_name": sub.graded_by_name or (sub.grader.empName if sub.grader else None),
        "graded_at": sub.graded_at,
        "assignment_id": assignment.id if assignment else None,
        "assigned_at": assignment.assigned_at if assignment else None,
        "assigned_by_name": (
            assignment.assigned_by_name or (assignment.assigner.empName if assignment.assigner else None)
            if assignment
            else None
        ),
        "submitted_at": sub.submitted_at,
        "updated_at": sub.updated_at,
    }


def _serialize_assignment(asgn: QuestionPaperAssignment) -> Dict[str, Any]:
    paper = asgn.question_paper
    op = asgn.operator
    assigner = asgn.assigner

    plant_id = paper.plant_id if (paper and paper.plant_id is not None) else (op.plantId if op else None)
    plant_name = (
        paper.plant.plantName
        if (paper and paper.plant)
        else (op.plantLocation if op else None)
    )
    department_id = (
        paper.department_id
        if (paper and paper.department_id is not None)
        else (op.departmentId if op else None)
    )
    department_name = (
        paper.department.departmentName
        if (paper and paper.department)
        else (op.departmentName if op else None)
    )
    sub_department_id = (
        paper.sub_department_id
        if (paper and paper.sub_department_id is not None)
        else (op.subDepartmentId if op else None)
    )
    sub_department_name = (
        paper.sub_department.subDepartmentName
        if (paper and paper.sub_department)
        else (op.subDepartmentName if op else None)
    )
    line_id = paper.line_id if (paper and paper.line_id is not None) else (op.lineId if op else None)
    line_name = (
        paper.line.lineName
        if (paper and paper.line)
        else (op.lineName if op else None)
    )
    machine_id = (
        paper.machine_id
        if (paper and paper.machine_id is not None)
        else (op.machineId if op else None)
    )
    machine_name = (
        paper.machine.machineName
        if (paper and paper.machine)
        else (op.machineName if op else None)
    )

    return {
        "id": asgn.id,
        "question_paper_id": asgn.question_paper_id,
        "question_paper_title": paper.title if paper else None,
        "question_paper_description": paper.description if paper else None,
        "day_type": asgn.day_type,
        "total_marks": paper.total_marks if paper else None,
        "total_questions": paper.total_questions if paper else 0,
        "duration_minutes": paper.duration_minutes if paper else None,
        "pass_percentage": paper.pass_percentage if paper else None,
        "operator_id": asgn.operator_id,
        "operator_name": op.empName if op else None,
        "operator_pay_code": op.payCode if op else None,
        "operator_email": op.email if op else None,
        "operator_designation": op.designation if op else None,
        "operator_department_name": op.departmentName if op else None,
        "operator_line_name": op.lineName if op else None,
        "operator_machine_name": op.machineName if op else None,
        "plant_id": plant_id,
        "plant_name": plant_name,
        "department_id": department_id,
        "department_name": department_name,
        "sub_department_id": sub_department_id,
        "sub_department_name": sub_department_name,
        "line_id": line_id,
        "line_name": line_name,
        "machine_id": machine_id,
        "machine_name": machine_name,
        "assigned_by": asgn.assigned_by,
        "assigned_by_name": asgn.assigned_by_name or (assigner.empName if assigner else None),
        "status": asgn.status,
        "submission_id": asgn.submission_id,
        "assigned_at": asgn.assigned_at,
        "due_at": asgn.due_at,
        "completed_at": asgn.completed_at,
        "notes": asgn.notes,
        "metadata": _from_json(asgn.metadata_json, None),
        "is_active": bool(asgn.is_active),
    }


def _paper_query_with_relations(db: Session):
    return db.query(QuestionPaper).options(
        joinedload(QuestionPaper.plant),
        joinedload(QuestionPaper.department),
        joinedload(QuestionPaper.sub_department),
        joinedload(QuestionPaper.line),
        joinedload(QuestionPaper.machine),
        joinedload(QuestionPaper.creator),
    )


def _submission_query_with_relations(db: Session):
    return db.query(QuestionPaperSubmission).options(
        joinedload(QuestionPaperSubmission.question_paper),
        joinedload(QuestionPaperSubmission.user),
        joinedload(QuestionPaperSubmission.grader),
        joinedload(QuestionPaperSubmission.plant),
        joinedload(QuestionPaperSubmission.department),
        joinedload(QuestionPaperSubmission.sub_department),
        joinedload(QuestionPaperSubmission.line),
        joinedload(QuestionPaperSubmission.machine),
    )


def _assignment_query_with_relations(db: Session):
    return db.query(QuestionPaperAssignment).options(
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.plant),
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.department),
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.sub_department),
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.line),
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.machine),
        joinedload(QuestionPaperAssignment.question_paper).joinedload(QuestionPaper.creator),
        joinedload(QuestionPaperAssignment.operator),
        joinedload(QuestionPaperAssignment.assigner),
    )


def create_question_paper(
    db: Session,
    payload: QuestionPaperCreate,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    normalized_day_type = normalize_day_type(payload.day_type)
    if not normalized_day_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="day_type is required (e.g. DAY_1, DAY_2)",
        )

    if payload.questions is None and payload.sections is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either questions or sections payload must be provided",
        )

    plant_id, dept_id, sub_dept_id, line_id, machine_id = _resolve_and_validate_hierarchy(
        db=db,
        plant_id=payload.plant_id,
        department_id=payload.department_id,
        sub_department_id=payload.sub_department_id,
        line_id=payload.line_id,
        machine_id=payload.machine_id,
    )

    questions_payload = payload.questions if payload.questions is not None else payload.sections
    inferred_count = _count_questions(payload.questions, payload.sections)
    total_questions = payload.total_questions if payload.total_questions is not None else inferred_count

    created_by = payload.created_by
    if created_by is None and current_user is not None:
        created_by = current_user.id
    elif created_by is not None:
        creator = db.query(User).filter(User.id == created_by).first()
        if not creator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Creator user with id {created_by} does not exist",
            )

    paper = QuestionPaper(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        day_type=normalized_day_type,
        document_code=payload.document_code.strip() if payload.document_code else None,
        revision=payload.revision.strip() if payload.revision else None,
        duration_minutes=payload.duration_minutes,
        duration_label=payload.duration_label.strip() if payload.duration_label else None,
        total_marks=payload.total_marks,
        pass_percentage=payload.pass_percentage,
        total_questions=total_questions,
        passing_instruction=payload.passing_instruction.strip() if payload.passing_instruction else None,
        plant_id=plant_id,
        department_id=dept_id,
        sub_department_id=sub_dept_id,
        line_id=line_id,
        machine_id=machine_id,
        sections_json=_to_json(payload.sections),
        questions_json=_to_json(questions_payload),
        metadata_json=_to_json(payload.metadata),
        is_active=True if payload.is_active is None else bool(payload.is_active),
        created_by=created_by,
    )

    try:
        db.add(paper)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save question paper due to invalid foreign key reference",
        ) from exc

    loaded = _paper_query_with_relations(db).filter(QuestionPaper.id == paper.id).first()
    return _serialize_paper(loaded)


def list_question_papers(
    db: Session,
    plant_id: Optional[int] = None,
    department_id: Optional[int] = None,
    sub_department_id: Optional[int] = None,
    line_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    day_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    query = _paper_query_with_relations(db)

    if plant_id is not None:
        query = query.filter(QuestionPaper.plant_id == plant_id)
    if department_id is not None:
        query = query.filter(QuestionPaper.department_id == department_id)
    if sub_department_id is not None:
        query = query.filter(QuestionPaper.sub_department_id == sub_department_id)
    if line_id is not None:
        query = query.filter(QuestionPaper.line_id == line_id)
    if machine_id is not None:
        query = query.filter(QuestionPaper.machine_id == machine_id)
    if day_type is not None and day_type.strip():
        query = query.filter(QuestionPaper.day_type == normalize_day_type(day_type))
    if is_active is not None:
        query = query.filter(QuestionPaper.is_active == is_active)

    papers = (
        query.order_by(QuestionPaper.id.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 1000))
        .all()
    )
    return [_serialize_paper(p) for p in papers]


def get_question_paper_by_id(db: Session, paper_id: int) -> Optional[Dict[str, Any]]:
    paper = _paper_query_with_relations(db).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        return None
    return _serialize_paper(paper)


def update_question_paper(
    db: Session,
    paper_id: int,
    payload: QuestionPaperUpdate,
) -> Optional[Dict[str, Any]]:
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        return None

    updates = payload.model_dump(exclude_unset=True)

    # Validate & align hierarchy if any hierarchy ID was included in the update
    hierarchy_keys = ("plant_id", "department_id", "sub_department_id", "line_id", "machine_id")
    if any(k in updates for k in hierarchy_keys):
        p_id, d_id, sd_id, l_id, m_id = _resolve_and_validate_hierarchy(
            db=db,
            plant_id=updates.get("plant_id", paper.plant_id),
            department_id=updates.get("department_id", paper.department_id),
            sub_department_id=updates.get("sub_department_id", paper.sub_department_id),
            line_id=updates.get("line_id", paper.line_id),
            machine_id=updates.get("machine_id", paper.machine_id),
        )
        paper.plant_id = p_id
        paper.department_id = d_id
        paper.sub_department_id = sd_id
        paper.line_id = l_id
        paper.machine_id = m_id

    if "title" in updates and updates["title"] is not None:
        paper.title = updates["title"].strip()
    if "description" in updates:
        paper.description = updates["description"].strip() if updates["description"] else None
    if "day_type" in updates and updates["day_type"] is not None:
        paper.day_type = normalize_day_type(updates["day_type"])
    if "document_code" in updates:
        paper.document_code = updates["document_code"].strip() if updates["document_code"] else None
    if "revision" in updates:
        paper.revision = updates["revision"].strip() if updates["revision"] else None
    if "duration_minutes" in updates:
        paper.duration_minutes = updates["duration_minutes"]
    if "duration_label" in updates:
        paper.duration_label = updates["duration_label"].strip() if updates["duration_label"] else None
    if "total_marks" in updates:
        paper.total_marks = updates["total_marks"]
    if "pass_percentage" in updates:
        paper.pass_percentage = updates["pass_percentage"]
    if "passing_instruction" in updates:
        paper.passing_instruction = (
            updates["passing_instruction"].strip() if updates["passing_instruction"] else None
        )
    if "is_active" in updates and updates["is_active"] is not None:
        paper.is_active = bool(updates["is_active"])

    questions_changed = False
    if "sections" in updates:
        paper.sections_json = _to_json(updates["sections"])
        questions_changed = True
    if "questions" in updates and updates["questions"] is not None:
        paper.questions_json = _to_json(updates["questions"])
        questions_changed = True
    if "metadata" in updates:
        paper.metadata_json = _to_json(updates["metadata"])

    if "total_questions" in updates and updates["total_questions"] is not None:
        paper.total_questions = updates["total_questions"]
    elif questions_changed:
        paper.total_questions = _count_questions(
            _from_json(paper.questions_json, None),
            _from_json(paper.sections_json, None),
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update question paper due to invalid reference",
        ) from exc

    loaded = _paper_query_with_relations(db).filter(QuestionPaper.id == paper.id).first()
    return _serialize_paper(loaded)


def delete_question_paper(db: Session, paper_id: int) -> bool:
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        return False
    paper.is_active = False
    db.commit()
    return True


def _count_answered(answers: Any) -> int:
    if isinstance(answers, dict):
        return sum(
            1
            for v in answers.values()
            if v is not None and not (isinstance(v, str) and not v.strip())
        )
    if isinstance(answers, list):
        return sum(
            1
            for item in answers
            if isinstance(item, dict)
            and item.get("answer") is not None
            and not (isinstance(item.get("answer"), str) and not item.get("answer").strip())
        )
    return 0


def _auto_evaluate_submission(
    paper: QuestionPaper,
    answers: Any,
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal], Optional[bool], str]:
    """
    Auto-score submission when the question paper includes answer keys
    (correctOption / correct_option / correctAnswer / correct_answer).
    """
    questions_list = _extract_flat_questions(
        _from_json(paper.questions_json, None),
        _from_json(paper.sections_json, None),
    )
    if not questions_list or not isinstance(answers, dict):
        return None, None, None, None, "SUBMITTED"

    gradable_count = 0
    earned = Decimal("0")
    possible = Decimal("0")

    for q_key, q_obj in questions_list:
        correct_key = None
        for candidate in ("correctOption", "correct_option", "correctAnswer", "correct_answer"):
            if q_obj.get(candidate) is not None:
                correct_key = q_obj[candidate]
                break
        if correct_key is None:
            continue

        gradable_count += 1
        q_marks = Decimal(str(q_obj.get("marks", 1)))
        possible += q_marks

        submitted_val = answers.get(q_key)
        if submitted_val is None and q_key.isdigit():
            submitted_val = answers.get(int(q_key))
        if submitted_val is None:
            continue

        if str(submitted_val).strip().lower() == str(correct_key).strip().lower():
            earned += q_marks

    if gradable_count == 0 or possible <= 0:
        return None, None, None, None, "SUBMITTED"

    score = earned.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    max_score = possible.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pct = ((earned / possible) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pass_threshold = Decimal(str(paper.pass_percentage if paper.pass_percentage is not None else 80))
    passed = pct >= pass_threshold
    eval_status = "PASSED" if passed else "FAILED"
    return score, max_score, pct, passed, eval_status


def submit_question_paper(
    db: Session,
    payload: QuestionPaperSubmissionCreate,
    current_user: Optional[User] = None,
    path_paper_id: Optional[int] = None,
) -> Dict[str, Any]:
    target_paper_id = path_paper_id if path_paper_id is not None else payload.question_paper_id
    if target_paper_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_paper_id is required",
        )

    paper = db.query(QuestionPaper).filter(QuestionPaper.id == target_paper_id).first()
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question paper with id {target_paper_id} not found",
        )

    # Resolve submitting user_id from authenticated JWT user or validated payload user_id
    target_user_id = payload.user_id if payload.user_id is not None else (current_user.id if current_user else None)
    if target_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id could not be determined from authentication token or request body",
        )

    submitting_user = db.query(User).filter(User.id == target_user_id).first()
    if not submitting_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {target_user_id} does not exist",
        )

    resolved_day_type = normalize_day_type(payload.day_type) if payload.day_type else paper.day_type
    answered_count = _count_answered(payload.answers)
    total_questions = paper.total_questions or _count_questions(
        _from_json(paper.questions_json, None),
        _from_json(paper.sections_json, None),
    )

    auto_score, auto_max, auto_pct, auto_passed, auto_status = _auto_evaluate_submission(
        paper, payload.answers
    )

    final_score = payload.score if payload.score is not None else auto_score
    final_max = payload.max_score if payload.max_score is not None else (
        auto_max if auto_max is not None else (Decimal(str(paper.total_marks)) if paper.total_marks is not None else None)
    )
    final_pct = payload.percentage if payload.percentage is not None else auto_pct
    if final_pct is None and final_score is not None and final_max is not None and final_max > 0:
        final_pct = ((Decimal(str(final_score)) / Decimal(str(final_max))) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    final_passed = payload.passed if payload.passed is not None else auto_passed
    if final_passed is None and final_pct is not None and paper.pass_percentage is not None:
        final_passed = final_pct >= Decimal(str(paper.pass_percentage))
    final_status = (payload.status.strip().upper() if payload.status else None) or (
        "PASSED" if final_passed is True else ("FAILED" if final_passed is False else auto_status)
    )

    # Resolve hierarchy snapshot: prefer paper's hierarchy, fall back to submitting user's hierarchy
    plant_id = paper.plant_id if paper.plant_id is not None else submitting_user.plantId
    department_id = paper.department_id if paper.department_id is not None else submitting_user.departmentId
    sub_department_id = (
        paper.sub_department_id if paper.sub_department_id is not None else submitting_user.subDepartmentId
    )
    line_id = paper.line_id if paper.line_id is not None else submitting_user.lineId
    machine_id = paper.machine_id if paper.machine_id is not None else submitting_user.machineId

    submission = QuestionPaperSubmission(
        question_paper_id=paper.id,
        user_id=submitting_user.id,
        day_type=resolved_day_type,
        plant_id=plant_id,
        department_id=department_id,
        sub_department_id=sub_department_id,
        line_id=line_id,
        machine_id=machine_id,
        answers_json=_to_json(payload.answers),
        participant_info_json=_to_json(payload.participant_info),
        training_schedule_json=_to_json(payload.training_schedule),
        answered_count=answered_count,
        total_questions=total_questions,
        score=final_score,
        max_score=final_max,
        percentage=final_pct,
        passed=final_passed,
        status=final_status,
        remarks=payload.remarks.strip() if payload.remarks else None,
    )

    try:
        db.add(submission)
        db.flush()

        # Atomically mark any active pending manual assignments for this operator + paper as COMPLETED
        pending_assignments = (
            db.query(QuestionPaperAssignment)
            .filter(
                QuestionPaperAssignment.question_paper_id == paper.id,
                QuestionPaperAssignment.operator_id == submitting_user.id,
                QuestionPaperAssignment.is_active == True,  # noqa: E712
                QuestionPaperAssignment.status.in_(["ASSIGNED", "PENDING"]),
            )
            .all()
        )
        now_utc = datetime.utcnow()
        for pending_asgn in pending_assignments:
            pending_asgn.status = "COMPLETED"
            pending_asgn.submission_id = submission.id
            pending_asgn.completed_at = now_utc

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save submission due to invalid reference",
        ) from exc

    loaded = (
        _submission_query_with_relations(db)
        .filter(QuestionPaperSubmission.id == submission.id)
        .first()
    )
    linked_assignment = (
        db.query(QuestionPaperAssignment)
        .options(joinedload(QuestionPaperAssignment.assigner))
        .filter(QuestionPaperAssignment.submission_id == submission.id)
        .order_by(QuestionPaperAssignment.id.desc())
        .first()
    )
    return _serialize_submission(loaded, linked_assignment)


def _load_assignments_by_submission_ids(
    db: Session,
    submission_ids: List[int],
) -> Dict[int, QuestionPaperAssignment]:
    if not submission_ids:
        return {}
    rows = (
        db.query(QuestionPaperAssignment)
        .options(joinedload(QuestionPaperAssignment.assigner))
        .filter(QuestionPaperAssignment.submission_id.in_(submission_ids))
        .order_by(QuestionPaperAssignment.id.desc())
        .all()
    )
    mapping: Dict[int, QuestionPaperAssignment] = {}
    for row in rows:
        if row.submission_id is not None and row.submission_id not in mapping:
            mapping[row.submission_id] = row
    return mapping


def list_submissions(
    db: Session,
    user_id: Optional[int] = None,
    question_paper_id: Optional[int] = None,
    day_type: Optional[str] = None,
    plant_id: Optional[int] = None,
    department_id: Optional[int] = None,
    sub_department_id: Optional[int] = None,
    line_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    is_graded: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    query = _submission_query_with_relations(db)

    if user_id is not None:
        query = query.filter(QuestionPaperSubmission.user_id == user_id)
    if question_paper_id is not None:
        query = query.filter(QuestionPaperSubmission.question_paper_id == question_paper_id)
    if day_type is not None and day_type.strip():
        query = query.filter(QuestionPaperSubmission.day_type == normalize_day_type(day_type))
    if plant_id is not None:
        query = query.filter(QuestionPaperSubmission.plant_id == plant_id)
    if department_id is not None:
        query = query.filter(QuestionPaperSubmission.department_id == department_id)
    if sub_department_id is not None:
        query = query.filter(QuestionPaperSubmission.sub_department_id == sub_department_id)
    if line_id is not None:
        query = query.filter(QuestionPaperSubmission.line_id == line_id)
    if machine_id is not None:
        query = query.filter(QuestionPaperSubmission.machine_id == machine_id)
    if is_graded is not None:
        query = query.filter(QuestionPaperSubmission.is_graded == is_graded)
    if status_filter is not None and status_filter.strip():
        st_norm = re.sub(r"[\s\-]+", "_", status_filter.strip()).upper()
        if st_norm in {"PENDING", "PENDING_REVIEW", "UNGRADED"}:
            query = query.filter(QuestionPaperSubmission.is_graded == False)  # noqa: E712
        elif st_norm == "GRADED":
            query = query.filter(QuestionPaperSubmission.is_graded == True)  # noqa: E712
        else:
            query = query.filter(QuestionPaperSubmission.status == st_norm)
    if search is not None and search.strip():
        pattern = f"%{search.strip()}%"
        query = (
            query.join(User, QuestionPaperSubmission.user_id == User.id)
            .join(QuestionPaper, QuestionPaperSubmission.question_paper_id == QuestionPaper.id)
            .filter(
                or_(
                    User.empName.ilike(pattern),
                    User.payCode.ilike(pattern),
                    QuestionPaper.title.ilike(pattern),
                )
            )
        )

    submissions = (
        query.order_by(QuestionPaperSubmission.submitted_at.desc(), QuestionPaperSubmission.id.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 1000))
        .all()
    )
    assignments_map = _load_assignments_by_submission_ids(db, [s.id for s in submissions])
    return [_serialize_submission(s, assignments_map.get(s.id)) for s in submissions]


def get_submission_by_id(db: Session, submission_id: int) -> Optional[Dict[str, Any]]:
    sub = (
        _submission_query_with_relations(db)
        .filter(QuestionPaperSubmission.id == submission_id)
        .first()
    )
    if not sub:
        return None
    linked_assignment = (
        db.query(QuestionPaperAssignment)
        .options(joinedload(QuestionPaperAssignment.assigner))
        .filter(QuestionPaperAssignment.submission_id == sub.id)
        .order_by(QuestionPaperAssignment.id.desc())
        .first()
    )
    return _serialize_submission(sub, linked_assignment)


def grade_submission(
    db: Session,
    submission_id: int,
    payload: SubmissionGradeUpdate,
    current_user: Optional[User] = None,
) -> Optional[Dict[str, Any]]:
    """Save supervisor manual grading/evaluation marks, percentage, pass/fail, and remarks."""
    sub = (
        _submission_query_with_relations(db)
        .filter(QuestionPaperSubmission.id == submission_id)
        .first()
    )
    if not sub:
        return None

    paper = sub.question_paper

    if payload.question_marks is not None:
        sub.question_marks_json = _to_json(payload.question_marks)

    # Resolve score: explicit score > sum of numeric question_marks > existing score
    score: Optional[Decimal] = sub.score
    if payload.score is not None:
        score = Decimal(str(payload.score))
    elif payload.question_marks:
        total_earned = Decimal("0")
        has_numeric = False
        for mark_val in payload.question_marks.values():
            if mark_val is None or (isinstance(mark_val, str) and not mark_val.strip()):
                continue
            try:
                total_earned += Decimal(str(mark_val))
                has_numeric = True
            except (InvalidOperation, ValueError, TypeError):
                continue
        if has_numeric:
            score = total_earned

    max_score: Optional[Decimal] = sub.max_score
    if payload.max_score is not None:
        max_score = Decimal(str(payload.max_score))
    elif max_score is None and paper and paper.total_marks is not None:
        max_score = Decimal(str(paper.total_marks))

    if score is not None:
        score = score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if max_score is not None:
        max_score = max_score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if payload.percentage is not None:
        percentage = Decimal(str(payload.percentage)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif score is not None and max_score is not None and max_score > 0:
        percentage = ((score / max_score) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        percentage = sub.percentage

    if payload.passed is not None:
        passed = bool(payload.passed)
    elif percentage is not None:
        pass_threshold = Decimal(
            str(paper.pass_percentage if (paper and paper.pass_percentage is not None) else 80)
        )
        passed = percentage >= pass_threshold
    else:
        passed = sub.passed

    grader_id = payload.graded_by if payload.graded_by is not None else (
        current_user.id if current_user else sub.graded_by
    )
    grader_user = None
    if payload.graded_by is not None:
        grader_user = db.query(User).filter(User.id == payload.graded_by).first()
        if not grader_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Grader user with id {payload.graded_by} does not exist",
            )

    grader_name = (
        payload.graded_by_name.strip()
        if (payload.graded_by_name and payload.graded_by_name.strip())
        else (
            grader_user.empName
            if grader_user
            else (current_user.empName if current_user else sub.graded_by_name)
        )
    )

    sub.score = score
    sub.max_score = max_score
    sub.percentage = percentage
    sub.passed = passed
    sub.is_graded = True
    sub.evaluation_status = "Graded"
    if payload.status and payload.status.strip():
        sub.status = payload.status.strip().upper()
    elif passed is True:
        sub.status = "PASSED"
    elif passed is False:
        sub.status = "FAILED"
    else:
        sub.status = "GRADED"

    if payload.remarks is not None:
        sub.remarks = payload.remarks.strip() or None

    sub.graded_by = grader_id
    sub.graded_by_name = grader_name
    sub.graded_at = datetime.utcnow()

    db.commit()

    loaded = (
        _submission_query_with_relations(db)
        .filter(QuestionPaperSubmission.id == sub.id)
        .first()
    )
    linked_assignment = (
        db.query(QuestionPaperAssignment)
        .options(joinedload(QuestionPaperAssignment.assigner))
        .filter(QuestionPaperAssignment.submission_id == sub.id)
        .order_by(QuestionPaperAssignment.id.desc())
        .first()
    )
    return _serialize_submission(loaded, linked_assignment)


def assign_question_papers(
    db: Session,
    payload: QuestionPaperAssignmentCreate,
    current_user: Optional[User] = None,
) -> Dict[str, Any]:
    """Supervisor bulk/single assignment of question paper(s) to selected operator(s)."""
    paper_ids: List[int] = []
    if payload.question_paper_id is not None:
        paper_ids.append(payload.question_paper_id)
    if payload.question_paper_ids:
        for pid in payload.question_paper_ids:
            if pid not in paper_ids:
                paper_ids.append(pid)

    operator_ids: List[int] = []
    if payload.operator_id is not None:
        operator_ids.append(payload.operator_id)
    if payload.operator_ids:
        for oid in payload.operator_ids:
            if oid not in operator_ids:
                operator_ids.append(oid)

    if not paper_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one question_paper_id is required",
        )
    if not operator_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one operator_id is required",
        )

    papers = db.query(QuestionPaper).filter(QuestionPaper.id.in_(paper_ids)).all()
    papers_by_id = {p.id: p for p in papers}
    missing_papers = [pid for pid in paper_ids if pid not in papers_by_id]
    if missing_papers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question paper(s) not found: {missing_papers}",
        )
    inactive_papers = [pid for pid in paper_ids if not papers_by_id[pid].is_active]
    if inactive_papers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign inactive question paper(s): {inactive_papers}",
        )

    operators = db.query(User).filter(User.id.in_(operator_ids)).all()
    operators_by_id = {u.id: u for u in operators}
    missing_operators = [oid for oid in operator_ids if oid not in operators_by_id]
    if missing_operators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operator user(s) not found: {missing_operators}",
        )

    assigned_by_id = (
        payload.assigned_by
        if payload.assigned_by is not None
        else (current_user.id if current_user else None)
    )
    assigner_user = None
    if payload.assigned_by is not None:
        assigner_user = db.query(User).filter(User.id == payload.assigned_by).first()
        if not assigner_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assigning user with id {payload.assigned_by} does not exist",
            )

    assigned_by_name = (
        payload.assigned_by_name.strip()
        if (payload.assigned_by_name and payload.assigned_by_name.strip())
        else (
            assigner_user.empName
            if assigner_user
            else (current_user.empName if current_user else None)
        )
    )

    existing_rows = (
        db.query(QuestionPaperAssignment)
        .filter(
            QuestionPaperAssignment.question_paper_id.in_(paper_ids),
            QuestionPaperAssignment.operator_id.in_(operator_ids),
        )
        .order_by(QuestionPaperAssignment.id.desc())
        .all()
    )
    active_pending_map: Dict[Tuple[int, int], QuestionPaperAssignment] = {}
    inactive_unsubmitted_map: Dict[Tuple[int, int], QuestionPaperAssignment] = {}
    for row in existing_rows:
        key = (row.question_paper_id, row.operator_id)
        if row.is_active and row.status in ("ASSIGNED", "PENDING") and key not in active_pending_map:
            active_pending_map[key] = row
        elif (not row.is_active) and row.submission_id is None and key not in inactive_unsubmitted_map:
            inactive_unsubmitted_map[key] = row

    now_utc = datetime.utcnow()
    notes_clean = payload.notes.strip() if (payload.notes and payload.notes.strip()) else None
    metadata_str = _to_json(payload.metadata)

    assigned_count = 0
    reactivated_count = 0
    updated_count = 0
    touched: List[QuestionPaperAssignment] = []

    try:
        for pid in paper_ids:
            paper = papers_by_id[pid]
            for oid in operator_ids:
                key = (pid, oid)
                if key in active_pending_map:
                    asgn = active_pending_map[key]
                    asgn.assigned_by = assigned_by_id
                    asgn.assigned_by_name = assigned_by_name
                    asgn.assigned_at = now_utc
                    if payload.due_at is not None:
                        asgn.due_at = payload.due_at
                    if payload.notes is not None:
                        asgn.notes = notes_clean
                    if payload.metadata is not None:
                        asgn.metadata_json = metadata_str
                    updated_count += 1
                    touched.append(asgn)
                elif key in inactive_unsubmitted_map:
                    asgn = inactive_unsubmitted_map[key]
                    asgn.is_active = True
                    asgn.status = "ASSIGNED"
                    asgn.day_type = paper.day_type
                    asgn.assigned_by = assigned_by_id
                    asgn.assigned_by_name = assigned_by_name
                    asgn.assigned_at = now_utc
                    asgn.due_at = payload.due_at
                    asgn.completed_at = None
                    asgn.submission_id = None
                    asgn.notes = notes_clean
                    asgn.metadata_json = metadata_str
                    reactivated_count += 1
                    touched.append(asgn)
                else:
                    asgn = QuestionPaperAssignment(
                        question_paper_id=pid,
                        operator_id=oid,
                        assigned_by=assigned_by_id,
                        assigned_by_name=assigned_by_name,
                        day_type=paper.day_type,
                        status="ASSIGNED",
                        assigned_at=now_utc,
                        due_at=payload.due_at,
                        notes=notes_clean,
                        metadata_json=metadata_str,
                        is_active=True,
                    )
                    db.add(asgn)
                    assigned_count += 1
                    touched.append(asgn)

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to save question paper assignments due to invalid reference",
        ) from exc

    touched_ids = [a.id for a in touched]
    loaded_rows = (
        _assignment_query_with_relations(db)
        .filter(QuestionPaperAssignment.id.in_(touched_ids))
        .all()
    )
    loaded_by_id = {a.id: a for a in loaded_rows}
    ordered_serialized = [_serialize_assignment(loaded_by_id[aid]) for aid in touched_ids if aid in loaded_by_id]

    return {
        "assigned_count": assigned_count,
        "reactivated_count": reactivated_count,
        "updated_count": updated_count,
        "assignments": ordered_serialized,
    }


def list_assignments(
    db: Session,
    question_paper_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    assigned_by: Optional[int] = None,
    status_filter: Optional[str] = None,
    day_type: Optional[str] = None,
    plant_id: Optional[int] = None,
    department_id: Optional[int] = None,
    sub_department_id: Optional[int] = None,
    line_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    query = _assignment_query_with_relations(db)

    if question_paper_id is not None:
        query = query.filter(QuestionPaperAssignment.question_paper_id == question_paper_id)
    if operator_id is not None:
        query = query.filter(QuestionPaperAssignment.operator_id == operator_id)
    if assigned_by is not None:
        query = query.filter(QuestionPaperAssignment.assigned_by == assigned_by)
    if status_filter is not None and status_filter.strip():
        st_norm = re.sub(r"[\s\-]+", "_", status_filter.strip()).upper()
        if st_norm in {"PENDING", "ASSIGNED"}:
            query = query.filter(QuestionPaperAssignment.status.in_(["ASSIGNED", "PENDING"]))
        else:
            query = query.filter(QuestionPaperAssignment.status == st_norm)
    if day_type is not None and day_type.strip():
        query = query.filter(QuestionPaperAssignment.day_type == normalize_day_type(day_type))
    if is_active is not None:
        query = query.filter(QuestionPaperAssignment.is_active == is_active)

    if any(x is not None for x in (plant_id, department_id, sub_department_id, line_id, machine_id)):
        query = query.join(
            QuestionPaper, QuestionPaperAssignment.question_paper_id == QuestionPaper.id
        ).join(User, QuestionPaperAssignment.operator_id == User.id)
        if plant_id is not None:
            query = query.filter(
                or_(QuestionPaper.plant_id == plant_id, User.plantId == plant_id)
            )
        if department_id is not None:
            query = query.filter(
                or_(QuestionPaper.department_id == department_id, User.departmentId == department_id)
            )
        if sub_department_id is not None:
            query = query.filter(
                or_(
                    QuestionPaper.sub_department_id == sub_department_id,
                    User.subDepartmentId == sub_department_id,
                )
            )
        if line_id is not None:
            query = query.filter(
                or_(QuestionPaper.line_id == line_id, User.lineId == line_id)
            )
        if machine_id is not None:
            query = query.filter(
                or_(QuestionPaper.machine_id == machine_id, User.machineId == machine_id)
            )

    rows = (
        query.order_by(QuestionPaperAssignment.assigned_at.desc(), QuestionPaperAssignment.id.desc())
        .offset(max(skip, 0))
        .limit(min(max(limit, 1), 1000))
        .all()
    )
    return [_serialize_assignment(a) for a in rows]


def unassign_question_paper(db: Session, assignment_id: int) -> bool:
    asgn = (
        db.query(QuestionPaperAssignment)
        .filter(QuestionPaperAssignment.id == assignment_id)
        .first()
    )
    if not asgn:
        return False
    asgn.is_active = False
    db.commit()
    return True


def get_operator_upcoming_papers(
    db: Session,
    operator_id: int,
    day_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return ONLY active question papers manually assigned to this operator
    that they have NOT yet attempted/submitted.
    """
    query = (
        _assignment_query_with_relations(db)
        .join(QuestionPaper, QuestionPaperAssignment.question_paper_id == QuestionPaper.id)
        .filter(
            QuestionPaperAssignment.operator_id == operator_id,
            QuestionPaperAssignment.is_active == True,  # noqa: E712
            QuestionPaperAssignment.status.in_(["ASSIGNED", "PENDING"]),
            QuestionPaper.is_active == True,  # noqa: E712
        )
    )
    if day_type is not None and day_type.strip():
        query = query.filter(QuestionPaperAssignment.day_type == normalize_day_type(day_type))

    assignments = (
        query.order_by(QuestionPaperAssignment.assigned_at.desc(), QuestionPaperAssignment.id.desc())
        .all()
    )
    if not assignments:
        return []

    # Exclude any paper already submitted by this operator
    submitted_paper_ids = {
        row[0]
        for row in db.query(QuestionPaperSubmission.question_paper_id)
        .filter(QuestionPaperSubmission.user_id == operator_id)
        .distinct()
        .all()
    }

    seen_paper_ids = set()
    upcoming: List[Dict[str, Any]] = []
    for asgn in assignments:
        if asgn.question_paper is None:
            continue
        if asgn.question_paper_id in submitted_paper_ids:
            continue
        if asgn.question_paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(asgn.question_paper_id)
        upcoming.append(
            {
                "assignment_id": asgn.id,
                "status": asgn.status,
                "assigned_by": asgn.assigned_by,
                "assigned_by_name": asgn.assigned_by_name
                or (asgn.assigner.empName if asgn.assigner else None),
                "assigned_at": asgn.assigned_at,
                "due_at": asgn.due_at,
                "notes": asgn.notes,
                "metadata": _from_json(asgn.metadata_json, None),
                "question_paper": _serialize_paper(asgn.question_paper),
            }
        )

    start = max(skip, 0)
    end = start + min(max(limit, 1), 1000)
    return upcoming[start:end]


def get_operator_past_papers(
    db: Session,
    operator_id: int,
    day_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Return ONLY question papers already attempted/submitted by this operator,
    including submitted answers, submission timestamp, and supervisor grading/remarks.
    """
    return list_submissions(
        db=db,
        user_id=operator_id,
        day_type=day_type,
        skip=skip,
        limit=limit,
    )
