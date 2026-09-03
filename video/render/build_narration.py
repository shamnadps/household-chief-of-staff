"""Regenerate beat0..4.wav with the Daniel voice, sentence by sentence, and
emit narration.srt with frame-accurate timings (each sentence is spoken on
its own so we know its exact length). Long sentences are split on commas into
shorter caption cues.

    python3 build_narration.py
"""
from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

HERE = Path(__file__).parent
NARR = HERE / "_narr"
NARR.mkdir(exist_ok=True)
VOICE = "Daniel"
MAX_CUE_CHARS = 140


def dur(p: Path) -> float:
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)]).strip())


def sentences(text: str) -> list[str]:
    t = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]


def cue_chunks(sentence: str) -> list[str]:
    """Split an over-long sentence into caption-sized chunks on commas."""
    if len(sentence) <= MAX_CUE_CHARS:
        return [sentence]
    parts = re.split(r"(?<=,)\s+", sentence)
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


def caption_text(raw: str) -> str:
    raw = raw.replace(" -- ", " — ").replace("--", "—").strip(" ,")
    return "\n".join(textwrap.wrap(raw, width=48, break_long_words=False))


def main() -> None:
    cues: list[tuple[float, float, str]] = []
    clock = 0.0
    for b in range(5):
        txt = (HERE / f"beat{b}.txt").read_text()
        seg_files: list[Path] = []
        for si, sent in enumerate(sentences(txt)):
            aiff = NARR / f"b{b}_{si:02d}.aiff"
            subprocess.run(["say", "-v", VOICE, "-o", str(aiff), sent], check=True)
            d = dur(aiff)
            seg_files.append(aiff)
            # spread this sentence's caption cues across its duration by length
            chunks = cue_chunks(sent)
            clen = sum(len(c) for c in chunks) or 1
            cstart = clock
            for c in chunks:
                cd = d * len(c) / clen
                cues.append((cstart, cstart + cd, caption_text(c)))
                cstart += cd
            clock += d
        listf = NARR / f"b{b}.list"
        listf.write_text("".join(f"file '{p.name}'\n" for p in seg_files))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(listf), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
             str(HERE / f"beat{b}.wav")],
            check=True, cwd=NARR)
        print(f"beat{b}.wav  {dur(HERE / f'beat{b}.wav'):.2f}s  "
              f"({len(seg_files)} sentences)")

    srt = HERE / "narration.srt"
    with srt.open("w") as f:
        for i, (a, z, text) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(z)}\n{text}\n\n")
    print(f"\n{srt.name}  {len(cues)} cues, ends {ts(cues[-1][1])}")


if __name__ == "__main__":
    main()
