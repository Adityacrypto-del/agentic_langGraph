"""Architecture diagrams for FrostByte (LangChain edition).

  python -m langchain_app.diagram

Writes to docs/:
  langchain_runnable_graph.mmd   what LangChain itself reports: frostbyte.get_graph().draw_mermaid()
  langchain_workflow.mmd         hand-drawn Mermaid of the 4-lane workflow
  langchain_workflow.svg / .png  Graphviz, 300 dpi, 4 lanes (DESIGN / VERIFY / IMPLEMENT / REPORT),
                                 every box annotated with the LangChain primitive that implements it

Agentic AI concept: OBSERVABILITY / explainability. A composed LCEL Runnable can describe its own
graph, and the hand-drawn view names which primitive gives each agentic behaviour.
"""
from html import escape
from pathlib import Path

import graphviz

from .mock_llm import MockChatModel
from .pipeline import build_pipeline

DOCS = Path(__file__).resolve().parent.parent / "docs"

# (id, label, primitive, lane)
NODES = [
    ("request", "Plain-English\ncold-chain rule", "input", None),
    ("spec_analyst", "spec_analyst", "prompt | llm | parse\n+ output-fixing retry", "DESIGN"),
    ("clarification_gate", "clarification_gate", "RunnableBranch", "DESIGN"),
    ("clarify", "CLARIFICATION NEEDED\n(questions, no RTL)", "RunnableLambda", "DESIGN"),
    ("design_parallel", "design_parallel", "RunnablePassthrough.assign\n(RunnableParallel)", "DESIGN"),
    ("rtl_designer_agent", "rtl_designer_agent", "bind_tools + ReAct loop\n@tool lint_verilog", "DESIGN"),
    ("testbench_writer", "testbench_writer", "prompt | llm | parser\n(spec only guardrail)", "DESIGN"),
    ("verify_debug_loop", "verify_debug_loop", "RunnableLambda(fn, config)\nlint -> sim -> debug", "VERIFY"),
    ("debugger", "debugger (critic)", "prompt | llm.with_retry", "VERIFY"),
    ("sim_gate", "sim passed?", "RunnableBranch", "VERIFY"),
    ("implement_parallel", "implement_parallel", "RunnablePassthrough.assign\n(RunnableParallel)", "IMPLEMENT"),
    ("synthesize", "synthesize", "RunnableLambda -> yosys", "IMPLEMENT"),
    ("power_estimate", "power_estimate", "RunnableLambda -> VCD power", "IMPLEMENT"),
    ("human_approval", "human_approval", "RunnableLambda (input())", "REPORT"),
    ("approved_gate", "approved?", "RunnableBranch", "REPORT"),
    ("report_writer", "report_writer", "prompt | llm | StrOutputParser", "REPORT"),
    ("outputs", "outputs/<module>/\ndesign.v tb.v report.md\nmetrics.json trace.jsonl", "files", None),
]
EDGES = [
    ("request", "spec_analyst", ""), ("spec_analyst", "clarification_gate", ""),
    ("clarification_gate", "clarify", "ambiguous"), ("clarification_gate", "design_parallel", "complete"),
    ("design_parallel", "rtl_designer_agent", "spec"), ("design_parallel", "testbench_writer", "spec"),
    ("rtl_designer_agent", "verify_debug_loop", "rtl"), ("testbench_writer", "verify_debug_loop", "tb"),
    ("verify_debug_loop", "debugger", "fail log"), ("debugger", "verify_debug_loop", "fix (RTL|TB)"),
    ("verify_debug_loop", "sim_gate", ""), ("sim_gate", "implement_parallel", "yes"),
    ("sim_gate", "human_approval", "no (honest fail)"),
    ("implement_parallel", "synthesize", ""), ("implement_parallel", "power_estimate", ""),
    ("synthesize", "human_approval", ""), ("power_estimate", "human_approval", ""),
    ("human_approval", "approved_gate", ""), ("approved_gate", "report_writer", "yes"),
    ("report_writer", "outputs", ""), ("clarify", "outputs", "questions.json"),
]
EDA_EDGES = ["rtl_designer_agent", "verify_debug_loop", "synthesize", "power_estimate"]
LANE_COLOR = {"DESIGN": "#e8f0fe", "VERIFY": "#fdecea", "IMPLEMENT": "#e6f4ea", "REPORT": "#fef7e0"}
NODE_COLOR = {"DESIGN": "#4285f4", "VERIFY": "#db4437", "IMPLEMENT": "#0f9d58", "REPORT": "#f4b400"}


def runnable_graph_mermaid() -> str:
    return build_pipeline(MockChatModel()).get_graph().draw_mermaid()


