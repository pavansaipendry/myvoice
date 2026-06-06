#!/usr/bin/env python3
"""
record_transcribe.py — record from the mic, transcribe locally with Whisper,
print the (punctuated) text to stdout.

Designed to be called by the /myvoice Claude Code slash command, so it runs
non-interactively: it starts listening, auto-stops after a short silence once
you've spoken (or after a max duration), then prints just the transcript.

Everything runs locally via faster-whisper — your audio never leaves the machine.

Flags:
    --model base.en     whisper model (tiny.en/base.en/small.en/...)
    --max 60            hard cap on recording seconds
    --silence 1.5       stop after this many seconds of trailing silence
    --threshold 0.015   RMS level above which a block counts as speech
    --self-test         skip the mic; transcribe a synthetic clip (plumbing check)
"""

import argparse
import re
import sys

import numpy as np

SR = 16000  # Whisper wants 16 kHz mono


def _resample_to_16k(audio, in_sr):
    """Downsample to 16 kHz. Uses clean decimation when in_sr is a multiple of
    16k (e.g. 48k->16k = /3), else falls back to linear interpolation."""
    if in_sr == SR:
        return audio
    if in_sr % SR == 0:
        f = in_sr // SR
        n = (len(audio) // f) * f
        return audio[:n].reshape(-1, f).mean(axis=1).astype(np.float32)
    n_out = int(round(len(audio) * SR / in_sr))
    x_old = np.linspace(0, 1, len(audio), endpoint=False)
    x_new = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def record(max_seconds, silence_stop, start_timeout, threshold, block=0.1):
    """Record until ~silence_stop seconds of quiet follow some speech.
    Captures at the device's native rate, then downsamples to 16 kHz."""
    import sounddevice as sd

    in_sr = int(sd.query_devices(kind="input")["default_samplerate"]) or SR
    blocksize = int(in_sr * block)
    frames, has_speech, silence, elapsed = [], False, 0.0, 0.0
    with sd.InputStream(samplerate=in_sr, channels=1, dtype="float32",
                        blocksize=blocksize) as stream:
        print("🎙  listening… (speak, it stops on its own)", file=sys.stderr, flush=True)
        while elapsed < max_seconds:
            data, _ = stream.read(blocksize)
            frames.append(data.copy())
            rms = float(np.sqrt(np.mean(data ** 2)))
            elapsed += block
            if rms > threshold:
                has_speech, silence = True, 0.0
            else:
                silence += block
            if has_speech and silence >= silence_stop:
                break
            if not has_speech and elapsed >= start_timeout:
                break  # nobody spoke
    if not frames:
        return np.zeros(0, dtype=np.float32), False
    audio = np.concatenate(frames, axis=0)[:, 0]
    return _resample_to_16k(audio, in_sr), has_speech


def cleanup(text):
    """Light grammar/punctuation tidy-up on top of Whisper's output."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]              # capitalize first letter
    if text[-1] not in ".!?":                       # ensure terminal punctuation
        text += "."
    return text


def type_into_focus(text):
    """Type text into whatever window is focused (your Claude Code prompt) via
    AppleScript keystrokes. Needs Accessibility permission for your terminal
    (System Settings -> Privacy & Security -> Accessibility)."""
    import subprocess
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to keystroke "{safe}"'],
        check=True,
    )


def transcribe(audio, model_name):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    # beam_size=5 + word punctuation gives cleaner grammar on short clips
    segments, _ = model.transcribe(audio, language="en", beam_size=5,
                                   vad_filter=True)
    return cleanup(" ".join(s.text.strip() for s in segments))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="small.en")
    p.add_argument("--max", type=float, default=60)
    p.add_argument("--silence", type=float, default=1.5)
    p.add_argument("--start-timeout", type=float, default=8)
    p.add_argument("--threshold", type=float, default=0.015)
    p.add_argument("--type", action="store_true",
                   help="type the transcript into the focused window (your prompt)")
    p.add_argument("--clip", action="store_true",
                   help="copy transcript to clipboard (then paste with Cmd+V)")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()

    if args.self_test:
        audio = (0.01 * np.random.randn(SR)).astype(np.float32)
        print("self-test transcript:", repr(transcribe(audio, args.model)),
              file=sys.stderr)
        return

    audio, has_speech = record(args.max, args.silence, args.start_timeout,
                               args.threshold)
    if not has_speech or audio.size < SR * 0.2:
        print("(no speech detected)")
        return
    print("… transcribing", file=sys.stderr, flush=True)
    text = transcribe(audio, args.model)
    if not text:
        print("(no speech detected)")
        return
    if args.type:
        try:
            type_into_focus(text)
        except Exception as e:
            print(f"(type failed: {e}; printing instead)", file=sys.stderr)
            print(text)
    elif args.clip:
        import subprocess
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        print(f'📋 copied — press Cmd+V to paste it into your prompt:\n\n{text}',
              file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
