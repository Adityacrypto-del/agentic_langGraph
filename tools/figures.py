"""Hardware figures for the README / poster (all from real artefacts, nothing hand-faked).

  python tools/figures.py fsm                          -> docs/s2_fsm.png       (Graphviz, from specs/s2.txt)
  python tools/figures.py device                       -> docs/device_block_diagram.png
  python tools/figures.py waveform outputs/<s2_module>  -> docs/s2_waveform.png  (iverilog+vvp VCD of the
                                                          agent-generated S2 RTL, matplotlib)
  python tools/figures.py netlist  outputs/<s1_module>  -> docs/s1_netlist.svg   (yosys `show -format svg`)
  python tools/figures.py table                        -> prints the S1-S4 hardware table (Markdown)

Needs native iverilog, vvp, yosys and graphviz (brew install icarus-verilog yosys graphviz).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


# --------------------------------------------------------------------------- S2 FSM
def fsm():
    import graphviz
    g = graphviz.Digraph("s2_fsm", format="png")
    g.attr(rankdir="LR", dpi="300", fontname="Helvetica", nodesep="0.8", ranksep="1.2",
           label="S2 vaccine-fridge alarm FSM (from specs/s2.txt) — transitions evaluated on "
                 "posedge clk; reading conditions only when sample_valid=1", labelloc="t", fontsize="13")
    g.attr("node", fontname="Helvetica", fontsize="11", style="filled")
    g.attr("edge", fontname="Helvetica", fontsize="9")
    g.node("rst", "rst_n=0\n(async)", shape="plaintext", style="")
    g.node("N", "NORMAL\nstate=0\nalarm=0", shape="circle", fillcolor="#e6f4ea", color="#0f9d58")
    g.node("S", "SUSPECT\nstate=1\nalarm=0", shape="circle", fillcolor="#fef7e0", color="#f4b400")
    g.node("E", "ALARM_\nEXCURSION\nstate=2\nalarm=1", shape="doublecircle", fillcolor="#fdecea",
           color="#db4437")
    g.node("F", "ALARM_\nFREEZE\nstate=3\nalarm=1", shape="doublecircle", fillcolor="#e8f0fe",
           color="#4285f4")
    g.edge("rst", "N", label="bad_count=0", style="dashed")
    g.edge("N", "N", label="in range: 4 ≤ temp ≤ 16 LSB\n(2–8 °C) or no sample")
    g.edge("N", "S", label="bad (temp<4 or >16 LSB), not freezing\nbad_count=1")
    g.edge("N", "F", label="freezing (temp ≤ 0 LSB = 0 °C)")
    g.edge("S", "S", label="bad, bad_count+1 < 3\nbad_count++")
    g.edge("S", "E", label="bad and bad_count reaches 3")
    g.edge("S", "F", label="freezing (temp ≤ 0 LSB = 0 °C)")
    g.edge("S", "N", label="in range\nbad_count=0")
    g.edge("E", "N", label="ack=1\nbad_count=0", color="#db4437")
    g.edge("F", "N", label="ack=1\nbad_count=0", color="#4285f4")
    g.edge("E", "E", label="readings ignored\nbad_count held")
    g.edge("F", "F", label="readings ignored\nbad_count held")
    g.render(DOCS / "s2_fsm", cleanup=True)
    print("wrote docs/s2_fsm.png")


# --------------------------------------------------------------------------- device block diagram
def device():
    import graphviz
    g = graphviz.Digraph("device", format="png")
    g.attr(rankdir="LR", dpi="300", fontname="Helvetica", nodesep="0.5", ranksep="0.7",
           label="FrostByte cold-chain logger: where the generated RTL sits (concept device; "
                 "only the digital block is generated and verified here)", labelloc="t", fontsize="13")
    g.attr("node", fontname="Helvetica", fontsize="11", shape="box", style="rounded,filled",
           fillcolor="white")
    g.attr("edge", fontname="Helvetica", fontsize="9")
    g.node("sensor", "Temperature sensor\n(thermistor / RTD)\nin vaccine fridge", fillcolor="#e8f0fe")
    g.node("adc", "8-bit ADC\nsigned two's complement\n0.5 °C / LSB\n(-64 … +63.5 °C)", fillcolor="#e8f0fe")
    with g.subgraph(name="cluster_chip") as c:
        c.attr(label="FrostByte chip (agent-generated, simulated + synthesized)", style="filled,rounded",
               fillcolor="#e6f4ea", color="#0f9d58", fontcolor="#0f9d58")
        c.node("fsm", "Rule FSM / counters\n(S1–S4 RTL)\ntemp[7:0], sample_valid,\nack → alarm, state",
               fillcolor="white", color="#0f9d58")
    g.node("xtal", "32.768 kHz\ncrystal", shape="ellipse", fillcolor="#fef7e0")
    g.node("coin", "CR2032\ncoin cell\n~3 V, ~220 mAh", shape="ellipse", fillcolor="#fef7e0")
    g.node("led", "Red LED", fillcolor="#fdecea")
    g.node("buzz", "Buzzer", fillcolor="#fdecea")
    g.node("log", "Logging MCU / BLE\n(excursion record\nfor audit)", fillcolor="#f1f3f4")
    g.node("btn", "Operator\nACK button", fillcolor="#f1f3f4")
    g.edge("sensor", "adc", label="analog")
    g.edge("adc", "fsm", label="temp[7:0]\nsample_valid")
    g.edge("xtal", "fsm", label="clk")
    g.edge("coin", "fsm", label="VDD (budget ≤100 nW\nfor the logic)", style="dashed")
    g.edge("btn", "fsm", label="ack")
    g.edge("fsm", "led", label="alarm")
    g.edge("fsm", "buzz", label="alarm")
    g.edge("fsm", "log", label="alarm, state[1:0]")
    g.render(DOCS / "device_block_diagram", cleanup=True)
    print("wrote docs/device_block_diagram.png")


# --------------------------------------------------------------------------- S2 waveform
WAVE_TB = """`timescale 1ns/1ps
module wave_tb;
  reg clk = 0, rst_n = 0, sample_valid = 0, ack = 0;
  reg signed [7:0] temp = 8'sd10;
  wire alarm; wire [1:0] state; wire [3:0] bad_count;
  {top} dut(.clk(clk), .rst_n(rst_n), .sample_valid(sample_valid), .temp(temp), .ack(ack),
            .alarm(alarm), .state(state), .bad_count(bad_count));
  always #5 clk = ~clk;
  task sample(input signed [7:0] t);
    begin @(negedge clk); temp = t; sample_valid = 1; @(negedge clk); sample_valid = 0; end
  endtask
  initial begin
    $dumpfile("wave.vcd"); $dumpvars(0, wave_tb);
    #12 rst_n = 1;
    sample(8'sd10);      // 5.0 C  in range  -> NORMAL
    sample(8'sd20);      // 10.0 C bad       -> SUSPECT, bad_count=1
    sample(8'sd21);      // bad              -> bad_count=2
    sample(8'sd22);      // bad              -> bad_count=3 -> ALARM_EXCURSION
    sample(8'sd10);      // ignored in ALARM
    @(negedge clk); ack = 1; @(negedge clk); ack = 0;   // operator ack -> NORMAL
    sample(8'sd10);      // in range -> NORMAL
    repeat (3) @(negedge clk);
    $finish;
  end
endmodule
"""


def _vcd_parse(path):
    """Minimal VCD reader -> {signal_name: [(time, int_value or None)]} for wave_tb scope."""
    ids, sig, t, scope = {}, {}, 0, []
    for line in open(path):
        line = line.strip()
        if line.startswith("$scope"):
            scope.append(line.split()[2])
        elif line.startswith("$upscope"):
            scope.pop()
        elif line.startswith("$var") and scope == ["wave_tb"]:
            p = line.split()
            ids.setdefault(p[3], p[4])
            sig[p[4]] = []
        elif line.startswith("#"):
            t = int(line[1:])
        elif line and line[0] in "01xz" and line[1:] in ids:
            sig[ids[line[1:]]].append((t, None if line[0] in "xz" else int(line[0])))
        elif line.startswith("b"):
            v, i = line[1:].split()
            if i in ids:
                sig[ids[i]].append((t, None if re.search("[xz]", v) else int(v, 2)))
    return sig


def waveform(outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir = Path(outdir)
    rtl = (outdir / "design.v").read_text()
    top = re.search(r"^\s*module\s+(\w+)", rtl, re.M).group(1)
    with tempfile.TemporaryDirectory() as d:
        Path(d, "design.v").write_text(rtl)
        Path(d, "wave_tb.v").write_text(WAVE_TB.replace("{top}", top))
        subprocess.run(["iverilog", "-g2012", "-o", "sim.vvp", "design.v", "wave_tb.v"], cwd=d, check=True)
        subprocess.run(["vvp", "-n", "sim.vvp"], cwd=d, check=True, capture_output=True)
        shutil.copy(Path(d, "wave.vcd"), outdir / "wave_demo.vcd")
        sig = _vcd_parse(Path(d, "wave.vcd"))
    t_end = max(t for s in sig.values() for t, _ in s)
    names = ["clk", "rst_n", "sample_valid", "temp", "ack", "state", "bad_count", "alarm"]
    state_names = {0: "NORMAL", 1: "SUSPECT", 2: "ALARM_EXC", 3: "ALARM_FRZ"}
    fig, axes = plt.subplots(len(names), 1, figsize=(13, 7.5), sharex=True, dpi=200)
    for ax, n in zip(axes, names):
        pts = sig[n] + [(t_end, sig[n][-1][1])]
        xs = [p[0] / 1000 for p in pts]
        ys = [p[1] if p[1] is not None else 0 for p in pts]
        bus = n in ("temp", "state", "bad_count")
        if not bus:
            ax.step(xs, ys, where="post", color="#db4437" if n == "alarm" else "#1a73e8", lw=1.2)
            ax.set_ylim(-0.3, 1.3)
            ax.set_yticks([])
        else:
            for (x0, v), (x1, _) in zip(pts, pts[1:]):
                if x1 == x0:
                    continue
                ax.fill_between([x0 / 1000, x1 / 1000], 0.1, 0.9, color="#e6f4ea" if n == "state" else "#f1f3f4",
                                edgecolor="#5f6368", lw=0.8)
                if v is None:
                    label = "x"
                elif n == "temp":
                    sv = v - 256 if v > 127 else v
                    label = f"{sv} ({sv / 2:g}°C)"
                elif n == "state":
                    label = state_names.get(v, str(v))
                else:
                    label = str(v)
                if (x1 - x0) / t_end > 0.03:
                    ax.text((x0 + x1) / 2000, 0.5, label, ha="center", va="center", fontsize=7)
            ax.set_ylim(0, 1)
            ax.set_yticks([])
        ax.set_ylabel(n, rotation=0, ha="right", va="center", fontsize=9)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[-1].set_xlabel("time (µs of testbench time; 10 ns clock)")
    fig.suptitle(f"S2 `{top}` — real iverilog/vvp simulation of the agent-generated RTL: "
                 "NORMAL → SUSPECT → ALARM_EXCURSION → ack → NORMAL", fontsize=11)
    fig.tight_layout()
    fig.savefig(DOCS / "s2_waveform.png")
    print("wrote docs/s2_waveform.png  (VCD kept at", outdir / "wave_demo.vcd", ")")


# --------------------------------------------------------------------------- S1 netlist schematic
def netlist(outdir):
    outdir = Path(outdir)
    rtl = (outdir / "design.v").read_text()
    top = re.search(r"^\s*module\s+(\w+)", rtl, re.M).group(1)
    with tempfile.TemporaryDirectory() as d:
        Path(d, "design.v").write_text(rtl)
        script = (f"read_verilog design.v; synth -top {top}; abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; "
                  f"opt_clean; stat; show -format svg -prefix s1_netlist -width -stretch {top}")
        r = subprocess.run(["yosys", "-q", "-p", script], cwd=d, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr)
        shutil.copy(Path(d, "s1_netlist.svg"), DOCS / "s1_netlist.svg")
    print("wrote docs/s1_netlist.svg")


# --------------------------------------------------------------------------- hardware table
def table():
    rows = []
    for sid in ("S1", "S2", "S3", "S4"):
        best = None
        for m in sorted((ROOT / "outputs").glob("*/metrics.json")):
            if m.parent.name.startswith("mock_"):
                continue
            d = json.loads(m.read_text())
            if d.get("spec") == sid and d.get("ok") and not d.get("mock"):
                best = (m.parent.name, d)
        rows.append((sid, best))
    print("| Spec | Module | Cells | DFFs | Area (GE) | Power (nW) | Budget (nW) | Within budget |")
    print("|---|---|---|---|---|---|---|---|")
    for sid, b in rows:
        if not b:
            print(f"| {sid} | _TBD: run Phase 5 benchmark_ | | | | | | |")
            continue
        n, d = b
        print(f"| {sid} | `{n}` | {d['cells']} | {d['dffs']} | {d['area_ge']} | {d['power_nw']} | "
              f"{d.get('budget_nw')} | {'yes' if d['within_budget'] else 'no'} |")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"fsm": fsm, "device": device, "table": table}.get(cmd, lambda: None)() if cmd in ("fsm", "device", "table") \
        else {"waveform": waveform, "netlist": netlist}[cmd](sys.argv[2])
