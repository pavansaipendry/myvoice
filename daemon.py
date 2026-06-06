#!/usr/bin/env python3
"""
myvoice daemon — hold-to-talk dictation that pastes into your focused window.

Start it once (in any terminal) and leave it running. Then, sitting in your
Claude Code prompt (or any text field):

    hold  Right Option (⌥)  →  speak  →  release

…and your transcribed words paste straight into the box. No command to type.
The Whisper model stays loaded, so transcription is fast. Everything is local.

One-time macOS permissions — grant your terminal app BOTH:
  System Settings → Privacy & Security → Accessibility
  System Settings → Privacy & Security → Input Monitoring
(without these, macOS blocks global hotkeys / synthetic paste)

Usage:
    python3 daemon.py                 # default hotkey: Right Option
    python3 daemon.py --model base.en # faster, lower quality
"""

import argparse
import subprocess
import sys
import threading
import time

import numpy as np
from pynput import keyboard

from record_transcribe import SR, _resample_to_16k, cleanup

def media_toggle(kb):
    """Tap the system Play/Pause media key. This controls whatever is currently
    'now playing' — a Chrome/YouTube tab, VLC, Spotify, Apple Music, etc. — so it
    works universally, unlike app-specific scripting."""
    try:
        kb.press(keyboard.Key.media_play_pause)
        kb.release(keyboard.Key.media_play_pause)
        return True
    except Exception:
        return False


class Daemon:
    def __init__(self, model_name, hotkey, auto_pause=True, device=None):
        import sounddevice as sd
        from faster_whisper import WhisperModel

        self.sd = sd
        print(f"loading whisper '{model_name}' …", file=sys.stderr, flush=True)
        self.model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self.hotkey = hotkey
        self.auto_pause = auto_pause
        self.device = device  # input device index, or None for system default
        self.kb = keyboard.Controller()
        info = sd.query_devices(device if device is not None else None, kind="input")
        self.in_sr = int(info["default_samplerate"]) or SR
        print(f"mic: {info['name']}", file=sys.stderr, flush=True)
        self.recording = False
        self.frames = []
        self.stream = None
        self.paused = False  # whether we toggled media for this take

    def _cb(self, indata, n, t, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start(self):
        if self.recording:
            return
        self.paused = media_toggle(self.kb) if self.auto_pause else False  # hush media
        self.frames = []
        self.recording = True
        self.stream = self.sd.InputStream(samplerate=self.in_sr, channels=1,
                                          dtype="float32", device=self.device,
                                          callback=self._cb)
        self.stream.start()
        print("🎙  recording… (release ⌥ to send)", file=sys.stderr, flush=True)

    def stop_recording(self):
        """Stop the mic, resume music right away, return the captured audio."""
        if not self.recording:
            return None
        self.recording = False
        self.stream.stop(); self.stream.close(); self.stream = None
        if self.paused:                       # resume media immediately
            media_toggle(self.kb)
            self.paused = False
        if not self.frames:
            return None
        return _resample_to_16k(np.concatenate(self.frames, axis=0)[:, 0], self.in_sr)

    def transcribe_and_paste(self, audio):
        if audio is None or audio.size < SR * 0.2:
            print("(too short)", file=sys.stderr); return
        segs, _ = self.model.transcribe(audio, language="en", beam_size=5,
                                        vad_filter=True)
        text = cleanup(" ".join(s.text.strip() for s in segs))
        if not text:
            print("(no speech detected)", file=sys.stderr); return
        print(f"→ {text}", file=sys.stderr, flush=True)
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        time.sleep(0.05)
        with self.kb.pressed(keyboard.Key.cmd):  # paste into focused window
            self.kb.press("v"); self.kb.release("v")

    def on_press(self, key):
        if key == self.hotkey:
            self.start()

    def on_release(self, key):
        if key == self.hotkey:
            audio = self.stop_recording()     # resumes music fast, before transcribe
            threading.Thread(target=self.transcribe_and_paste,
                             args=(audio,), daemon=True).start()

    def run(self):
        print("myvoice ready ✦ hold Right Option (⌥) to talk, release to send. "
              "Ctrl-C to quit.", file=sys.stderr, flush=True)
        with keyboard.Listener(on_press=self.on_press,
                               on_release=self.on_release) as listener:
            listener.join()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="small.en")
    p.add_argument("--no-pause", action="store_true",
                   help="don't auto-pause media while recording")
    p.add_argument("--mic", default="MacBook",
                   help="substring of input device name to use (default 'MacBook' "
                        "= built-in mic; falls back to system default if not found). "
                        "Pass --mic '' to force the system default input.")
    args = p.parse_args()

    device = None
    if args.mic:
        import sounddevice as sd
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and args.mic.lower() in d["name"].lower():
                device = i
                break
        if device is None:
            print(f"(no input device matching '{args.mic}'; using default)",
                  file=sys.stderr)

    Daemon(args.model, hotkey=keyboard.Key.alt_r,
           auto_pause=not args.no_pause, device=device).run()


if __name__ == "__main__":
    main()
