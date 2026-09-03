"""Regenerate beat0..4.wav with Google Cloud Text-to-Speech (natural neural
voice) instead of macOS `say`, sentence by sentence, and rebuild
narration.srt with exact timings.

Auth: uses `gcloud auth print-access-token`. The texttospeech API must be
enabled on the project (done: household-agent-hack26).

    python3 build_narration_gcp.py [voice_name]
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import textwrap
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
NARR = HERE / "_narr_gcp"
NARR.mkdir(exist_ok=True)

PROJECT = "household-agent-hack26"
VOICE = sys.argv[1] if len(sys.argv) > 1 else "en-US-Studio-Q"
LANG = "-".join(VOICE.split("-")[:2])
URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
MAX_CUE_CHARS = 140


def token() -> str:
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def dur(p: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)]).strip())


def synth(text: str, out: Path, tok: str) -> None:
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": LANG, "name": VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 44100,
                        "speakingRate": 0.98},
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {tok}",
        "x-goog-user-project": PROJECT,
        "Content-Type": "application/json; charset=utf-8",
    })
    with urllib.request.urlopen(req) as r:
        audio = json.load(r)["audioContent"]
    out.write_bytes(base64.b64decode(audio))


def sentences(text: str) -> list[str]:
    t = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]


def cue_chunks(s: str) -> list[str]:
    if len(s) <= MAX_CUE_CHARS:
        return [s]
    parts = re.split(r"(?<=,)\s+", s)
    chunks, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) + 1 > MAX_CUE_CHARS:
            chunks.append(cur.strip())
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur.strip())
    return chunks


def ts(x: float) -> str:
    h, rem = divmod(x, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def cap(raw: str) -> str:
    raw = raw.replace(" -- ", " — ").replace("--", "—").strip(" ,")
    return "\n".join(textwrap.wrap(raw, width=48, break_long_words=False))


def main() -> None:
    tok = token()
    print(f"voice: {VOICE}")
    cues: list[tuple[float, float, str]] = []
    clock = 0.0
    for b in range(5):
        txt = (HERE / f"beat{b}.txt").read_text()
        segs: list[Path] = []
        for si, sent in enumerate(sentences(txt)):
            raw = NARR / f"b{b}_{si:02d}.wav"
            synth(sent, raw, tok)
            d = dur(raw)
            segs.append(raw)
            chunks = cue_chunks(sent)
            clen = sum(len(c) for c in chunks) or 1
            cs = clock
            for c in chunks:
                cd = d * len(c) / clen
                cues.append((cs, cs + cd, cap(c)))
                cs += cd
            clock += d
        lst = NARR / f"b{b}.list"
        lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
             str(HERE / f"beat{b}.wav")], check=True, cwd=NARR)
        print(f"beat{b}.wav  {dur(HERE / f'beat{b}.wav'):.2f}s  ({len(segs)} sentences)")

    srt = HERE / "narration.srt"
    with srt.open("w") as f:
        for i, (a, z, t) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(z)}\n{t}\n\n")
    print(f"\n{srt.name}  {len(cues)} cues, ends {ts(cues[-1][1])}")


if __name__ == "__main__":
    main()
