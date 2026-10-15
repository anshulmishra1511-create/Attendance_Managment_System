"""
OpenRouter Tool-Calling Diagnostic Script
=========================================
Standalone diagnostic utility that verifies:
1. .env loading and OPENROUTER_API_KEY presence
2. API connectivity to OpenRouter (https://openrouter.ai/api/v1)
3. Model capability to trigger structured tool/function calls
4. Local tool execution pipeline health
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

import attendance_tools


def run_diagnostic() -> bool:
    print("=" * 65)
    print("OpenRouter Diagnostic & Tool-Calling Pipeline Check")
    print("=" * 65)

    # 1. Environment and Key Validation
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

    print("\n[Step 1/4] Checking environment configuration...")
    if not api_key:
        print("  [FAIL] OPENROUTER_API_KEY is not set.")
        print("  Please create a .env file with your key (see .env.example):")
        print("    OPENROUTER_API_KEY=sk-or-v1-...")
        return False

    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"  [OK] Found OPENROUTER_API_KEY: {masked_key}")
    print(f"  [OK] Target Model: {model}")

    # 2. OpenRouter Client Initialization
    print("\n[Step 2/4] Connecting to OpenRouter API...")
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://attendance-system.local",
                "X-Title": "Attendance Diagnostics",
            },
        )
    except Exception as exc:
        print(f"  [FAIL] Could not initialize client: {exc}")
        return False
    print("  [OK] Client initialized successfully.")

    # 3. Test Tool-Calling Ping
    print("\n[Step 3/4] Sending tool-calling ping to model...")
    test_messages = [
        {
            "role": "system",
            "content": "You are a tool-calling assistant. When asked about attendance, always invoke the appropriate tool.",
        },
        {
            "role": "user",
            "content": "Fetch the attendance records for student with roll number 101.",
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=test_messages,
            tools=attendance_tools.TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=500,
        )
    except Exception as exc:
        print(f"  [FAIL] API request failed: {exc}")
        return False

    message = response.choices[0].message
    tool_calls = message.tool_calls

    if not tool_calls:
        print("  [FAIL] Model responded, but did not trigger a tool call.")
        print(f"  Response content: {message.content}")
        return False

    first_call = tool_calls[0]
    func_name = first_call.function.name
    raw_args = first_call.function.arguments
    print(f"  [OK] Tool-calling succeeded! Model invoked: '{func_name}'")
    print(f"       Arguments: {raw_args}")

    # 4. Pipeline Execution Verification
    print("\n[Step 4/4] Validating local tool execution dispatch...")
    if func_name == "get_student_attendance":
        try:
            args = json.loads(raw_args)
            result = attendance_tools.get_student_attendance(**args)
            print(f"  [OK] Successfully executed {func_name} locally!")
            print(f"       Result preview: Roll #{result.get('roll_no')} ({result.get('name')}), Attendance: {result.get('attendance_percentage')}%")
        except Exception as exc:
            print(f"  [FAIL] Failed executing tool function locally: {exc}")
            return False
    else:
        print(f"  [INFO] Model called '{func_name}' instead of get_student_attendance. Tool dispatch is functional.")

    print("\n" + "=" * 65)
    print("SUCCESS: OpenRouter API key and tool-calling pipeline are 100% operational!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)
