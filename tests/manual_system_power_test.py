"""Manual safe test script for high-risk system power operations (shutdown, restart, sleep)."""

from __future__ import annotations

import time

from core.assistant import JarvisAssistant


def run_manual_test() -> None:
    print("=== JARVIS System Power Manual Test ===")
    print("SAFE MODE: High-risk power operations require explicit confirmation.\n")

    assistant = JarvisAssistant()
    assistant.startup()

    print("--- Test 1: Shutdown confirmation request & cancellation ---")
    res1 = assistant.handle_command("shutdown computer")
    print(f"Request: 'shutdown computer' -> {res1.message}")

    res2 = assistant.handle_command("no")
    print(f"Response: 'no' -> {res2.message}\n")

    print("--- Test 2: Restart confirmation request & cancellation ---")
    res3 = assistant.handle_command("restart computer")
    print(f"Request: 'restart computer' -> {res3.message}")

    res4 = assistant.handle_command("cancel")
    print(f"Response: 'cancel' -> {res4.message}\n")

    print("--- Test 3: Sleep confirmation request & cancellation ---")
    res5 = assistant.handle_command("sleep computer")
    print(f"Request: 'sleep computer' -> {res5.message}")

    res6 = assistant.handle_command("abort")
    print(f"Response: 'abort' -> {res6.message}\n")

    print("--- Test 4: Confirmation Expiration (10s timeout) ---")
    res7 = assistant.handle_command("shutdown computer")
    print(f"Request: 'shutdown computer' -> {res7.message}")
    print("Waiting 11 seconds to test expiration...")
    time.sleep(11.0)
    res8 = assistant.handle_command("yes")
    print(f"Response: 'yes' (after timeout) -> {res8.message}\n")

    print("--- Test 5: Interactive Real Hardware Power Action Execution ---")
    print("WARNING: This prompt allows testing an actual Windows power action.")
    print("Choose an action to execute on Windows, or press ENTER to skip all power actions safely:")
    print("  1 - Shutdown")
    print("  2 - Restart")
    print("  3 - Sleep")

    try:
        choice = input("Enter choice (1, 2, 3 or ENTER to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    action_map = {
        "1": ("shutdown computer", "Shutting down Windows"),
        "2": ("restart computer", "Restarting Windows"),
        "3": ("sleep computer", "Putting Windows to sleep"),
    }

    if choice in action_map:
        cmd_text, label = action_map[choice]
        print(f"\nAbout to execute {label}.")
        try:
            confirm = input("Type YES to confirm execution: ").strip()
        except (EOFError, KeyboardInterrupt):
            confirm = ""

        if confirm.strip().casefold() == "yes":
            print(f"Initiating request: '{cmd_text}'...")
            req = assistant.handle_command(cmd_text)
            print(f"Assistant: {req.message}")
            print("Confirming with 'yes'...")
            exec_res = assistant.handle_command("yes")
            print(f"Result: {exec_res.message}")
        else:
            print("Execution cancelled.")
    else:
        print("Skipped real power execution.")

    print("\n=== Manual System Power Test Complete ===")


if __name__ == "__main__":
    run_manual_test()
