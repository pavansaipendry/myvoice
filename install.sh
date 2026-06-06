#!/usr/bin/env bash
# Install the /myvoice slash command for Claude Code.
# Copies the transcription script + command into ~/.claude/ and checks deps.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/myvoice"
CMDS="$HOME/.claude/commands"

echo "installing /myvoice …"
mkdir -p "$DEST" "$CMDS"
cp "$HERE/record_transcribe.py" "$DEST/record_transcribe.py"
cp "$HERE/commands/myvoice.md" "$CMDS/myvoice.md"

echo "checking python deps (sounddevice, faster-whisper) …"
python3 - <<'PY' || { echo "  -> run: pip install -r requirements.txt"; exit 1; }
import importlib, sys
miss = [m for m in ("sounddevice", "faster_whisper", "numpy")
        if importlib.util.find_spec(m) is None]
print("  missing:", miss or "none")
sys.exit(1 if miss else 0)
PY

echo
echo "done. In Claude Code, type /myvoice and start speaking."
echo "(first use downloads the Whisper model ~74MB; grant your terminal mic access if prompted)"
