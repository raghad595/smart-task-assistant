"""
This file main task is to manage all the other files features to make the model use them depending on the intent extracted from the arabic message sent by the user.
The model will be used in the FastAPI backend to extract the intent and information from the arab
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from auth import can_assign_task
from dates import parse_arabic_datetime
from llm import extract_intent
from policy import answer_policy_question


# Configuration of the database path using Pathlib for cross-platform compatibility.
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "database.db"

app = FastAPI(title="Smart Task Assistant")


# Request and response models (user message, extracted intent, and structured response).
class ChatRequest(BaseModel):
    user_id: int = Field(gt=0)
    message: str = Field(min_length=1)

class ChatResponse(BaseModel):
    action: str
    task_id: Optional[int] = None
    reply: str

# Helper functions for audit logging and database access.
def log_audit(
    db: sqlite3.Connection,
    user_id: int,
    message: str,
    action_taken: str,
    status: str,
) -> None:
    """Append an audit record and commit the current transaction."""

    try:
        db.execute(
            """
            INSERT INTO audit_logs (
                user_id,
                message,
                action_taken,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, message, action_taken, status),
        )
        db.commit()

    except sqlite3.Error:
        db.rollback()
        raise


def audited_response(
    db: sqlite3.Connection,
    request: ChatRequest,
    action_taken: str,
    status: str,
    reply: str,
    task_id: Optional[int] = None,
) -> ChatResponse:
    """Write the audit record before returning the API response."""

    log_audit(
        db=db,
        user_id=request.user_id,
        message=request.message,
        action_taken=action_taken,
        status=status,
    )

    return ChatResponse(
        action=action_taken,
        task_id=task_id,
        reply=reply,
    )

# Database dependency
def get_db() -> Generator[sqlite3.Connection, None, None]:
    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail="Database is not initialized.",
        )

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        conn.close()


# format task-list responses
def format_tasks(rows: list, scope: str) -> str:
    if not rows:
        if scope == "all":
            return "لا توجد مهام مسجلة حالياً."
        if scope == "department":
            return "لا توجد مهام في قسمك حالياً."
        return "لا توجد مهام مسندة إليك حالياً."

    status_ar = {
        "pending": "قيد الانتظار",
        "in_progress": "قيد التنفيذ",
        "completed": "مكتملة",
        "cancelled": "ملغاة",
    }

    lines = ["المهام:"]

    for task in rows:
        status = status_ar.get(task["status"], task["status"])

        lines.append(
            f"- رقم المهمة: {task['task_id']}\n"
            f"  الوصف: {task['description']}\n"
            f"  المكلف: {task['assignee_name']}\n"
            f"  الموعد: {task['scheduled_at']}\n"
            f"  الحالة: {status}"
        )

    return "\n".join(lines)


