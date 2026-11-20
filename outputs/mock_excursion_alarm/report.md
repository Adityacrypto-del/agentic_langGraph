> **MOCK LLM (scripted) — EDA results are real.** The LLM text was scripted; every tool number below came from real iverilog/yosys runs.

# Report: excursion_alarm

## Summary
Status: **PASS** after 1 verify retries.

## Spec rules
- 1. rst_n=0 immediately sets count=0 (alarm=0).
- 2. Readings are evaluated only on a posedge where sample_valid=1.
- 3. A reading is out-of-range if temp < 4 or temp > 16 (signed comparison).
- 4. Out-of-range reading: count = min(count+1, 3) (saturates at 3).
- 5. In-range reading (4 <= temp <= 16): count = 0.
- 6. alarm = 1 whenever count == 3, else 0.

## Design decisions
2-bit saturating counter of consecutive out-of-range readings; signed comparison against 4 and 16.

## Verification result
passed=True total=19 failed=0

## Synthesis result
cells=27 dffs=2 area_ge=48.0

## Power estimate
0.6846 nW vs budget 100.0 nW (within budget: True).
This is a switching-activity estimate, not silicon power.

## Retry history
- retry 1 (sim): fixed RTL – The count wraps from 3 to 0 on a 4th out-of-range reading instead of saturating at 3 as rule 4 requires.

## Limitations
Generic-gate synthesis; power is a switching-activity estimate; simulation only.
