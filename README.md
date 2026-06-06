# myvoice — local voice dictation for the terminal / Claude Code

Hold a key, speak, and your words appear in your prompt — transcribed **locally**
with Whisper, so your voice never leaves your machine. Built as a DIY take on
Claude Code's native `/voice`, but fully offline and yours to hack.

```
hold  Right Option (⌥)  →  speak  →  release  →  text pastes into your prompt
```

## Why
Claude Code's built-in `/voice` is great but streams your audio to the cloud.
`myvoice` does speech-to-text **on-device** (faster-whisper / Whisper `small.en`)
and works in any text field, not just Claude Code.

**Honest limitation:** only the *native* `/voice` can stream text live into Claude
Code's input box as you speak — no third-party tool can write to that buffer. So
`myvoice` does the next best thing: you hold a key, speak, and the finished text
is **pasted** into whatever field is focused (your prompt), ready to edit + send.

## How it works
```
mic ──▶ record (auto/while-held) ──▶ Whisper (local) ──▶ clean text ──▶ paste into focused field
```
- **Recording:** `sounddevice`, captured at the device's native rate and
  downsampled to 16 kHz.
- **Transcription:** `faster-whisper` with `small.en` (good punctuation +
  accuracy; CPU is fine for short clips). The model stays loaded in the daemon
  for speed.
- **Insertion:** copies text to the clipboard and sends ⌘V to the focused window.

## Three ways to use it

**1. Hold-to-talk daemon (recommended)** — start once, then just hold a key:
```bash
python3 daemon.py                 # leave running; hold Right Option to talk
```
While you hold the key it **auto-pauses whatever's playing** (YouTube/Chrome,
VLC, Spotify, Music — via the system media key) and resumes on release.

> By default it records from the **built-in mic** (`--mic MacBook`). This is on
> purpose: using the AirPods *mic* forces them into low-quality "call mode" (a
> volume jump + worse audio), so recording from the built-in mic keeps AirPods in
> hi-fi for playback. Override with `--mic <name>`, or `--mic ''` for the system
> default input.

**2. `/myvoice` Claude Code slash command** — speak, transcript goes straight to
Claude (auto-stops on silence):
```
/myvoice
```

**3. One-shot CLI** — record once and copy to clipboard (then ⌘V), or type it:
```bash
python3 record_transcribe.py --clip     # → clipboard, paste with ⌘V
python3 record_transcribe.py --type     # → types into focused field
```

## Install
```bash
pip install -r requirements.txt          # sounddevice, faster-whisper, numpy (+ pynput for the daemon)
bash install.sh                           # installs /myvoice command + script into ~/.claude/
```

### macOS permissions (one-time, for the daemon)
The hold-to-talk daemon needs your terminal app added to **both**:
- **System Settings → Privacy & Security → Input Monitoring** (detect the hotkey)
- **System Settings → Privacy & Security → Accessibility** (paste for you)

Grant them, then **restart the daemon** (permissions only apply on a fresh start).
First run also downloads the Whisper model (~244 MB for `small.en`).

### Optional: always-on (auto-start at login)
Copy `com.myvoice.daemon.plist` into `~/Library/LaunchAgents/`, edit the paths,
then `launchctl load ~/Library/LaunchAgents/com.myvoice.daemon.plist`.

## Files
| file | what |
|------|------|
| `record_transcribe.py` | record + local Whisper transcribe; `--clip` / `--type` / `--self-test` |
| `daemon.py` | hold-to-talk background listener (Right Option), pastes into focus |
| `commands/myvoice.md` | the `/myvoice` Claude Code slash command |
| `install.sh` | installs the command + script into `~/.claude/` |

## Options
- `--model tiny.en|base.en|small.en|medium.en` — speed vs accuracy (default `small.en`).
- Daemon: `--mic <name substring>` pick input device · `--no-pause` don't pause media.
- Recorder: `--silence`, `--threshold`, `--max` to tune auto-stop.

## Caveats
- Each dictation overwrites your clipboard (it pastes via ⌘V).
- Transcription is on-device and decent, not perfect; bump to `medium.en` for
  higher accuracy at the cost of speed.
- macOS only for the paste/hotkey bits (uses AppleScript + pynput).

---
*Built by [@pavansaipendry](https://github.com/pavansaipendry). Local STT via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper).*
