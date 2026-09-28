"""
TrendPilot web demo.

    streamlit run app/streamlit_app.py

The CLI in demo.py already satisfies the brief's demo requirement; this exists
because the agent's *process* is the interesting part and a terminal scroll
hides it. Here the plan, each tool call, and the reviewer's verdict are shown as
they happen, so a viewer can see the agent deciding rather than just its output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from agent import TrendPilotAgent          # noqa: E402
from memory import Memory                  # noqa: E402
from ollama_client import OllamaClient     # noqa: E402
import tools as toolmod                    # noqa: E402

PLATFORMS = ["LinkedIn", "Instagram", "X", "YouTube Shorts", "TikTok", "Facebook"]
TONES = ["professional and exciting", "motivational", "funny", "humorous",
         "short and catchy", "inspirational", "meme style"]
OUTPUT_TYPES = ["post", "post and hashtags", "reel script",
                "post and reel script", "full content plan"]

st.set_page_config(page_title="TrendPilot", page_icon="🚀", layout="wide")


class StreamlitAgent(TrendPilotAgent):
    """Mirror the agent's trace into the page as it runs."""

    def __init__(self, *a, sink=None, **kw):
        super().__init__(*a, **kw)
        self.sink = sink
        self.lines: list[str] = []

    def _say(self, text):
        super()._say(text)
        if self.sink is not None and text.strip():
            self.lines.append(text)
            self.sink.code("\n".join(self.lines[-28:]), language="text")


st.title("🚀 TrendPilot")
st.caption("A local agentic AI content assistant — Ollama + Gemma 3:4B. "
           "AIRI Team PITB, AI Internship Task 2.")

with st.sidebar:
    st.header("Settings")
    model = st.text_input("Ollama model", value="gemma3:4b")

    client = OllamaClient(model=model)
    if client.is_up():
        installed = client.available_models()
        st.success("Ollama is running")
        st.caption("Installed: " + ", ".join(installed))
        if model not in installed:
            st.warning(f"`{model}` is not installed — the agent will fall back "
                       f"to `{client.resolve_model()}`.")
    else:
        st.error("Ollama is not running on http://localhost:11434")
        st.stop()

    st.divider()
    st.subheader("The agent's tools")
    for t in toolmod.REGISTRY.values():
        st.caption(f"**{t.name}** — {t.description}"
                   + ("" if t.uses_llm else "  ·  *no model call*"))

    st.divider()
    mem_stats = Memory().stats()
    st.subheader("Memory")
    if mem_stats.get("runs"):
        st.metric("Previous runs", mem_stats["runs"])
        if mem_stats.get("mean_review_score") is not None:
            st.metric("Mean reviewer score", f"{mem_stats['mean_review_score']}/5")
    else:
        st.caption("No runs recorded yet.")

left, right = st.columns([1, 1])
with left:
    topic = st.text_area(
        "What is your topic?", height=90,
        placeholder="e.g. YOLOv8 helmet detection system for motorcycle riders")
    c1, c2 = st.columns(2)
    platform = c1.selectbox("Platform", PLATFORMS)
    tone = c2.selectbox("Tone", TONES)
    output_type = st.selectbox("What do you want?", OUTPUT_TYPES, index=1)
    go = st.button("Generate", type="primary", use_container_width=True)

with right:
    st.subheader("Agent trace")
    st.caption("The agent plans its own tool sequence — it is not a fixed pipeline.")
    trace_box = st.empty()
    trace_box.code("Waiting for a topic…", language="text")

if go:
    if not topic.strip():
        st.warning("Enter a topic first.")
        st.stop()

    agent = StreamlitAgent(model=model, verbose=False, sink=trace_box)
    with st.spinner("The agent is working — a local 4B model takes a minute or two…"):
        try:
            ctx = agent.run(topic=topic.strip(), platform=platform, tone=tone,
                            output_type=output_type)
        except Exception as exc:                       # noqa: BLE001
            st.error(f"The run failed: {exc}")
            st.stop()

    st.divider()
    m = st.columns(4)
    m[0].metric("Tools called", len(ctx.get("tools_used", [])))
    review = ctx.get("review") or {}
    m[1].metric("Reviewer", review.get("verdict", "—"),
                delta=f"{review.get('average', '—')}/5")
    m[2].metric("Revised", "yes" if ctx.get("revised") else "no")
    m[3].metric("Time", f"{ctx.get('elapsed_seconds', 0)}s")

    if ctx.get("tool_errors"):
        st.warning("Some tools failed; the agent saved what it had. "
                   + "; ".join(f"{e['tool']}: {e['error'][:80]}"
                               for e in ctx["tool_errors"]))

    tabs = st.tabs(["Result", "Reviewer", "Raw JSON"])
    with tabs[0]:
        st.markdown(toolmod.render_markdown(ctx))
        if ctx.get("caption"):
            st.text_area("Copy the caption", ctx["caption"], height=170)
        if ctx.get("hashtags"):
            st.code(" ".join(ctx["hashtags"]), language="text")
    with tabs[1]:
        if review:
            if review.get("scores"):
                st.table([{"check": k, "score": f"{v}/5"}
                          for k, v in review["scores"].items()])
            for label, key in (("Problems", "problems"), ("Fixes", "fixes")):
                if review.get(key):
                    st.markdown(f"**{label}**")
                    for item in review[key]:
                        st.markdown(f"- {item}")
            if ctx.get("caption_original"):
                with st.expander("The post before revision"):
                    st.text(ctx["caption_original"])
        else:
            st.caption("The reviewer did not run.")
    with tabs[2]:
        st.json({k: v for k, v in ctx.items() if k != "angles"})

    if ctx.get("saved_markdown"):
        st.success(f"Saved to `{ctx['saved_markdown']}`")
        st.download_button(
            "Download the markdown",
            Path(ctx["saved_markdown"]).read_text(encoding="utf-8"),
            file_name=Path(ctx["saved_markdown"]).name, mime="text/markdown")
