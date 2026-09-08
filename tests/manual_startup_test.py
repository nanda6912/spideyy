"""Interactive, opt-in diagnostic for SPIDEYY Windows login startup."""

from __future__ import annotations

from system.startup_manager import StartupManager


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().casefold() in {"y", "yes"}


def main() -> None:
    manager = StartupManager()
    status = "Enabled" if manager.is_enabled() else "Disabled"
    print(f"Start with Windows: {status}")
    print(f"Startup command: {manager.get_startup_command()}")

    if not manager.is_enabled() and _confirm("Enable SPIDEYY at Windows login?"):
        print("Startup enabled." if manager.enable() else "Startup could not be enabled.")

    if manager.is_enabled() and _confirm("Disable SPIDEYY at Windows login?"):
        print("Startup disabled." if manager.disable() else "Startup could not be disabled.")

    if manager.is_enabled():
        print()
        print("Startup remains enabled. To verify it:")
        print("1. Save your work and close SPIDEYY.")
        print("2. Sign out of Windows, then sign in to the same user account.")
        print("3. Wait for the desktop; SPIDEYY should open once and report voice readiness.")
    else:
        print("No startup setting was changed unless you explicitly confirmed it.")


if __name__ == "__main__":
    main()
