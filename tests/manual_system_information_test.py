"""Manual test for system information commands via real assistant routing."""

from __future__ import annotations

from core.assistant import JarvisAssistant


def run_manual_test() -> None:
    assistant = JarvisAssistant()
    assistant.startup()

    print("=== JARVIS System Information Manual Test ===")
    print("Testing read-only system information commands:\n")

    test_commands = [
        "cpu usage",
        "cpu status",
        "processor usage",
        "memory usage",
        "ram usage",
        "memory status",
        "disk usage",
        "disk status",
        "storage status",
        "battery status",
        "battery level",
        "what time is it",
        "current time",
        "time",
        "system status",
    ]

    for command in test_commands:
        print(f"Command: '{command}'")
        result = assistant.handle_command(command)
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Data: {result.data}\n")

    print("=== Manual System Information Test Complete ===")


if __name__ == "__main__":
    run_manual_test()
