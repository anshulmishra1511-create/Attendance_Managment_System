# AI-Powered College Attendance Management System

An intelligent, backend-engineered student attendance tracking system featuring type-hinted tool functions and an autonomous agent loop powered by OpenRouter LLMs (supporting models like `google/gemini-2.5-flash` and `openai/gpt-4o-mini`).

---

## Architecture Overview

```
                        +---------------------------+
                        |  User Prompt / CLI Query  |
                        +-------------+-------------+
                                      |
                                      v
                        +-------------+-------------+
                        |     ai_attendance.py      |
                        |   (OpenRouter Agent Loop) |
                        +------+-------------+------+
                               |             ^
             OpenAI Tool Calls |             | Tool Outputs
                               v             |
                        +------+-------------+------+
                        |    attendance_tools.py    |
                        | (Type-Hinted Backend API) |
                        +-------------+-------------+
                                      |
                            Atomic I/O Reads/Writes
                                      v
                        +-------------+-------------+
                        |       students.json       |
                        |   (JSON Student Database) |
                        +---------------------------+
```

---

## File Structure

| File | Description |
| :--- | :--- |
| [`students.json`](students.json) | Local JSON database storing college student attendance records and daily history. |
| [`attendance_tools.py`](attendance_tools.py) | Core Python backend module providing atomic storage operations, calculation math, input validation, and `TOOLS_SCHEMA`. |
| [`ai_attendance.py`](ai_attendance.py) | Autonomous agent loop interfacing with OpenRouter for natural-language attendance commands and relative date resolution. |
| [`test_attendance.py`](test_attendance.py) | Isolated unit test suite covering percentage math, shortage logic, idempotent updates, and student enrollment. |
| [`test_openrouter.py`](test_openrouter.py) | End-to-end diagnostic test verifying API authentication and function calling over OpenRouter. |
| [`.env.example`](.env.example) | Environment variable template for API keys and model configuration. |
| [`.gitignore`](.gitignore) | Excludes `.env`, `venv/`, `__pycache__/`, and temporary files from version control. |

---

## Prerequisites & Installation

### 1. Clone & Set Up Virtual Environment

```bash
# Navigate to the project root
cd ATTENDANCE

# Optional: Create and activate virtual environment
python -m venv venv
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install openai requests python-dotenv
```

### 3. Configure OpenRouter API Key

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Add your OpenRouter key into `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=google/gemini-2.5-flash
```

---

## Running Diagnostics & Tests

### 1. Run Core Unit Tests
Executes 11 isolated unit tests using temporary JSON storage:

```bash
python -m unittest test_attendance.py -v
```

### 2. Verify OpenRouter Connection & Tool Calling
Runs a 4-step diagnostic checking credentials, OpenRouter reachability, tool invocation, and local dispatch:

```bash
python test_openrouter.py
```

Expected output:
```text
[Step 1/4] Checking environment configuration... [OK]
[Step 2/4] Connecting to OpenRouter API...        [OK]
[Step 3/4] Sending tool-calling ping to model...  [OK] Model invoked: 'get_student_attendance'
[Step 4/4] Validating local tool execution...     [OK]
SUCCESS: OpenRouter API key and tool-calling pipeline are 100% operational!
```

---

## Using the AI Attendance Assistant

Run `ai_attendance.py` directly from the terminal with natural language instructions:

### 1. Check Attendance Shortages & Remedial Advice
```bash
python ai_attendance.py "Check who currently has an attendance shortage below 75% and what they need to fix it."
```

### 2. Mark Attendance Using Relative Dates ("Today", "Yesterday")
```bash
python ai_attendance.py "Mark roll numbers 101, 103, and 105 as Present for today."
```

### 3. Enroll a New Student
```bash
python ai_attendance.py "Add a new student with roll number 106 named Priya Nair."
```

### 4. Fetch Detailed Student Profile
```bash
python ai_attendance.py "Get the full attendance breakdown for student with roll number 102."
```

---

## Backend Functions Reference (`attendance_tools.py`)

- **`get_all_students() -> list[dict]`**:
  Retrieves all registered students, calculated attendance percentages, and shortage flags.

- **`mark_attendance(roll_numbers: list[int], status: str, date_str: str) -> dict`**:
  Idempotently records `'Present'` or `'Absent'` for a given date (`YYYY-MM-DD`). Adjusts attendance counters without double-counting classes if status is updated on an existing date.

- **`get_student_attendance(roll_no: int) -> dict`**:
  Returns attendance stats, complete history, shortage warnings, and calculates the exact number of consecutive classes required to reach 75%:
  $$\text{Classes Needed} = \max(0, \lceil 3 \cdot \text{total} - 4 \cdot \text{attended} \rceil)$$

- **`add_student(roll_no: int, name: str) -> dict`**:
  Enrolls a new student with duplicate roll number checks and validation.

- **`TOOLS_SCHEMA: list[dict]`**:
  OpenAI-compatible function definitions export ready to pass directly to `client.chat.completions.create(tools=TOOLS_SCHEMA)`.
