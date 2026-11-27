"""
Comprehensive Test Suite for Unified LMS Question Papers & Employee Submissions APIs.
Tests Day 1, Day 2, hierarchy validation/auto-inference, Hindi/Devanagari payloads,
auto-scoring, filtering, and idempotent table creation.
"""
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.LMS.models import (
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
from app.LMS.schemas.questionPaperSchema import (
    OperatorUpcomingPaperResponse,
    QuestionPaperAssignmentBulkResponse,
    QuestionPaperAssignmentCreate,
    QuestionPaperCreate,
    QuestionPaperResponse,
    QuestionPaperSubmissionCreate,
    QuestionPaperSubmissionResponse,
    QuestionPaperUpdate,
    SubmissionGradeUpdate,
)
from app.LMS.services import questionPaperService
from app.main import app


def _setup_db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _register_mssql_funcs(dbapi_conn, _conn_record):
        dbapi_conn.create_function(
            "getdate", 0, lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )

    # Verify idempotent table creation (call twice)
    target_tables = [
        QuestionPaper.__table__,
        QuestionPaperSubmission.__table__,
        QuestionPaperAssignment.__table__,
    ]
    Base.metadata.create_all(engine)
    Base.metadata.create_all(engine, tables=target_tables, checkfirst=True)
    insp = inspect(engine)
    assert "question_papers" in insp.get_table_names()
    assert "question_paper_submissions" in insp.get_table_names()
    assert "question_paper_assignments" in insp.get_table_names()

    Session = sessionmaker(bind=engine)
    db = Session()

    p1 = Plant(id=1, plantName="unit 5")
    d1 = Department(id=6, plantId=1, departmentName="LB")
    d2 = Department(id=10, plantId=1, departmentName="PAINT SHOP")
    sd1 = SubDepartment(id=1014, plantId=1, departmentId=6, subDepartmentName="LBSubDep")
    sd2 = SubDepartment(id=1018, plantId=1, departmentId=10, subDepartmentName="PAINTSHOPSubDep")
    l1 = Line(id=1013, plantId=1, departmentId=6, subDepartmentId=1014, lineName="LBLine")
    l2 = Line(id=1017, plantId=1, departmentId=10, subDepartmentId=1018, lineName="PAINTSHOPLine")
    m1 = Machine(id=1008, plantId=1, departmentId=6, subDepartmentId=1014, lineId=1013, machineName="LBMachine")
    m2 = Machine(id=1012, plantId=1, departmentId=10, subDepartmentId=1018, lineId=1017, machineName="PAINTSHOPMachine")

    admin = User(
        id=1,
        payCode="ADMIN-001",
        empName="System Super Administrator",
        dob=date(1990, 1, 1),
        email="admin",
        passwordHash="hash",
        role="SUPER_ADMIN",
        active=True,
    )
    emp = User(
        id=2,
        payCode="10144",
        empName="Vishnu",
        dob=date(1980, 1, 1),
        plantId=1,
        departmentId=6,
        subDepartmentId=1014,
        lineId=1013,
        machineId=1008,
        email="vishnu@ntf.com",
        passwordHash="hash",
        role="OPERATOR",
        active=True,
    )

    db.add_all([p1, d1, d2, sd1, sd2, l1, l2, m1, m2, admin, emp])
    db.commit()
    return db, admin, emp


def run_question_paper_tests():
    # 1. Verify OpenAPI Route Registration
    schema = app.openapi()
    paths = schema["paths"]
    expected_paths = [
        "/api/v1/lms/question-papers/",
        "/api/v1/lms/question-papers/{paper_id}",
        "/api/v1/lms/question-papers/assignments",
        "/api/v1/lms/question-papers/assignments/{assignment_id}",
        "/api/v1/lms/question-papers/operator/upcoming",
        "/api/v1/lms/question-papers/operator/past",
        "/api/v1/lms/question-papers/submissions",
        "/api/v1/lms/question-papers/submissions/{submission_id}",
        "/api/v1/lms/question-papers/submissions/{submission_id}/grade",
        "/api/v1/lms/question-papers/{paper_id}/submit",
    ]
    for ep in expected_paths:
        assert ep in paths, f"Missing route in OpenAPI: {ep}"
    print("[OK] OpenAPI question-paper routes registered:", expected_paths)

    db, admin, emp = _setup_db()

    # 2. Create Day 1 Paper (grouped Day1QuestionPaper.jsx format with Hindi text + machine_id auto-infer)
    day1_questions = {
        "general": [
            {"q": "कंपनी कब START हुई?", "options": ["1990", "1984", "2000", "1980"]},
            {"q": "कंपनी का MAIN प्लांट कहाँ है?", "options": ["Sanand Gujarat", "Neemrana", "IMT Manesar", "Delhi"]},
        ],
        "maintenance": [
            {"q": "Maintenance क्या होता है?", "options": []},  # Free-text answer like Day1 Q14
        ],
    }
    p_day1 = questionPaperService.create_question_paper(
        db=db,
        payload=QuestionPaperCreate(
            title="DOJO TEST PAPER- DAY-1",
            description="NTF Company History, Overview, 5S, Kaizen, and General Plant Safety.",
            day_type="day1",
            document_code="F18(AMD-02)",
            revision="Rev. 00",
            duration_minutes=30,
            duration_label="30 मिनट",
            total_marks=20,
            pass_percentage=80,
            passing_instruction="(ऑब्जेक्टिव टेस्ट में पास होने के लिए 80% अंक लाना अनिवार्य है।)",
            machine_id=1008,  # Should auto-infer line=1013, sub_dept=1014, dept=6, plant=1
            questions=day1_questions,
            metadata={"totalPages": 2},
        ),
        current_user=admin,
    )
    resp_day1 = QuestionPaperResponse(**p_day1)
    assert resp_day1.day_type == "DAY_1"
    assert resp_day1.plant_id == 1 and resp_day1.plant_name == "unit 5"
    assert resp_day1.department_id == 6 and resp_day1.department_name == "LB"
    assert resp_day1.sub_department_id == 1014 and resp_day1.sub_department_name == "LBSubDep"
    assert resp_day1.line_id == 1013 and resp_day1.line_name == "LBLine"
    assert resp_day1.machine_id == 1008 and resp_day1.machine_name == "LBMachine"
    assert resp_day1.total_questions == 3
    assert resp_day1.created_by == 1
    assert resp_day1.questions["general"][0]["q"] == "कंपनी कब START हुई?"
    print("[OK] Day 1 paper created with hierarchy auto-inference and Unicode preservation.")

    # 3. Create Day 2 Paper (numbered Day2QuestionPaper.jsx format with answer keys for auto-scoring)
    day2_questions = {
        "1": {
            "q": "पार्ट की कलर वैल्यू किस इंस्ट्रूमेंट से चेक करते हैं?",
            "options": ["हाईएस्ट गेज कैलिपर", "वर्नियर", "कलर मीटर", "माइक्रोमीटर"],
            "correctOption": 2,
            "marks": 1,
        },
        "2": {
            "q": "पेंटेड पार्ट की DFT किस यंत्र से चेक करते हैं?",
            "options": ["Gloss मीटर", "टेपर स्केल", "DFT मीटर", "माइक्रोमीटर"],
            "correctOption": 2,
            "marks": 1,
        },
    }
    p_day2 = questionPaperService.create_question_paper(
        db=db,
        payload=QuestionPaperCreate(
            title="DOJO TEST PAPER-DAY-2",
            day_type="Day 2",
            document_code="F18(AMD-02)",
            revision="Rev. 00",
            plantId=1,
            departmentId=10,
            subDepartmentId=1018,
            lineId=1017,
            machineId=1012,
            questions=day2_questions,
        ),
        current_user=admin,
    )
    resp_day2 = QuestionPaperResponse(**p_day2)
    assert resp_day2.day_type == "DAY_2"
    assert resp_day2.department_id == 10 and resp_day2.machine_id == 1012
    assert resp_day2.total_questions == 2
    print("[OK] Day 2 paper created with camelCase input support.")

    # 4. Hierarchy mismatch validation must return 400
    try:
        questionPaperService.create_question_paper(
            db=db,
            payload=QuestionPaperCreate(
                title="Bad Hierarchy",
                day_type="DAY_1",
                department_id=10,
                machine_id=1008,  # belongs to dept 6, not 10
                questions=day1_questions,
            ),
            current_user=admin,
        )
        assert False, "Should have raised 400 for mismatched hierarchy"
    except HTTPException as exc:
        assert exc.status_code == 400
    print("[OK] Hierarchy mismatch rejected with HTTP 400.")

    # 5. List & filter papers
    all_papers = questionPaperService.list_question_papers(db)
    assert len(all_papers) == 2

    only_day1 = questionPaperService.list_question_papers(db, day_type="day1")
    assert len(only_day1) == 1 and only_day1[0]["id"] == resp_day1.id

    by_machine = questionPaperService.list_question_papers(db, machine_id=1012)
    assert len(by_machine) == 1 and by_machine[0]["id"] == resp_day2.id

    single = questionPaperService.get_question_paper_by_id(db, resp_day1.id)
    assert single is not None and single["title"] == "DOJO TEST PAPER- DAY-1"
    print("[OK] Question paper list filtering and GET by ID verified.")

    # 6. Supervisor assigns ONLY Day 1 paper to operator -> Operator upcoming returns ONLY Day 1
    before_assign_upcoming = questionPaperService.get_operator_upcoming_papers(db, operator_id=emp.id)
    assert before_assign_upcoming == [], "Operator must see 0 upcoming papers before manual assignment"

    asgn_res = questionPaperService.assign_question_papers(
        db=db,
        payload=QuestionPaperAssignmentCreate(
            question_paper_id=resp_day1.id,
            operator_ids=[emp.id],
            notes="Complete Day 1 safety induction",
        ),
        current_user=admin,
    )
    asgn_bulk = QuestionPaperAssignmentBulkResponse(**asgn_res)
    assert asgn_bulk.assigned_count == 1
    assert len(asgn_bulk.assignments) == 1
    assert asgn_bulk.assignments[0].status == "ASSIGNED"

    upcoming_after_assign = questionPaperService.get_operator_upcoming_papers(db, operator_id=emp.id)
    assert len(upcoming_after_assign) == 1
    upcoming_item = OperatorUpcomingPaperResponse(**upcoming_after_assign[0])
    assert upcoming_item.question_paper.id == resp_day1.id
    assert upcoming_item.status == "ASSIGNED"
    assert upcoming_item.notes == "Complete Day 1 safety induction"
    print("[OK] Supervisor assignment & Operator Upcoming isolation verified.")

    # 7. Submit Day 1 filled response (no answer keys -> SUBMITTED + auto-completes assignment)
    sub1 = questionPaperService.submit_question_paper(
        db=db,
        payload=QuestionPaperSubmissionCreate(
            question_paper_id=resp_day1.id,
            answers={"1": 1, "2": 2, "3": "मशीन की देखभाल"},
            participant_info={
                "time": "30 मिनट",
                "date": "27/11/2026",
                "name": "Vishnu",
                "designation": "ASSEMBLER",
                "unit": "unit 5",
            },
            training_schedule={"title": "Day 1 Initial Plant Training", "trainer": "Line Leader"},
        ),
        current_user=emp,
    )
    sub1_resp = QuestionPaperSubmissionResponse(**sub1)
    assert sub1_resp.user_id == emp.id
    assert sub1_resp.user_pay_code == "10144"
    assert sub1_resp.day_type == "DAY_1"
    assert sub1_resp.answered_count == 3
    assert sub1_resp.total_questions == 3
    assert sub1_resp.status == "SUBMITTED"
    assert sub1_resp.is_graded is False
    assert sub1_resp.evaluation_status == "Pending Review"
    assert sub1_resp.assignment_id == asgn_bulk.assignments[0].id
    assert sub1_resp.answers["3"] == "मशीन की देखभाल"
    assert sub1_resp.department_id == 6 and sub1_resp.machine_id == 1008

    # Upcoming must now be empty and Past must contain Day 1 submission
    upcoming_after_submit = questionPaperService.get_operator_upcoming_papers(db, operator_id=emp.id)
    assert upcoming_after_submit == [], "Submitted paper must move out of Upcoming immediately"
    past_after_submit = questionPaperService.get_operator_past_papers(db, operator_id=emp.id)
    assert len(past_after_submit) == 1 and past_after_submit[0]["id"] == sub1_resp.id
    completed_assignments = questionPaperService.list_assignments(
        db, operator_id=emp.id, status_filter="COMPLETED"
    )
    assert len(completed_assignments) == 1
    assert completed_assignments[0]["submission_id"] == sub1_resp.id
    print("[OK] Day 1 submission auto-completed assignment and moved paper from Upcoming to Past.")

    # 8. Supervisor grades Day 1 submission -> Operator Past reflects score/remarks/Graded
    graded = questionPaperService.grade_submission(
        db=db,
        submission_id=sub1_resp.id,
        payload=SubmissionGradeUpdate(
            question_marks={"1": 1, "2": 1, "3": 0.5},
            max_score=3,
            remarks="Good understanding of plant safety",
        ),
        current_user=admin,
    )
    graded_resp = QuestionPaperSubmissionResponse(**graded)
    assert graded_resp.is_graded is True
    assert graded_resp.evaluation_status == "Graded"
    assert float(graded_resp.score) == 2.5
    assert float(graded_resp.max_score) == 3.0
    assert float(graded_resp.percentage) == 83.33
    assert graded_resp.passed is True
    assert graded_resp.status == "PASSED"
    assert graded_resp.remarks == "Good understanding of plant safety"
    assert graded_resp.graded_by == admin.id

    past_after_grade = questionPaperService.get_operator_past_papers(db, operator_id=emp.id)
    assert past_after_grade[0]["is_graded"] is True
    assert past_after_grade[0]["evaluation_status"] == "Graded"
    assert past_after_grade[0]["remarks"] == "Good understanding of plant safety"

    # Supervisor submission filters: is_graded & search
    graded_only = questionPaperService.list_submissions(db, is_graded=True, search="Vishnu")
    assert len(graded_only) == 1 and graded_only[0]["id"] == sub1_resp.id
    pending_only = questionPaperService.list_submissions(db, status_filter="PENDING")
    assert len(pending_only) == 0
    print("[OK] Supervisor grading & filtered submission listing verified.")

    # 9. Submit Day 2 filled response (with answer keys -> auto-scored PASSED 100%)
    sub2 = questionPaperService.submit_question_paper(
        db=db,
        payload=QuestionPaperSubmissionCreate(
            answers={"1": 2, "2": 2},
            participant_info={"name": "Vishnu", "qualification": "ITI", "unit": "unit 5"},
        ),
        current_user=emp,
        path_paper_id=resp_day2.id,
    )
    sub2_resp = QuestionPaperSubmissionResponse(**sub2)
    assert sub2_resp.day_type == "DAY_2"
    assert float(sub2_resp.score) == 2.0
    assert float(sub2_resp.max_score) == 2.0
    assert float(sub2_resp.percentage) == 100.0
    assert sub2_resp.passed is True
    assert sub2_resp.status == "PASSED"
    print("[OK] Day 2 submission auto-scored cleanly (score=2/2, 100%, PASSED).")

    # 8. Filter submissions by user_id, question_paper_id, day_type, and hierarchy
    emp_subs = questionPaperService.list_submissions(db, user_id=emp.id)
    assert len(emp_subs) == 2
    day2_subs = questionPaperService.list_submissions(db, user_id=emp.id, day_type="DAY_2")
    assert len(day2_subs) == 1 and day2_subs[0]["question_paper_id"] == resp_day2.id
    dept6_subs = questionPaperService.list_submissions(db, department_id=6)
    assert len(dept6_subs) == 1 and dept6_subs[0]["id"] == sub1_resp.id
    print("[OK] Submission filtering by user_id, day_type, and hierarchy verified.")

    # 9. Update & soft-delete paper
    updated = questionPaperService.update_question_paper(
        db, resp_day1.id, QuestionPaperUpdate(title="DOJO TEST PAPER- DAY-1 (Updated)")
    )
    assert updated["title"] == "DOJO TEST PAPER- DAY-1 (Updated)"
    assert questionPaperService.delete_question_paper(db, resp_day1.id) is True
    active_papers = questionPaperService.list_question_papers(db, is_active=True)
    assert len(active_papers) == 1
    print("[OK] Question paper update & soft-delete verified.")

    db.close()
    print("ALL QUESTION PAPER BACKEND TESTS PASSED (100%)!")


if __name__ == "__main__":
    run_question_paper_tests()
