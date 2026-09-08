"""Manual diagnostic script for Phase 5B read-only desktop context queries."""

from __future__ import annotations

import sys
from core.assistant import JarvisAssistant


def run_manual_context_test() -> None:
    print()
    print("=" * 60)
    print("SPIDEYY PHASE 5B READ-ONLY DESKTOP CONTEXT DIAGNOSTIC")
    print("=" * 60)

    assistant = JarvisAssistant()
    startup = assistant.startup()
    print(f"[STARTUP] {startup.message}")
    print()

    apps = assistant.registry.load_all()
    target_app = apps[0].name if apps else "chrome"
    print(f"[REGISTRY] Discovered {len(apps)} registered applications. Testing target: '{target_app}'")

    queries = [
        "what window is active",
        "what application is active",
        "which monitor is this window on",
        "what applications are open",
        f"is {target_app} open",
        f"where is {target_app}",
    ]

    for query in queries:
        print(f"QUERY: '{query}'")
        result = assistant.handle_command(query)
        status_tag = "OK" if result.success else "FAIL"
        print(f"RESULT [{status_tag}]: {result.message}")
        if result.data:
            print(f"DATA: {result.data}")
        print("-" * 60)

    print()
    print("[DIAGNOSTIC COMPLETE]")


if __name__ == "__main__":
    run_manual_context_test()
