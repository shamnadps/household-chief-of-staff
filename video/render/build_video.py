"""Assemble FINAL.mp4 from frames/<beat>/ + beat0..4.wav (run build_narration.py first).

Per beat: (image, weight) pairs. Each frame is held for
weight / sum(weights) * (that beat's wav duration), so audio and picture stay
in sync beat by beat. Frames scale into 1920x1080 on a pad. Hard cuts.

    python3 build_narration.py && python3 build_video.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).parent
FR = HERE / "frames"
WORK = HERE / "_build"
WORK.mkdir(exist_ok=True)

W, H, FPS = 1920, 1080, 30
PAD_DARK = "0x0b1120"
PAD_LIGHT = "0xf7f8fa"
PAD_BY_BEAT = {
    "beat0": PAD_DARK, "beat1": PAD_LIGHT, "beat2": PAD_LIGHT,
    "beat3": PAD_LIGHT, "beat4": PAD_DARK,
}

BEATS: dict[str, list[tuple[str, float]]] = {
    "beat0": [("beat0/01_title.jpg", 1)],
    "beat1": [("beat1/01_arch.jpg", 1)],
    "beat2": [
        ("beat2/01_sweep.jpg", 11),      # "here is a sweep running... ten proposals"
        ("beat2/02_wardrobe.jpg", 22),   # wardrobe / Kai paragraph
        ("beat2/03_gift.jpg", 19),       # gifts / photo book, over budget, flagged
        ("beat2/04_groceries.jpg", 15),  # four staples, 27.20 total
        ("beat2/05_travel.jpg", 21),     # Zurich / Bali, over travel budget
        ("beat2/06_kai_just.jpg", 18),   # Kai's justification on the proposal
    ],
    "beat3": [
        ("beat3/01_kai_card.jpg", 13),      # one email per proposal; open Kai's, approve
        ("beat3/02_executed.jpg", 13),      # flips to executed, budget counter moves
        ("beat3/03_after_overview.jpg", 12),# reject the photo book; gifts budget untouched
        ("beat3/04_completed.jpg", 10),     # deterministic budget check before email
        ("beat3/05_budgets.jpg", 11),       # the whole system on one page
    ],
    "beat4": [
        ("beat4/01_ask.jpg", 21),   # agentcore invoke, summarise + flag over budget
        ("beat4/02_github.jpg", 13),# it is all on GitHub, Apache-2.0
        ("beat4/03_close.jpg", 11), # watches / decides / justifies / asks first
    ],
}


def dur(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)])
    return float(out.strip())


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    seg_files: list[Path] = []
    for beat, frames in BEATS.items():
        wav = HERE / f"{beat}.wav"
        total = dur(wav)
        wsum = sum(w for _, w in frames)
        pad = PAD_BY_BEAT.get(beat, PAD_DARK)
        print(f"{beat}: {total:.2f}s over {len(frames)} frames")
        for i, (img, w) in enumerate(frames):
            seconds = total * w / wsum
            seg = WORK / f"{beat}_{i:02d}.mp4"
            fo = max(seconds - 0.4, 0.01)
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={pad},setsar=1,"
                  f"fade=t=in:st=0:d=0.35,fade=t=out:st={fo:.3f}:d=0.35,"
                  f"format=yuv420p")
            run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
                 "-t", f"{seconds:.3f}", "-i", str(FR / img),
                 "-vf", vf, "-r", str(FPS), "-c:v", "libx264",
                 "-preset", "medium", "-crf", "20", str(seg)])
            seg_files.append(seg)
            print(f"   {img}  {seconds:.2f}s")

    listf = WORK / "segs.txt"
    listf.write_text("".join(f"file '{p}'\n" for p in seg_files))
    visual = HERE / "video_visual.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listf), "-c", "copy", str(visual)])
    print(f"video_visual.mp4  {dur(visual):.2f}s")

    narr = HERE / "narration.wav"
    inputs: list[str] = []
    for b in range(5):
        inputs += ["-i", str(HERE / f"beat{b}.wav")]
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
         "[0:a][1:a][2:a][3:a][4:a]concat=n=5:v=0:a=1[a]", "-map", "[a]", str(narr)])
    print(f"narration.wav  {dur(narr):.2f}s")

    track = narr
    bed = HERE / "music_bed.wav"
    if bed.exists():
        track = HERE / "narration_mixed.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(narr), "-i", str(bed),
             "-filter_complex",
             ("[0:a]aresample=44100,asplit=2[vo][key];"
              "[1:a]aresample=44100,volume=0.18[bed];"
              "[bed][key]sidechaincompress=threshold=0.03:ratio=3:attack=20:release=400[duck];"
              "[vo][duck]amix=inputs=2:duration=first:normalize=0[mix]"),
             "-map", "[mix]", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(track)])
        print(f"narration_mixed.wav  {dur(track):.2f}s  (+ music bed)")

    final = HERE / "FINAL.mp4"
    srt = HERE / "narration.srt"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(visual), "-i", str(track)]
    if srt.exists():
        cmd += ["-i", str(srt)]
    cmd += ["-map", "0:v", "-map", "1:a"]
    if srt.exists():
        cmd += ["-map", "2:s", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)]
    run(cmd)
    print(f"\nFINAL.mp4  {dur(final):.2f}s"
          f"{'  (+ soft captions)' if srt.exists() else ''}"
          f"{'  (+ music bed)' if bed.exists() else ''}")


if __name__ == "__main__":
    main()
