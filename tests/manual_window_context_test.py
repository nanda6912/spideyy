"""Interactive Phase 5C-2 focus, window discovery, and safe-close diagnostic.

This script never closes a window without an explicit typed 'yes' from the user.
Review unsaved work before confirming any close request.
"""

from __future__ import annotations

from core.assistant import JarvisAssistant


def show_result(label: str, result) -> None:
    status = "OK" if result.success else "FAIL"
    print(f"{label} [{status}]: {result.message}")
    if result.data:
        # Show relevant details if present
        for key in ("windows", "window_count", "application", "hwnd", "monitor_index"):
            if key in result.data:
                print(f"    {key}: {result.data[key]}")


def run_manual_window_context_test() -> None:
    print("=" * 60)
    print("SPIDEYY PHASE 5C-2 WINDOW CONTEXT & DISCOVERY HARDENING")
    print("WARNING: closing a confirmed window may lose unsaved work.")
    print("=" * 60)

    assistant = JarvisAssistant()
    startup = assistant.startup()
    show_result("Startup", startup)

    # 1. Open windows listing
    print("\n--- 1. OPEN WINDOWS LISTING ---")
    show_result("List open windows", assistant.handle_command("list open windows"))

    # 2. Active window context
    print("\n--- 2. ACTIVE WINDOW CONTEXT ---")
    show_result("What is active", assistant.handle_command("what is active"))
    show_result("What window is active", assistant.handle_command("what window is active"))
    show_result("Which application is active", assistant.handle_command("which application is active"))

    # 3. Focus application
    print("\n--- 3. FOCUS APPLICATION ---")
    apps = assistant.registry.load_all()
    chrome = next((app for app in apps if "chrome" in {app.name.casefold(), *(a.casefold() for a in app.aliases)}), None)
    target = chrome.name if chrome else (apps[0].name if apps else None)
    if target is not None:
        show_result(f"Focus {target}", assistant.handle_command(f"focus {target}"))
        if len(apps) > 1:
            show_result(f"Focus {apps[1].name}", assistant.handle_command(f"focus {apps[1].name}"))

    # 4. Close application with cancellation & multi-window safeguard
    if target is not None:
        print(f"\n--- 4. CLOSE {target.upper()} WITH SAFE CANCELLATION ---")
        show_result(f"Request close {target}", assistant.handle_command(f"close {target}"))
        show_result("Cancel close", assistant.handle_command("cancel"))

        # 5. Close application with explicit confirmation check
        print(f"\n--- 5. CLOSE {target.upper()} WITH EXPLICIT CONFIRMATION ---")
        close_req = assistant.handle_command(f"close {target}")
        show_result(f"Request close {target} again", close_req)

        if close_req.success and close_req.data.get("requires_confirmation"):
            print("\n--- SAFETY CONFIRMATION CHECK ---")
            print(f"To actually close the {target} window via WM_CLOSE, type 'yes' and press Enter.")
            print("Default is CANCEL (type anything else or press Enter to cancel safely).")
            try:
                user_choice = input(f"Confirm closing {target}? [yes/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                user_choice = "no"

            if user_choice == "yes":
                show_result("Explicit close confirmation", assistant.handle_command("yes"))
            else:
                show_result("Close cancelled safely", assistant.handle_command("cancel"))
        else:
            print("Note: Close was not queued (e.g. multiple windows found or application not open).")

    # 6. Close active window with cancellation
    print("\n--- 6. CLOSE ACTIVE WINDOW WITH CANCELLATION ---")
    show_result("Request close active window", assistant.handle_command("close this window"))
    show_result("Cancel active-window close", assistant.handle_command("no"))

    # 7. Dashboard protection check
    print("\n--- 7. DASHBOARD PROTECTION CHECK ---")
    print("Testing protection against closing assistant dashboard via 'close this window'.")
    show_result("Dashboard protection check", assistant.handle_command("close this window"))
    assistant.handle_command("cancel")

    print("\n" + "=" * 60)
    print("Diagnostic complete.")
    print("=" * 60)


if __name__ == "__main__":
    run_manual_window_context_test()