def graphviz_workflow() -> graphviz.Digraph:
    g = graphviz.Digraph("frostbyte", format="png")
    g.attr(rankdir="TB", fontname="Helvetica", nodesep="0.35", ranksep="0.45", compound="true",
           label="FrostByte — LangChain edition: one composed LCEL Runnable "
                 "(box = step, small text = LangChain primitive)", labelloc="t", fontsize="16")
    g.attr("node", fontname="Helvetica", fontsize="11", shape="box", style="rounded,filled")
    g.attr("edge", fontname="Helvetica", fontsize="9", color="#555555")
    for lane in ("DESIGN", "VERIFY", "IMPLEMENT", "REPORT"):
        with g.subgraph(name=f"cluster_{lane}") as c:
            c.attr(label=lane, style="filled,rounded", fillcolor=LANE_COLOR[lane],
                   color=NODE_COLOR[lane], fontsize="14", fontcolor=NODE_COLOR[lane])
            for nid, label, prim, ln in NODES:
                if ln != lane:
                    continue
                shape = "diamond" if prim == "RunnableBranch" else "box"
                html = (f"<<b>{escape(label).replace(chr(10), '<br/>')}</b><br/>"
                        f"<font point-size='9' color='#444444'>"
                        f"{escape(prim).replace(chr(10), '<br/>')}</font>>")
                c.node(nid, html, shape=shape, fillcolor="white", color=NODE_COLOR[lane])
    for nid, label, prim, ln in NODES:
        if ln is None:
            g.node(nid, label, shape="note", fillcolor="#f1f3f4", color="#888888")
    for a, b, lbl in EDGES:
        g.edge(a, b, label=lbl)
    g.node("eda", "<<b>EDA tool server</b> (FastAPI, Docker)<br/>"
                  "<font point-size='9'>iverilog lint · vvp sim · yosys synth · VCD power</font>>",
           shape="cylinder", fillcolor="#ede7f6", color="#673ab7")
    for n in EDA_EDGES:
        g.edge(n, "eda", style="dashed", color="#673ab7", arrowhead="none", constraint="false")
    return g


WORKFLOW_MMD = """flowchart TB
  REQ[/"Plain-English cold-chain rule"/]
  subgraph DESIGN["DESIGN"]
    SA["spec_analyst<br/><small>prompt | llm | parse + output-fixing retry</small>"]
    CG{"clarification_gate<br/><small>RunnableBranch</small>"}
    CL["CLARIFICATION NEEDED<br/><small>RunnableLambda</small>"]
    DP["design_parallel<br/><small>RunnablePassthrough.assign</small>"]
    RA["rtl_designer_agent<br/><small>bind_tools ReAct loop + @tool lint_verilog</small>"]
    TW["testbench_writer<br/><small>prompt | llm | parser, spec only</small>"]
  end
  subgraph VERIFY["VERIFY"]
    VL["verify_debug_loop<br/><small>RunnableLambda(fn, config)</small>"]
    DB["debugger (critic)<br/><small>prompt | llm.with_retry</small>"]
    SG{"sim passed?<br/><small>RunnableBranch</small>"}
  end
  subgraph IMPLEMENT["IMPLEMENT"]
    IP["implement_parallel<br/><small>RunnablePassthrough.assign</small>"]
    SY["synthesize<br/><small>RunnableLambda</small>"]
    PW["power_estimate<br/><small>RunnableLambda</small>"]
  end
  subgraph REPORT["REPORT"]
    HA["human_approval<br/><small>RunnableLambda</small>"]
    AG{"approved?<br/><small>RunnableBranch</small>"}
    RW["report_writer<br/><small>prompt | llm | StrOutputParser</small>"]
  end
  EDA[("EDA tool server<br/>iverilog / vvp / yosys / power")]
  OUT[/"outputs/&lt;module&gt;/"/]
  REQ --> SA --> CG
  CG -- ambiguous --> CL --> OUT
  CG -- complete --> DP
  DP -- spec --> RA & TW
  RA -- rtl --> VL
  TW -- tb --> VL
  VL -- fail log --> DB -- fix --> VL
  VL --> SG
  SG -- yes --> IP --> SY & PW
  SY & PW --> HA
  SG -- no --> HA
  HA --> AG -- yes --> RW --> OUT
  RA -.-> EDA
  VL -.-> EDA
  SY -.-> EDA
  PW -.-> EDA
  classDef design fill:#e8f0fe,stroke:#4285f4
  classDef verify fill:#fdecea,stroke:#db4437
  classDef impl fill:#e6f4ea,stroke:#0f9d58
  classDef report fill:#fef7e0,stroke:#f4b400
  class SA,CG,CL,DP,RA,TW design
  class VL,DB,SG verify
  class IP,SY,PW impl
  class HA,AG,RW report
"""


def main():
    DOCS.mkdir(exist_ok=True)
    (DOCS / "langchain_runnable_graph.mmd").write_text(runnable_graph_mermaid())
    (DOCS / "langchain_workflow.mmd").write_text(WORKFLOW_MMD)
    g = graphviz_workflow()
    g.attr(dpi="300")
    g.render(DOCS / "langchain_workflow", format="png", cleanup=True)
    g.attr(dpi="96")
    g.render(DOCS / "langchain_workflow", format="svg", cleanup=True)
    for f in ("langchain_runnable_graph.mmd", "langchain_workflow.mmd", "langchain_workflow.png",
              "langchain_workflow.svg"):
        print("wrote docs/" + f)


if __name__ == "__main__":
    main()
