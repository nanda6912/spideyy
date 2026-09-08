"""Interactive Phase 5C-1 focus and safe-close diagnostic.

This script never closes a window without an explicit confirmation typed by the
user. Review unsaved work before confirming any close request.
"""

from __future__ import annotations

from core.assistant import JarvisAssistant


def show_result(label: str, result) -> None:
    status = "OK" if result.success else "FAIL"
    print(f"{label} [{status}]: {result.message}")


def run_manual_window_context_test() -> None:
    print("SPIDEYY PHASE 5C-1 WINDOW CONTEXT DIAGNOSTIC")
    print("WARNING: closing a confirmed window may lose unsaved work.")
    assistant = JarvisAssistant()
    startup = assistant.startup()
    show_result("Startup", startup)

    apps = assistant.registry.load_all()
    chrome = next((app for app in apps if "chrome" in {app.name.casefold(), *(a.casefold() for a in app.aliases)}), None)
    target = chrome.name if chrome else (apps[0].name if apps else None)
    if target is None:
        print("No discovered application is available for this diagnostic.")
        return

    show_result(f"Focus {target}", assistant.handle_command(f"focus {target}"))
    if len(apps) > 1:
        show_result("Focus another discovered application", assistant.handle_command(f"focus {apps[1].name}"))

    show_result(f"Request close {target}", assistant.handle_command(f"close {target}"))
    show_result("Cancel close", assistant.handle_command("cancel"))
    show_result(f"Request close {target} again", assistant.handle_command(f"close {target}"))
    print("\n--- SAFETY CONFIRMATION CHECK ---")
    print(f"To actually close the {target} window via WM_CLOSE, type 'yes' and press Enter.")
    print("To cancel and leave all windows open safely, press Enter or type anything else.")
    try:
        user_choice = input(f"Confirm closing {target}? [yes/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        user_choice = "no"

    if user_choice in {"yes", "confirm", "confirmed"}:
        show_result("Explicit close confirmation", assistant.handle_command("yes"))
    else:
        show_result("Close cancelled safely", assistant.handle_command("cancel"))

    print("\nTesting 'close this window' with safe cancellation:")
    show_result("Request close active window", assistant.handle_command("close this window"))
    show_result("Cancel active-window close", assistant.handle_command("no"))


if __name__ == "__main__":
    run_manual_window_context_test()
