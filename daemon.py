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


class Daemon:
    def __init__(self, model_name, hotkey):
        import sounddevice as sd
        from faster_whisper import WhisperModel

        self.sd = sd
        print(f"loading whisper '{model_name}' …", file=sys.stderr, flush=True)
        self.model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self.hotkey = hotkey
        self.kb = keyboard.Controller()
        self.in_sr = int(sd.query_devices(kind="input")["default_samplerate"]) or SR
        self.recording = False
        self.frames = []
        self.stream = None

    def _cb(self, indata, n, t, status):
        if self.recording:
            self.frames.append(indata.copy())

    def start(self):
        if self.recording:
            return
        self.frames = []
        self.recording = True
        self.stream = self.sd.InputStream(samplerate=self.in_sr, channels=1,
                                          dtype="float32", callback=self._cb)
        self.stream.start()
        print("🎙  recording… (release ⌥ to send)", file=sys.stderr, flush=True)

    def stop_and_paste(self):
        if not self.recording:
            return
        self.recording = False
        self.stream.stop(); self.stream.close(); self.stream = None
        if not self.frames:
            return
        audio = _resample_to_16k(np.concatenate(self.frames, axis=0)[:, 0], self.in_sr)
        if audio.size < SR * 0.2:
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
            # transcribe off the listener thread so keys stay responsive
            threading.Thread(target=self.stop_and_paste, daemon=True).start()

    def run(self):
        print("myvoice ready ✦ hold Right Option (⌥) to talk, release to send. "
              "Ctrl-C to quit.", file=sys.stderr, flush=True)
        with keyboard.Listener(on_press=self.on_press,
                               on_release=self.on_release) as listener:
            listener.join()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="small.en")
    args = p.parse_args()
    Daemon(args.model, hotkey=keyboard.Key.alt_r).run()


if __name__ == "__main__":
    main()
