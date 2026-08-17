"""Manual hardware test for low-risk Windows system controls (volume, workstation lock)."""

from __future__ import annotations

import sys

from core.assistant import JarvisAssistant


def run_manual_test() -> None:
    print("=== JARVIS System Control Manual Test ===")
    print("WARNING: This test will alter the actual Windows master volume level.\n")

    assistant = JarvisAssistant()
    assistant.startup()

    volume_commands = [
        "volume up",
        "volume down",
        "mute volume",
        "unmute volume",
        "set volume to 50",
        "set volume to 25",
        "set volume to 75",
    ]

    for command in volume_commands:
        print(f"Command: '{command}'")
        result = assistant.handle_command(command)
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Data: {result.data}\n")

    print("--- Workstation Lock Test ---")
    print("About to lock the computer.")
    try:
        user_input = input("Type YES to continue and lock the computer: ").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""

    if user_input.upper() == "YES":
        print("Executing 'lock computer'...")
        result = assistant.handle_command("lock computer")
        print(f"Result: {result.message}")
    else:
        print("Skipped lock computer test.")

    print("\n=== Manual System Control Test Complete ===")


if __name__ == "__main__":
    run_manual_test()
