# Recording the FrostByte (LangChain edition) demo video

A clean backup recording for the exhibition (handbook 12.3): about 3 minutes, real tools, real LLM.
If the network or the LLM fails on the day, play this video instead.

## 1. Before you record (5 minutes)

```bash
docker compose up -d eda                 # EDA tool server (iverilog, vvp, yosys)
curl -s localhost:8000/health            # -> {"ok":true}
source .venv-lc/bin/activate
ollama list | grep qwen2.5-coder:7b      # or set GROQ/GEMINI keys in .env
python -m pytest -q                      # all green before you hit record
```

- Terminal: a dark theme, font size 18 or larger, window about 120×35, prompt shortened (`PS1='$ '`).
- Close notifications. Use a quiet room. Use a headset microphone if you have one.
- Open these in tabs, ready to show: `docs/langchain_workflow.png`, `docs/s2_fsm.png`,
  `docs/s2_waveform.png`, `docs/s1_netlist.svg`, `README.md` (results table).
- Use **macOS**: Cmd+Shift+5 → "Record Selected Portion", or **OBS** (1080p, 30 fps, MKV, then remux to MP4).

## 2. Shot list (3 minutes)

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | `docs/device_block_diagram.png` | "Vaccines spoil invisibly when too warm or frozen. FrostByte turns a written storage rule into the tiny always-on chip logic that watches for it." |
| 0:15–0:35 | `python -m langchain_app.run specs/s5.txt --auto-approve` | "A vague rule: *warn when too warm*. The agent refuses to guess and asks questions. No RTL is written." |
| 0:35–1:35 | `python -m langchain_app.run specs/s2.txt --auto-approve` | Narrate each step: spec_analyst → design_parallel (RTL agent calls lint_verilog itself; testbench writer sees only the spec) → verify_debug_loop (point at any 🔁 retry line) → implement_parallel (yosys and power) → human_approval → report_writer. |
| 1:35–2:05 | `outputs/<s2 module>/report.md`, `tb.v` result line, `docs/s2_waveform.png` | "TEST_RESULT PASS from a real simulator; this is the waveform of the agent's own RTL going NORMAL → SUSPECT → ALARM, then ack." |
| 2:05–2:30 | `docs/langchain_workflow.png` | "The whole system is one composed LangChain Runnable: Branch for routing, Parallel for fan-out, a hand-written ReAct loop for tool use." |
| 2:30–3:00 | README results and ablation tables | "Here are our measured numbers, including failures, and the 0-retry versus 3-retry ablation." |

If S2 needs no retry in your take, also show a recorded run that did retry (trace.jsonl, or the
`history` in `metrics.json`). Do not fake one.

## 3. Offline fallback (no LLM available)

```bash
python -m langchain_app.run specs/s1.txt --mock --auto-approve
```

Every line is prefixed `[MOCK]` and labelled **MOCK LLM (scripted) — EDA results are real**. Say so
out loud. Mock runs never enter the benchmark.

## 4. After recording

- Trim the dead time. Add captions for each pipeline step if you have time.
- Export as MP4 (H.264), under 100 MB. Upload as unlisted and put the link and QR code on the poster.
- Keep a local copy on a USB stick.
