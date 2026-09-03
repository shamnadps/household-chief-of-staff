# Demo video

`beat0.txt` … `beat4.txt` — the spoken narration, one file per beat, plain text
for macOS `say` (numbers spelled out, `S E S` spaced, `--` = em-dash pause).

**`render/`** is the self-contained build: `build_narration.py` (say → per-beat
WAVs + `narration.srt`), `build_video.py` (holds each still in `frames/beat*/`
for its narration-synced slice, muxes to `FINAL.mp4` with soft captions),
`pages/` (title cards + terminal cards, served over http for screenshotting).

## Rebuild

```bash
cd video/render
cp ../beat*.txt .
python3 build_narration.py
python3 build_video.py        # -> render/FINAL.mp4
```

Current cut: **4:41**, 1920×1080, H.264 / AAC, soft captions. Under the 5-min cap.

## Frames (narration order)

| Beat | Frames |
|---|---|
| 0 | title-open card |
| 1 | architecture diagram |
| 2 | `term_sweep` (lambda invoke) · dashboard: wardrobe/Kai · photo-book card · groceries · travel + budget bars · Kai's justification |
| 3 | Kai card (Approve/Reject) · Kai EXECUTED · dashboard after (gifts "nothing pending", 8 need approval) · COMPLETED + sweep log · budget bars |
| 4 | `term_ask` (AgentCore Q&A) · GitHub repo · title-close card |

## TODO — AWS console B-roll (blocked in automation)

The Claude-in-Chrome extension can't navigate to `console.aws.amazon.com`, so
the "proof it runs on AWS" cutaways aren't captured. Grab 2–3 stills and drop
them into `render/frames/beat1/` (and/or `beat2/`), then bump the weights in
`build_video.py::BEATS`:

- **DynamoDB** → table `HouseholdAgent` → Explore items (show `TXN#…` rows)
- **Bedrock** → Model access (Nova Lite enabled) or Usage
- optional: **Lambda** `household-agent-sweep`, or its CloudWatch log group

The real `aws lambda invoke` output and `agentcore invoke` output are already on
screen (terminal cards) and the dashboard is the live deployed stack, so the
video stands without these — they'd just strengthen the Technical Implementation
score.

## Upload

`render/FINAL.mp4` → YouTube/Vimeo (unlisted is fine) → paste the link into the
Devpost submission. `say -v Daniel` VO is clear but robotic; re-record over the
same timings if you want a human voice (`narration.srt` has the cue timings).
