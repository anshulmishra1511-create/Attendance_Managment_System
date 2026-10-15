"""
AI Attendance Assistant Module
==============================
Senior-engineered autonomous agent loop connecting OpenRouter LLMs with
attendance management tools via function calling.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

import attendance_tools

# Load environment variables from .env file
load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

# Map tool names to their corresponding Python implementations
TOOL_DISPATCH: Dict[str, Callable[..., Any]] = {
    "get_all_students": attendance_tools.get_all_students,
    "mark_attendance": attendance_tools.mark_attendance,
    "get_student_attendance": attendance_tools.get_student_attendance,
    "add_student": attendance_tools.add_student,
}


def get_client() -> OpenAI:
    """
    Initializes and returns an OpenAI client configured for OpenRouter.

    Raises:
        ValueError: If OPENROUTER_API_KEY is missing from environment.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is missing. "
            "Please create a .env file containing your OpenRouter API key "
            "(see .env.example) or export OPENROUTER_API_KEY in your shell."
        )
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://attendance-system.local",
            "X-Title": "AI Attendance Management System",
        },
    )


def execute_tool_call(tool_name: str, arguments_json: str) -> str:
    """
    Safely parses arguments and executes the requested tool from attendance_tools.

    Args:
        tool_name (str): The name of the tool/function to invoke.
        arguments_json (str): JSON-encoded string of arguments from the model.

    Returns:
        str: JSON-serialized result of the tool execution.
    """
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return json.dumps({
            "error": f"Tool '{tool_name}' is not recognized. Available tools: {list(TOOL_DISPATCH.keys())}"
        })

    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as exc:
        return json.dumps({
            "error": f"Failed to parse tool arguments JSON: {exc}",
            "raw_arguments": arguments_json,
        })

    try:
        result = func(**kwargs)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "error": f"Execution error in tool '{tool_name}': {str(exc)}"
        })


def process_command(
    user_prompt: str,
    model: Optional[str] = None,
    max_turns: int = 6,
    verbose: bool = True,
) -> str:
    """
    Executes the autonomous agent loop:
    1. Sends user prompt and attendance tools schema to the OpenRouter model.
    2. Injects system instructions with today's date for relative date resolution.
    3. Handles multi-turn tool calling, executes Python functions, feeds back results.
    4. Returns the final synthesized response to the user.

    Args:
        user_prompt (str): The natural language instruction from the user.
        model (Optional[str]): OpenRouter model identifier (defaults to OPENROUTER_MODEL env or gemini-2.5-flash).
        max_turns (int): Maximum tool-use iterations to prevent infinite loops.
        verbose (bool): If True, logs tool calls and actions to standard output.

    Returns:
        str: Final natural language response from the assistant.
    """
    client = get_client()
    target_model = model or DEFAULT_MODEL
    today_str = datetime.now().strftime("%Y-%m-%d")

    system_prompt = (
        "You are an automated college attendance assistant. "
        f"Today's date is {today_str}. "
        "Always resolve relative dates using today's date, call the appropriate attendance tools, "
        "and summarize the action clearly."
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for turn in range(max_turns):
        if verbose:
            print(f"[Agent Loop] Step {turn + 1}: Querying {target_model}...")

        response = client.chat.completions.create(
            model=target_model,
            messages=messages,
            tools=attendance_tools.TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=2000,
        )

        choice = response.choices[0]
        response_message = choice.message

        # If the model produced tool calls, execute them and feedback the results
        if response_message.tool_calls:
            # Append the assistant's decision containing tool calls
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments

                if verbose:
                    print(f"  -> Invoking tool: {function_name}({arguments})")

                tool_output_str = execute_tool_call(function_name, arguments)

                if verbose:
                    preview = (tool_output_str[:120] + "...") if len(tool_output_str) > 120 else tool_output_str
                    print(f"  <- Tool Output: {preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_output_str,
                })
        else:
            # No further tool calls: the model returned the final message
            final_content = response_message.content or ""
            return final_content

    return "Agent loop reached maximum turn limit without reaching a final response."


# ---------------------------------------------------------------------------
# Interactive CLI / Testing Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 65)
    print("AI Attendance Assistant (OpenRouter Agent Loop)")
    print("=" * 65)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("\n[NOTE] OPENROUTER_API_KEY is not set.")
        print("To run queries against live models, add your key to .env:")
        print("    OPENROUTER_API_KEY=sk-or-v1-...\n")
        print("Testing mock tool execution locally:")
        sample_tool_result = execute_tool_call("get_student_attendance", '{"roll_no": 102}')
        print(f"Sample get_student_attendance(102) =>\n{sample_tool_result}")
        sys.exit(0)

    # If key is available, run interactive or test query
    test_query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Check who currently has an attendance shortage below 75% and what they need to fix it."
    )

    print(f"\nUser Prompt: {test_query}\n")
    try:
        reply = process_command(test_query)
        print("\n" + "=" * 65)
        print("FINAL ASSISTANT RESPONSE:")
        print("=" * 65)
        print(reply)
    except Exception as e:
        print(f"\nExecution error: {e}")
