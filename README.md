# SPIDEYY

SPIDEYY is a Windows desktop assistant with offline Vosk speech recognition,
pyttsx3 responses, a PySide6 dashboard, and deterministic application/window
commands. It operates on locally discovered applications and Windows window
handles; spoken input is never executed as a shell command.

## Overview

The voice flow is:

`hello jarvis` → acknowledgement → constrained command recognition → response → wake listening

Wake listening is limited to the wake phrase. Command listening uses a Vosk
grammar generated from registered application names and aliases, together with
the monitors currently reported by Windows. The command router is deterministic:
there is no fuzzy command correction.

## Architecture

- `voice/audio.py`: float32 microphone capture through sounddevice.
- `voice/speech.py`: PCM conversion, Vosk recognizer lifecycle, diagnostics,
  wake/command grammars, and partial/final text.
- `wake/wake_phrase.py`: text-only wake decision.
- `voice/interaction.py`: wake → command → TTS orchestration.
- `voice/tts.py`: synchronous pyttsx3 speech.
- `core/assistant.py`: assistant lifecycle orchestration.
- `core/command_registry.py`: command pattern definitions, `CommandIntent` matching, and speech grammar generation.
- `core/command_router.py`: deterministic command routing and intent dispatching to system services.
- `system/`: application registry/discovery, launching, monitor information,
  and handle-based window operations.
- `ui/dashboard.py`: desktop dashboard.


## Project Structure

```text
app/       application entry point
core/      state, configuration, logging, and command orchestration
data/      bundled Vosk model, logs, and application registry database
system/    Windows integration services
tests/     automated tests and manual hardware diagnostics
ui/        PySide6 dashboard
voice/     audio capture, speech recognition, TTS, and interaction
wake/      wake phrase and snap detection
```

## Requirements

- Windows (application launching and window management use `pywin32`).
- Python 3.13. The project is verified with its `.venv313` environment.
- A microphone supported by sounddevice/PortAudio.
- The bundled Vosk model at `data/models/vosk-model-small-en-us-0.15`, or an
  equivalent model placed at that path.

Install dependencies in a virtual environment:

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Vosk Model Setup

The application expects this directory:

```text
data/models/vosk-model-small-en-us-0.15
```

The model is included in the current workspace. If distributing the project
without it, download a compatible Vosk English model and preserve that path,
or pass an explicit `model_path` to the relevant voice service.

## Running the Application

```powershell
.\.venv313\Scripts\python.exe -m app.main
```

The dashboard initializes the local application registry at startup. Voice
interaction is exercised through the dedicated manual interaction script.

## Running Tests

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

The test suite uses mocks for Vosk, audio, TTS, Qt, and Windows APIs where
hardware or desktop integration is not appropriate for automated testing.

## Running Manual Speech Benchmark

```powershell
.\.venv313\Scripts\python.exe -m tests.manual_speech_benchmark
```

This benchmark does not execute desktop commands. It prints expected, partial,
and final recognition text for the supported benchmark phrases. It is the
appropriate way to validate microphone accuracy on the target machine.

For audio levels, device inventory, and block-size comparisons:

```powershell
.\.venv313\Scripts\python.exe tests\manual_speech_diagnostic.py --benchmark
```

## Running Manual Voice Interaction Test

```powershell
.\.venv313\Scripts\python.exe -m tests.manual_voice_interaction_test
```

This test starts the registry and voice interaction service. It can launch
applications and move windows, so use it only on the intended Windows desktop.

## Supported Voice Commands

Implemented commands include:

- `hello jarvis` (wake phrase)
- `help`
- `what can you do`
- `status` and `jarvis status`
- `show monitors`, `list monitors`, and `how many monitors`
- `refresh applications`
- `open <application>`, `launch <application>`, and `start <application>`
- `maximize <application>`, `minimize <application>`, and `restore <application>`
- `move <application> to monitor <number>`
- `cpu usage`, `cpu status`, and `processor usage`
- `memory usage`, `ram usage`, and `memory status`
- `disk usage`, `disk status`, and `storage status`
- `battery status` and `battery level`
- `what time is it`, `current time`, and `time`
- `system status`


Application names and aliases come from the local registry. Monitor numbers in
the command grammar are restricted to monitors currently detected by Windows.

## Verification Status

Implemented and automatically tested: lifecycle state handling, command
routing, application discovery/launching, monitor/window operations, speech
recognizer and grammar lifecycle, wake handling, interaction orchestration,
TTS, dashboard behavior, and audio stream cleanup.

Physically verified on the current Windows setup: wake recognition, the listed
benchmark commands, application launch, window movement, monitor responses,
and returning to wake mode after TTS. Hardware behavior can vary by microphone
and driver, so rerun the manual benchmark after changing audio devices or
models.
