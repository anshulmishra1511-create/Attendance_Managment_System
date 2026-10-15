import sys

# Ensure resilient console encoding across all Windows terminals (PowerShell, CMD, Bash)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ai_attendance import process_command


def main():
    print("=" * 65, flush=True)
    print("[AI] Attendance Management System - Interactive Chat", flush=True)
    print("Type your command in natural language (e.g., 'Mark roll 101 present today')", flush=True)
    print("Type 'exit' or 'quit' to close the program.", flush=True)
    print("=" * 65, flush=True)
    
    while True:
        try:
            user_input = input("\n[?] Enter command: ").strip()
            
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting... Goodbye!", flush=True)
                break
            
            if not user_input:
                continue
            
            print("\n[...] Processing with AI...", flush=True)
            response = process_command(user_input)
            
            print("\n" + "=" * 40, flush=True)
            print("[AI Response]:", flush=True)
            print(response, flush=True)
            print("=" * 40, flush=True)
            
        except (KeyboardInterrupt, EOFError):
            print("\nExiting... Goodbye!", flush=True)
            break
        except Exception as e:
            print(f"\n[!] Error: {e}", flush=True)


if __name__ == "__main__":
    main()
