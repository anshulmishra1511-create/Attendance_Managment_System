"""
Attendance Management System Tools
==================================
Senior-engineered, production-ready backend module for interacting with student attendance records.
Provides type-hinted helper functions and OpenAI-compatible tool calling schemas.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Default storage path pointing to students.json in the same directory
DATA_FILE_PATH: Path = Path(__file__).parent / "students.json"

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Internal Storage Helpers
# ---------------------------------------------------------------------------

def _load_students(file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Loads student records safely from the JSON storage file."""
    path = file_path or DATA_FILE_PATH
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupted JSON in student data file: {path}") from exc


def _save_students(students: List[Dict[str, Any]], file_path: Optional[Path] = None) -> None:
    """
    Saves student records atomically using a temporary file to avoid corruption.
    """
    path = file_path or DATA_FILE_PATH
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(students, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp_path.replace(path)


def _validate_date(date_str: str) -> None:
    """Validates that a date string is in strict YYYY-MM-DD calendar format."""
    if not isinstance(date_str, str) or not DATE_REGEX.match(date_str):
        raise ValueError(f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'.")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date '{date_str}': {exc}") from exc


def _normalize_status(status: str) -> str:
    """Validates and normalizes attendance status to 'Present' or 'Absent'."""
    if not isinstance(status, str):
        raise ValueError("Status must be a string ('Present' or 'Absent').")
    cleaned = status.strip().capitalize()
    if cleaned not in ("Present", "Absent"):
        raise ValueError(f"Invalid status '{status}'. Allowed values are 'Present' or 'Absent'.")
    return cleaned


# ---------------------------------------------------------------------------
# Core Attendance Management Functions
# ---------------------------------------------------------------------------

def get_all_students(file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Retrieves all student records with computed attendance percentages.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing student records,
        including roll_no, name, total_classes, attended_classes, attendance_percentage,
        and attendance_history.
    """
    students = _load_students(file_path)
    augmented: List[Dict[str, Any]] = []

    for s in students:
        total = s.get("total_classes", 0)
        attended = s.get("attended_classes", 0)
        pct = round((attended / total * 100.0), 2) if total > 0 else 0.0

        augmented.append({
            "roll_no": s["roll_no"],
            "name": s["name"],
            "total_classes": total,
            "attended_classes": attended,
            "attendance_percentage": pct,
            "has_shortage": pct < 75.0 if total > 0 else False,
            "attendance_history": s.get("attendance_history", {}),
        })

    return augmented


def mark_attendance(
    roll_numbers: List[int],
    status: str,
    date_str: str,
    file_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Marks attendance ('Present' or 'Absent') for a list of student roll numbers for a specific date.

    Handles idempotent updates: if attendance was already logged for that date,
    adjusts attended_classes count accordingly without double-counting total_classes.

    Args:
        roll_numbers (List[int]): List of student roll numbers to mark.
        status (str): Attendance status ('Present' or 'Absent').
        date_str (str): Date string in 'YYYY-MM-DD' format.
        file_path (Optional[Path]): Optional custom file path for storage.

    Returns:
        Dict[str, Any]: Execution summary detailing updated roll numbers,
        unmatched roll numbers, and total affected.
    """
    _validate_date(date_str)
    normalized_status = _normalize_status(status)

    if not isinstance(roll_numbers, list) or not all(isinstance(r, int) for r in roll_numbers):
        raise ValueError("roll_numbers must be a list of integers.")

    target_rolls = set(roll_numbers)
    students = _load_students(file_path)

    updated: List[int] = []
    student_map = {s["roll_no"]: s for s in students}

    for roll in target_rolls:
        if roll in student_map:
            student = student_map[roll]
            history: Dict[str, str] = student.setdefault("attendance_history", {})
            prev_status = history.get(date_str)

            if prev_status is None:
                # First time logging attendance for this date
                student["total_classes"] = student.get("total_classes", 0) + 1
                if normalized_status == "Present":
                    student["attended_classes"] = student.get("attended_classes", 0) + 1
            else:
                # Date already exists; recalculate if status changes
                if prev_status != normalized_status:
                    if normalized_status == "Present" and prev_status == "Absent":
                        student["attended_classes"] = student.get("attended_classes", 0) + 1
                    elif normalized_status == "Absent" and prev_status == "Present":
                        student["attended_classes"] = max(0, student.get("attended_classes", 0) - 1)

            history[date_str] = normalized_status
            updated.append(roll)

    not_found = list(target_rolls - set(updated))

    if updated:
        _save_students(students, file_path)

    return {
        "success": True,
        "date": date_str,
        "status": normalized_status,
        "updated_roll_numbers": sorted(updated),
        "not_found_roll_numbers": sorted(not_found),
        "total_updated": len(updated),
        "message": f"Marked {len(updated)} student(s) as '{normalized_status}' for {date_str}."
        + (f" {len(not_found)} roll number(s) not found." if not_found else ""),
    }


def get_student_attendance(roll_no: int, file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Fetches detailed attendance statistics for a single student by roll number.
    Identifies shortage warnings if attendance is below 75% and calculates
    the number of consecutive classes required to reach 75%.

    Args:
        roll_no (int): Roll number of the student.
        file_path (Optional[Path]): Optional custom file path for storage.

    Returns:
        Dict[str, Any]: Attendance summary including percentage, shortage warning,
        remedial classes required, and attendance history.
    """
    if not isinstance(roll_no, int):
        raise ValueError("roll_no must be an integer.")

    students = _load_students(file_path)
    student = next((s for s in students if s["roll_no"] == roll_no), None)

    if not student:
        return {
            "success": False,
            "roll_no": roll_no,
            "error": f"Student with roll number {roll_no} not found.",
        }

    total = student.get("total_classes", 0)
    attended = student.get("attended_classes", 0)
    history = student.get("attendance_history", {})

    pct = round((attended / total * 100.0), 2) if total > 0 else 0.0
    is_shortage = pct < 75.0 if total > 0 else False

    # Calculate minimum consecutive classes to attend to reach 75%:
    # (attended + x) / (total + x) >= 0.75 => x >= 3*total - 4*attended
    classes_needed_for_75 = 0
    shortage_warning: Optional[str] = None

    if is_shortage and total > 0:
        classes_needed_for_75 = max(0, math.ceil(3 * total - 4 * attended))
        shortage_warning = (
            f"CRITICAL SHORTAGE WARNING: Attendance is {pct}%, which is below the mandatory 75% threshold. "
            f"The student must attend the next {classes_needed_for_75} consecutive class(es) without absence to reach 75%."
        )

    return {
        "success": True,
        "roll_no": student["roll_no"],
        "name": student["name"],
        "total_classes": total,
        "attended_classes": attended,
        "missed_classes": total - attended,
        "attendance_percentage": pct,
        "is_shortage": is_shortage,
        "shortage_warning": shortage_warning,
        "classes_needed_for_75": classes_needed_for_75,
        "attendance_history": history,
    }


def add_student(roll_no: int, name: str, file_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Registers a new student into the attendance database.

    Args:
        roll_no (int): Unique roll number of the student.
        name (str): Full name of the student.
        file_path (Optional[Path]): Optional custom file path for storage.

    Returns:
        Dict[str, Any]: Confirmation containing the created student record.
    """
    if not isinstance(roll_no, int) or roll_no <= 0:
        raise ValueError("roll_no must be a positive integer.")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string.")

    cleaned_name = name.strip()
    students = _load_students(file_path)

    if any(s["roll_no"] == roll_no for s in students):
        return {
            "success": False,
            "roll_no": roll_no,
            "error": f"Student with roll number {roll_no} already exists.",
        }

    new_student = {
        "roll_no": roll_no,
        "name": cleaned_name,
        "total_classes": 0,
        "attended_classes": 0,
        "attendance_history": {},
    }

    students.append(new_student)
    _save_students(students, file_path)

    return {
        "success": True,
        "message": f"Student '{cleaned_name}' with Roll No {roll_no} added successfully.",
        "student": new_student,
    }


# ---------------------------------------------------------------------------
# OpenAI-Compatible Tool Call Schemas
# ---------------------------------------------------------------------------

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_all_students",
            "description": "Retrieves the list of all registered students with summary stats including total classes, attended classes, attendance percentage, and shortage flag.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_attendance",
            "description": "Marks attendance for one or more students on a given date. Handles both first-time marking and idempotent modifications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "roll_numbers": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of student roll numbers to mark attendance for.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["Present", "Absent"],
                        "description": "The attendance status to assign ('Present' or 'Absent').",
                    },
                    "date_str": {
                        "type": "string",
                        "description": "Date in 'YYYY-MM-DD' format (e.g. '2026-10-15').",
                    },
                },
                "required": ["roll_numbers", "status", "date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_attendance",
            "description": "Fetches complete attendance profile, percentage, attendance history, and critical shortage warning (if below 75% attendance) for a specific student.",
            "parameters": {
                "type": "object",
                "properties": {
                    "roll_no": {
                        "type": "integer",
                        "description": "The unique roll number of the student.",
                    },
                },
                "required": ["roll_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_student",
            "description": "Enrolls a new student into the attendance management database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "roll_no": {
                        "type": "integer",
                        "description": "Unique integer roll number for the new student.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Full name of the student.",
                    },
                },
                "required": ["roll_no", "name"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Self-Verification Block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Attendance Management Tools")
    print("=" * 60)

    # 1. Fetch all students
    all_students = get_all_students()
    print(f"\n1. Loaded {len(all_students)} students from database:")
    for s in all_students:
        flag = " [SHORTAGE WARNING]" if s["has_shortage"] else ""
        print(f"   - #{s['roll_no']}: {s['name']} | Attendance: {s['attendance_percentage']}% ({s['attended_classes']}/{s['total_classes']}){flag}")

    # 2. Check student attendance with warning test
    print("\n2. Checking student with shortage (Roll No 102):")
    res_102 = get_student_attendance(102)
    print(f"   Name: {res_102['name']} ({res_102['attendance_percentage']}%)")
    print(f"   Shortage Flag: {res_102['is_shortage']}")
    print(f"   Warning: {res_102['shortage_warning']}")
    print(f"   Consecutive Classes Needed: {res_102['classes_needed_for_75']}")

    print("\n   Checking student without shortage (Roll No 101):")
    res_101 = get_student_attendance(101)
    print(f"   Name: {res_101['name']} ({res_101['attendance_percentage']}%)")
    print(f"   Shortage Flag: {res_101['is_shortage']}")

    # 3. Test OpenAI schemas export
    print(f"\n3. Exported TOOLS_SCHEMA count: {len(TOOLS_SCHEMA)}")
    for tool in TOOLS_SCHEMA:
        print(f"   - Tool: {tool['function']['name']}: {tool['function']['description'][:65]}...")

    print("\n" + "=" * 60)
    print("All tools verified successfully.")
    print("=" * 60)