# POST /chat
@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> ChatResponse:

    # Search the sender in the database.
    employee = db.execute(
        """
        SELECT id, name, role, department
        FROM employees
        WHERE id = ?
        """,
        (request.user_id,),
    ).fetchone()

    if employee is None:
        log_audit(
            db, request.user_id, request.message,
            "identify_employee", "rejected"
        )
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    sender = dict(employee)

    # Extract the intent.
    try:
        extracted = extract_intent(request.message)
    except (ValueError, RuntimeError):
        log_audit(
            db, request.user_id, request.message,
            "intent_extraction", "error"
        )
        raise HTTPException(
            status_code=502,
            detail="Could not interpret the message.",
        )

    # Branch 1: Policy question (known or unknown)
    if extracted.intent == "policy_qa":
        question = extracted.policy_question or request.message

        try:
            answer = answer_policy_question(question)
        except (ValueError, RuntimeError):
            log_audit(
                db, request.user_id, request.message,
                "policy_qa", "error"
            )
            raise HTTPException(
                status_code=502,
                detail="The policy service is unavailable.",
            )

        return audited_response(
            db, request, "policy_qa", "success", answer
        )

    # Branch 2: Show existing tasks (own, department, or all)
    elif extracted.intent == "show_tasks":
        role = sender["role"]
        scope = extracted.requested_scope or "own"

        # Authorization before querying task records.
        if scope == "all" and role != "مدير":
            return audited_response(
                db, request, "show_tasks", "rejected",
                "عذراً، لا تملك صلاحية عرض جميع مهام الشركة."
            )

        if scope == "department" and role == "موظف":
            return audited_response(
                db, request, "show_tasks", "rejected",
                "عذراً، يمكنك الاطلاع على مهامك فقط."
            )

        if scope == "department" and role == "مدير":
            return audited_response(
                db, request, "show_tasks", "clarify",
                "يرجى تحديد القسم الذي تريد عرض مهامه."
            )

        query = """
            SELECT
                t.task_id,
                t.description,
                t.scheduled_at,
                t.status,
                assignee.name AS assignee_name,
                assignee.department AS assignee_department
            FROM tasks AS t
            JOIN employees AS assignee
                ON assignee.id = t.assignee_id
        """
        params = []

        if scope == "own":
            query += " WHERE t.assignee_id = ?"
            params.append(sender["id"])

        elif scope == "department":
            if role != "مشرف":
                return audited_response(
                    db, request, "show_tasks", "rejected",
                    "عذراً، لا تملك صلاحية عرض هذه المهام."
                )

            query += " WHERE assignee.department = ?"
            params.append(sender["department"])

        elif scope != "all":
            return audited_response(
                db, request, "show_tasks", "clarify",
                "يرجى تحديد المهام التي تريد عرضها."
            )

        query += " ORDER BY t.scheduled_at, t.task_id"

        try:
            rows = db.execute(query, params).fetchall()
        except sqlite3.Error:
            db.rollback()
            log_audit(
                db, request.user_id, request.message,
                "show_tasks", "error"
            )
            raise HTTPException(
                status_code=500,
                detail="Could not retrieve tasks.",
            )

        reply = format_tasks(rows, scope)

        return audited_response(
            db, request, "show_tasks", "success", reply
        )

    # Branch 3: create new task
    elif extracted.intent == "create_task":

        # Resolve the assignee from database records.
        assignee_name = (
            extracted.assignee_name.strip()
            if extracted.assignee_name
            else ""
        )

        if assignee_name:
            matches = db.execute(
                """
                SELECT id, name, role, department
                FROM employees
                WHERE name = ?
                """,
                (assignee_name,),
            ).fetchall()

            if len(matches) == 0:
                return audited_response(
                    db, request, "create_task", "clarify",
                    f"لم أجد موظفاً باسم {assignee_name}. "
                    "يرجى التأكد من الاسم."
                )

            if len(matches) > 1:
                return audited_response(
                    db, request, "create_task", "clarify",
                    f"يوجد أكثر من موظف باسم {assignee_name}. "
                    "يرجى تحديد الموظف المقصود."
                )

            assignee = dict(matches[0])

        else:
            # Implicit self-directed reminder.
            assignee = sender

        # Check authorization before task creation.
        if not can_assign_task(sender, assignee):
            return audited_response(
                db, request, "create_task", "rejected",
                f"عذراً، لا تملك صلاحية إسناد مهمة إلى "
                f"{assignee['name']}."
            )

        description = (
            extracted.task_description.strip()
            if extracted.task_description
            else ""
        )

        if not description:
            return audited_response(
                db, request, "create_task", "clarify",
                "ما وصف المهمة التي تريد تسجيلها؟"
            )

        time_expression = (
            extracted.time_expression.strip()
            if extracted.time_expression
            else ""
        )

        if not time_expression:
            return audited_response(
                db, request, "create_task", "clarify",
                "متى تريد تنفيذ المهمة؟ يرجى تحديد اليوم والوقت."
            )

        # Resolve the date and apply the Friday rule.
        try:
            scheduled_at, was_shifted = parse_arabic_datetime(
                time_expression
            )
        except (ValueError, TypeError):
            return audited_response(
                db, request, "create_task", "clarify",
                "لم أتمكن من تحديد الموعد بدقة. "
                "يرجى توضيح اليوم والوقت."
            )

        if not scheduled_at:
            return audited_response(
                db, request, "create_task", "clarify",
                "يرجى تحديد موعد واضح للمهمة."
            )

        # Insert the task and audit record in the same time.
        try:
            cursor = db.execute(
                """
                INSERT INTO tasks (
                    description,
                    scheduled_at,
                    creator_id,
                    assignee_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    description,
                    scheduled_at,
                    sender["id"],
                    assignee["id"],
                ),
            )

            task_id = cursor.lastrowid
            final_dt = datetime.fromisoformat(scheduled_at)

            reply = (
                f"تم إنشاء المهمة «{description}» وإسنادها إلى "
                f"{assignee['name']} بتاريخ "
                f"{final_dt.strftime('%Y-%m-%d')} "
                f"الساعة {final_dt.strftime('%H:%M')}."
            )

            if was_shifted:
                reply += (
                    " كان الموعد يوم الجمعة، لذلك تم ترحيل "
                    "المهمة إلى يوم السبت مع الحفاظ على الوقت."
                )

            # This commits both the task and its success audit.
            return audited_response(
                db, request, "create_task", "success",
                reply, task_id
            )

        except sqlite3.Error:
            db.rollback()

            log_audit(
                db, request.user_id, request.message,
                "create_task", "error"
            )

            raise HTTPException(
                status_code=500,
                detail="The task could not be saved.",
            )

    # Branch 4: Unknown intent or unhandled case
    return audited_response(
        db, request, "unknown", "clarify",
        "عذراً، لم أفهم طلبك بوضوح. يرجى إعادة صياغة طلبك."
    )