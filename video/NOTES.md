# Demo video — narration script

`beat0.txt` … `beat4.txt` are the spoken narration, one file per beat, plain
text so macOS `say` reads them cleanly (numbers spelled out, `S E S` spaced so
it isn't read "sess", `--` for an em-dash pause).

Raw `say -v Daniel` timing (measured): beat0 31s · beat1 45s · beat2 105s ·
beat3 60s · beat4 42s — **≈ 4:43 total**, under the 5-minute limit.

## Beat → screen mapping (for frame capture)

| Beat | On screen |
|---|---|
| 0 | Title card (`video-production/title_open.html`) or the four category icons |
| 1 | `docs/architecture.svg`; a beat of the AWS console (Bedrock model access / CloudWatch) |
| 2 | Terminal: `aws lambda invoke --function-name household-agent-sweep …`; then `/admin` dashboard cards — wardrobe (Kai), gifts (hamper), groceries, travel; then DynamoDB `TXN#` items; then the Kai proposal's justification text |
| 3 | The approval email in the inbox; click Approve → JSON response; back to the dashboard / DynamoDB showing `executed` + the moved budget bar; reject the gift email |
| 4 | Terminal: `agentcore invoke '{"action":"ask","prompt":"Why did you propose the hamper, and is groceries near its budget?"}'`; the GitHub repo page; `docs/architecture.svg` |

## Numbers to lock during capture

Model-generated amounts vary per sweep. Before final narration, run a clean
sweep (`scripts/demo_reset.py` → `scripts/seed_data.py` → invoke) and confirm /
adjust in `beat2.txt`:

- Kai wardrobe proposal amount (script says **£60**)
- Gift hamper amount (script avoids a figure — keep it that way, or insert the real one)
- Grocery total (script says **£27.20** = milk 4.50 + bread 2.20 + coffee 8.50 + toilet paper 12.00)
- Zurich / Bali flight figures (script says **£1365 / £2465**; live pricing is off with `SERPAPI_API_KEY=none`, so these come from the seeded seasonal curve and are stable)
- Kai justification wording — quote the real text off the proposal

## Build

The assembly pipeline lives in `../../../google-cloud/video-production/`
(`build_narration.py` → `build_video.py`). Point it at these five files (or copy
them over its `beat*.txt`), drop the captured stills into `frames/beat*/`, and
adjust the per-frame weights in `build_video.py::BEATS` to match the new timings.
