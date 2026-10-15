"""
Unit Tests for Attendance Management System
==========================================
Comprehensive tests for attendance_tools.py using isolated temporary files.
Can be executed with standard `python -m unittest` or `pytest`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import attendance_tools as at


class TestAttendanceTools(unittest.TestCase):
    def setUp(self) -> None:
        """Create a temporary directory and seed test student data."""
        self.test_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.test_dir) / "test_students.json"

        # Seed initial dataset:
        # Student 1: 18/20 = 90% (No shortage)
        # Student 2: 13/20 = 65% (Shortage < 75%)
        # Student 3: 0/0 = 0% (Edge case: new student)
        self.seed_data = [
            {
                "roll_no": 101,
                "name": "Aarav Sharma",
                "total_classes": 20,
                "attended_classes": 18,
                "attendance_history": {
                    "2026-09-01": "Present",
                    "2026-09-02": "Present",
                },
            },
            {
                "roll_no": 102,
                "name": "Diya Patel",
                "total_classes": 20,
                "attended_classes": 13,
                "attendance_history": {
                    "2026-09-01": "Present",
                    "2026-09-02": "Absent",
                },
            },
            {
                "roll_no": 103,
                "name": "Fresh Student",
                "total_classes": 0,
                "attended_classes": 0,
                "attendance_history": {},
            },
        ]

        with open(self.test_db_path, "w", encoding="utf-8") as f:
            json.dump(self.seed_data, f, indent=2)

    def tearDown(self) -> None:
        """Clean up temporary directory and files."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. get_all_students and Percentage Calculations
    # -----------------------------------------------------------------------

    def test_get_all_students_percentages(self) -> None:
        """Verify student list retrieval and percentage math."""
        students = at.get_all_students(file_path=self.test_db_path)
        self.assertEqual(len(students), 3)

        s101 = next(s for s in students if s["roll_no"] == 101)
        self.assertEqual(s101["attendance_percentage"], 90.0)
        self.assertFalse(s101["has_shortage"])

        s102 = next(s for s in students if s["roll_no"] == 102)
        self.assertEqual(s102["attendance_percentage"], 65.0)
        self.assertTrue(s102["has_shortage"])

        s103 = next(s for s in students if s["roll_no"] == 103)
        self.assertEqual(s103["attendance_percentage"], 0.0)
        self.assertFalse(s103["has_shortage"])

    def test_get_student_attendance_shortage_calculation(self) -> None:
        """Verify shortage alert and formula for classes required to reach 75%."""
        # 13 attended out of 20 total:
        # (13 + x) / (20 + x) >= 0.75 => x >= 3*(20) - 4*(13) = 60 - 52 = 8 classes
        res_102 = at.get_student_attendance(102, file_path=self.test_db_path)
        self.assertTrue(res_102["success"])
        self.assertTrue(res_102["is_shortage"])
        self.assertEqual(res_102["attendance_percentage"], 65.0)
        self.assertEqual(res_102["classes_needed_for_75"], 8)
        self.assertIn("CRITICAL SHORTAGE WARNING", res_102["shortage_warning"])

        # Student 101 has 90%, no shortage
        res_101 = at.get_student_attendance(101, file_path=self.test_db_path)
        self.assertFalse(res_101["is_shortage"])
        self.assertEqual(res_101["classes_needed_for_75"], 0)
        self.assertIsNone(res_101["shortage_warning"])

    def test_get_student_attendance_not_found(self) -> None:
        """Verify non-existent student lookup returns structured error."""
        res = at.get_student_attendance(999, file_path=self.test_db_path)
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"])

    # -----------------------------------------------------------------------
    # 2. mark_attendance Tests
    # -----------------------------------------------------------------------

    def test_mark_attendance_new_date_present(self) -> None:
        """Marking a new date as Present increments total and attended classes."""
        res = at.mark_attendance(
            roll_numbers=[101],
            status="Present",
            date_str="2026-10-15",
            file_path=self.test_db_path,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["updated_roll_numbers"], [101])

        student = at.get_student_attendance(101, file_path=self.test_db_path)
        self.assertEqual(student["total_classes"], 21)
        self.assertEqual(student["attended_classes"], 19)
        self.assertEqual(student["attendance_history"]["2026-10-15"], "Present")

    def test_mark_attendance_new_date_absent(self) -> None:
        """Marking a new date as Absent increments total classes but not attended classes."""
        res = at.mark_attendance(
            roll_numbers=[101],
            status="Absent",
            date_str="2026-10-15",
            file_path=self.test_db_path,
        )
        self.assertTrue(res["success"])

        student = at.get_student_attendance(101, file_path=self.test_db_path)
        self.assertEqual(student["total_classes"], 21)
        self.assertEqual(student["attended_classes"], 18)
        self.assertEqual(student["attendance_history"]["2026-10-15"], "Absent")

    def test_mark_attendance_idempotent_status_flip(self) -> None:
        """
        Re-marking an existing date from Present to Absent adjusts attended count
        without double-counting total_classes.
        """
        # On 2026-09-02, student 101 was originally Present (18/20)
        res = at.mark_attendance(
            roll_numbers=[101],
            status="Absent",
            date_str="2026-09-02",
            file_path=self.test_db_path,
        )
        self.assertTrue(res["success"])

        student = at.get_student_attendance(101, file_path=self.test_db_path)
        # Total classes should still be 20, attended should decrease from 18 to 17
        self.assertEqual(student["total_classes"], 20)
        self.assertEqual(student["attended_classes"], 17)
        self.assertEqual(student["attendance_history"]["2026-09-02"], "Absent")

    def test_mark_attendance_batch_and_unmatched_rolls(self) -> None:
        """Batch marking with some invalid rolls reports unmatched roll numbers."""
        res = at.mark_attendance(
            roll_numbers=[101, 102, 999],
            status="Present",
            date_str="2026-10-15",
            file_path=self.test_db_path,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["updated_roll_numbers"], [101, 102])
        self.assertEqual(res["not_found_roll_numbers"], [999])

    def test_mark_attendance_validation_errors(self) -> None:
        """Invalid date or invalid status raises ValueError."""
        with self.assertRaises(ValueError):
            at.mark_attendance([101], "InvalidStatus", "2026-10-15", file_path=self.test_db_path)

        with self.assertRaises(ValueError):
            at.mark_attendance([101], "Present", "not-a-date", file_path=self.test_db_path)

        with self.assertRaises(ValueError):
            at.mark_attendance([101], "Present", "2026-02-30", file_path=self.test_db_path)

    # -----------------------------------------------------------------------
    # 3. add_student Tests
    # -----------------------------------------------------------------------

    def test_add_student_success(self) -> None:
        """Adding a new student successfully writes to database."""
        res = at.add_student(104, "Meera Sen", file_path=self.test_db_path)
        self.assertTrue(res["success"])
        self.assertEqual(res["student"]["roll_no"], 104)
        self.assertEqual(res["student"]["name"], "Meera Sen")
        self.assertEqual(res["student"]["total_classes"], 0)
        self.assertEqual(res["student"]["attended_classes"], 0)

        # Verify persisted file
        students = at.get_all_students(file_path=self.test_db_path)
        self.assertEqual(len(students), 4)

    def test_add_student_duplicate(self) -> None:
        """Attempting to add duplicate roll number fails gracefully."""
        res = at.add_student(101, "Duplicate Aarav", file_path=self.test_db_path)
        self.assertFalse(res["success"])
        self.assertIn("already exists", res["error"])

    def test_add_student_invalid_arguments(self) -> None:
        """Invalid roll_no or empty name raises ValueError."""
        with self.assertRaises(ValueError):
            at.add_student(-5, "Bad Roll", file_path=self.test_db_path)

        with self.assertRaises(ValueError):
            at.add_student(105, "   ", file_path=self.test_db_path)


if __name__ == "__main__":
    unittest.main()
