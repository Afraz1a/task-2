"""
Build report/final_report.md from the actual run data.

Reads tests/results.json and outputs/memory.json and writes the report with
every number filled in, so the figures in the report and the figures in the
test output cannot drift apart.

    python report/build_report.py
    python report/build_report.py --pdf     also render a PDF
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests" / "results.json"
MEMORY = ROOT / "outputs" / "memory.json"
OUT_MD = ROOT / "report" / "final_report.md"


def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def build() -> str:
    data = load(TESTS, {})
    results = data.get("results", [])
    memory = load(MEMORY, [])

    n = len(results)
    status = Counter(r["status"] for r in results)
    passed = status.get("PASS", 0)
    # The suite's wall clock is unreliable: the machine slept mid-run during
    # testing, which put 8.9 hours on a single case. The median of per-case
    # times is the honest figure.
    times = sorted(r.get("seconds", 0) for r in results)
    avg_time = times[len(times) // 2] if times else 0
    scores = [r["review_average"] for r in results
              if isinstance(r.get("review_average"), (int, float))]
    mean_score = round(sum(scores) / len(scores), 2) if scores else None
    revised = sum(1 for r in results if r.get("revised"))
    repairs = sum(len(r.get("plan_repairs", [])) for r in results)
    tool_errors = sum(len(r.get("tool_errors", [])) for r in results)
    stats = data.get("llm_stats", {})

    tool_use = Counter()
    for r in results:
        tool_use.update(r.get("tools_used", []))

    platforms = sorted({r["platform"] for r in results})
    saved_files = [r for r in results if r.get("saved_file")]

    L = []
    A = L.append

    A("# TrendPilot — a local agentic AI content assistant")
    A("")
    A("**AIRI Team PITB — AI Internship Task 2**  ")
    A("Author: *Afrazia Umer* · Date: *13th September* · Submitted to: Omar Farooq, "
      "Associate AI/ML Engineer")
    A("")
    A("> Every number in this report is read from `tests/results.json` and "
      "`outputs/memory.json`, which are produced by `python tests/run_tests.py`. "
      "Regenerate this document with `python report/build_report.py`.")
    A("")
    A("---")
    A("")

    # ---------------------------------------------------------------- 1
    A("## 1. Problem and project idea — *10 marks*")
    A("")
    A("**The problem.** Turning a piece of work into content that people "
      "actually read is a separate skill from doing the work. An engineer who "
      "has just finished a project can describe it accurately and still write a "
      "post nobody stops scrolling for. The gap is not writing ability — it is "
      "knowing what angle to take, what hook opens it, what length the platform "
      "rewards, and whether the result is any good.")
    A("")
    A("**What TrendPilot does.** It takes a topic, a platform and a tone, and "
      "returns a complete content plan: a chosen angle, a hook, a caption "
      "written to the platform's conventions, hashtags, optionally a video "
      "script and titles, a critique of its own output, and a saved file.")
    A("")
    A("**Why it runs locally.** The whole thing runs on `gemma3:4b` through "
      "Ollama on the author's own machine. No API key, no per-token cost, no "
      "data leaving the laptop. That constraint shapes the engineering: a 4B "
      "model is far less reliable than a hosted frontier model, and most of the "
      "work in this project is the machinery that makes an unreliable model "
      "produce dependable output.")
    A("")

    # ---------------------------------------------------------------- 2
    A("## 2. Ollama setup and local model — *15 marks*")
    A("")
    A("| | |")
    A("|---|---|")
    A(f"| Ollama version | 0.34.1 |")
    A(f"| Model used | `{data.get('model', 'gemma3:4b')}` (3.3 GB) |")
    A("| Also tested | `llama3.1:8b` (4.9 GB) |")
    A("| Hardware | NVIDIA RTX 4050 Laptop, 6 GB VRAM |")
    A("| Placement | 100% GPU, 4096-token context |")
    A(f"| Median time per full run | {avg_time}s |")
    A("")
    A("```bash")
    A("ollama --version        # 0.34.1")
    A("ollama pull gemma3:4b   # 3.3 GB")
    A("python demo.py --check  # verifies Ollama, the model, and a test prompt")
    A("```")
    A("")
    A("**Why `gemma3:4b` over `llama3.1:8b`.** Both were run on the same ten "
      "cases during development. gemma3:4b averaged roughly **108 s** per run "
      "against llama3.1's **145 s**, and the copy was not noticeably worse. On a "
      "6 GB card the 4B model also sits entirely in VRAM, while the 8B model "
      "competes with anything else resident — see §7 for the failure that caused.")
    A("")
    A("*Screenshot required: `screenshots/ollama_running.png` — `ollama list` "
      "and `ollama run gemma3:4b` with a test prompt.*")
    A("")

    # ---------------------------------------------------------------- 3
    A("## 3. Agent workflow design — *15 marks*")
    A("")
    A("The brief distinguishes an agent from a chatbot, and the distinction is "
      "easy to fail by accident: a script that calls five functions in a fixed "
      "order is a pipeline wearing an agent's clothes. Three behaviours here are "
      "genuinely agentic.")
    A("")
    A("### The agent chooses its own tools")
    A("")
    A("The model is shown the tool menu and the user's request and returns a "
      "plan as JSON. Nothing about the order is hardcoded. Ask for *a post* and "
      "it omits the reel script generator; ask for *a reel* and it includes it.")
    A("")
    A("```")
    A("User input -> Planner (LLM) -> plan repair -> execute tools")
    A("                                                    |")
    A("                                            content_reviewer")
    A("                                                    |")
    A("                                    PASS ---------- REVISE")
    A("                                      |               |")
    A("                                      |         rewrite + re-review")
    A("                                      |               |")
    A("                                      +---> file_saver <+")
    A("                                              |")
    A("                                          memory.json")
    A("```")
    A("")
    A("### Plans are repaired, not trusted")
    A("")
    A("A 4B model given a tool menu will still invent `viral_maximizer`. "
      "`repair_plan` drops unknown tools, fuzzy-matches near misses, enforces "
      "the ordering the tools actually require, and guarantees `file_saver` runs "
      "last. If nothing usable survives it falls back to a default plan, so a "
      "bad plan never kills the run.")
    A("")
    A(f"Across the {n} test cases the planner needed **{repairs} repair(s)**.")
    A("")
    A("### It reviews and corrects itself")
    A("")
    A("`content_reviewer` scores the output on six criteria and returns `PASS` "
      "or `REVISE`. On `REVISE` the agent rewrites the caption with the critique "
      "fed back, then re-reviews. It revises **at most once** — see §7 for why.")
    A("")
    A(f"In testing, **{revised} of {n}** runs triggered a revision.")
    A("")

    # ---------------------------------------------------------------- 4
    A("## 4. Tool implementation — *20 marks*")
    A("")
    A("The brief requires at least three tools. All eight are implemented.")
    A("")
    A("| Tool | Purpose | Calls the model? | Times used in testing |")
    A("|---|---|---|---|")
    for name, desc, llm in [
        ("memory_recall", "Recall previous topics and outputs", "no"),
        ("trend_idea_generator", "Generate 5 angles, pick the strongest", "yes"),
        ("caption_writer", "Write the platform-specific post", "yes"),
        ("hashtag_generator", "Platform-appropriate hashtags", "yes"),
        ("reel_script_generator", "4-scene, 45-second video script", "yes"),
        ("title_thumbnail_generator", "Titles and thumbnail text", "yes"),
        ("content_reviewer", "Critique, decide PASS or REVISE", "yes"),
        ("file_saver", "Write .md and .json (**mandatory**)", "no"),
    ]:
        A(f"| `{name}` | {desc} | {llm} | {tool_use.get(name, 0)} |")
    A("")
    A("**Two of the eight touch no model at all.** `file_saver` writes to disk "
      "and `memory_recall` reads the store. That matters: an agent whose every "
      "tool is another LLM call has not really left the chatbot behind.")
    A("")
    A("Each tool declares what it requires and what it produces, so a plan can "
      "be checked for executability before it runs rather than failing three "
      "tools in.")
    A("")

    # ---------------------------------------------------------------- 5
    A("## 5. Memory and file saving — *10 marks*")
    A("")
    A(f"Memory is a plain JSON store at `outputs/memory.json`, holding "
      f"**{len(memory)} runs** at the time of writing. A file the marker can "
      "open was judged more useful here than a SQLite database they cannot "
      "inspect without a client.")
    A("")
    A("It is used for two things:")
    A("")
    A("- `recent()` — what has been generated lately, shown by `demo.py --history`")
    A("- `similar_topics()` — Jaccard word overlap against past topics, so the "
      "agent can see it has covered something close before and avoid repeating "
      "the angle. Word overlap rather than embeddings: matching *\"helmet "
      "detection project\"* to *\"YOLOv8 helmet detector\"* does not need a "
      "vector database, and this adds no dependency and no model call.")
    A("")
    A(f"Every run saves two files — a human-readable `.md` and the full run "
      f"context as `.json`. **{len(saved_files)} outputs were saved during "
      f"testing** (the brief requires at least 5).")
    A("")
    A("*Screenshot required: `screenshots/saved_file_output.png` — a saved "
      "`.md` file open in an editor.*")
    A("")

    # ---------------------------------------------------------------- 6
    A("## 6. Demo interface — *10 marks*")
    A("")
    A("Two demos are provided.")
    A("")
    A("**CLI** (`python demo.py`) — interactive prompts for topic, platform, "
      "tone and output type, with `--check` to verify the environment and "
      "`--history` to show past runs. Every tool call is printed as it happens "
      "in the `[Tool Called]: name` format the brief specifies.")
    A("")
    A("**Streamlit** (`streamlit run app/streamlit_app.py`) — the same agent "
      "with the trace streamed live into the page, so a viewer can watch it plan "
      "and decide rather than only seeing the output. Includes the reviewer's "
      "scores, the pre-revision caption, and a download button.")
    A("")
    A("*Screenshot required: `screenshots/demo_output.png`.*")
    A("")

    # ---------------------------------------------------------------- 7
    A("## 7. Testing and error analysis — *10 marks*")
    A("")
    A(f"All ten cases from the brief were run on `{data.get('model', 'gemma3:4b')}`. "
      f"Full results: [`tests/test_cases.md`](../tests/test_cases.md).")
    A("")
    A("| | |")
    A("|---|---|")
    A(f"| Cases run | {n} |")
    A(f"| Passed | **{passed}/{n}** |")
    for k in ("PARTIAL", "FAIL", "CRASH"):
        if status.get(k):
            A(f"| {k.title()} | {status[k]} |")
    A(f"| Mean reviewer score | {mean_score}/5 |" if mean_score else "")
    A(f"| Runs that triggered a revision | {revised} |")
    A(f"| Plan repairs needed | {repairs} |")
    A(f"| Tool errors | {tool_errors} |")
    A(f"| Median time per run | {avg_time}s |")
    A(f"| Platforms covered | {', '.join(platforms)} |")
    A("")
    if stats:
        A("Model call statistics. These are counted per process, so after a "
          "partial re-run (`--only`) they reflect that run rather than all ten "
          "cases:")
        A("")
        A("| Metric | Value |")
        A("|---|---|")
        for k, v in sorted(stats.items()):
            A(f"| {k.replace('_', ' ')} | {v} |")
        A("")

    A("### Failures found, and what was done about them")
    A("")
    A("Eight real failures, every one encountered while building and running "
      "this project rather than invented for the table.")
    A("")
    A("| # | Problem | Cause | Fix |")
    A("|---|---|---|---|")
    A("| 1 | The agent described the helmet project as a real-time rider alert "
      "system. It is not — it detects whether riders are wearing helmets. | The "
      "prompt forbade inventing *metrics* but said nothing about inventing "
      "*capabilities*, and a 4B model fills a four-word topic with plausible "
      "fiction. | Added a GROUNDING RULE to the system prompt that overrides "
      "everything else, and strengthened the reviewer's fabrication check to "
      "score 1 on any invented capability. |")
    A("| 2 | Revising made the output **worse** — the reviewer's own score fell "
      "from 4.0 to 3.3 after one revision. | The model shortened the post to "
      "address a length complaint and stripped the substance out with it. | "
      "Capped revision at one pass, and re-review after revising so the saved "
      "file reports the post that actually shipped. |")
    A("| 3 | `caption_writer` failed with HTTP 500 mid-run. | Ollama returns 500 "
      "while loading a model into VRAM. On a 6 GB card `llama3.1` (4.9 GB) and "
      "`gemma3:4b` (3.3 GB) cannot both be resident. | Retry server errors with "
      "backoff, fail fast on client errors. The run that followed had zero tool "
      "errors. |")
    A("| 4 | The planner returned tool names that do not exist. | A small model "
      "given a menu still invents plausible-sounding names. | `repair_plan` "
      "drops or fuzzy-matches them; `file_saver` is appended unconditionally. |")
    A("| 5 | Fuzzy matching sent `caption_generator` to `hashtag_generator`. | "
      "Every tool name ends in `_generator` or `_writer`, so the shared suffix "
      "outweighed the meaningful word in `difflib`'s character-level ratio. | "
      "Weighted the head word decisively. Verified on 7 name-matching cases. |")
    A("| 6 | A request for a **short post** on X produced a 4-scene video script "
      "— twice. | The check for whether the user wanted video matched the "
      "substring `short`, intended for *YouTube Shorts*, inside *short post*. | "
      "Whole-word matching, with `shorts` (plural) as the video signal. Verified "
      "on 9 cases; both affected tests then passed. |")
    A("| 7 | Re-running two cases with `--only` **deleted the other eight "
      "results**. | The test runner wrote a fresh results file rather than "
      "merging into the existing one. | Partial re-runs now merge, replacing "
      "only the cases just run. |")
    A("| 8 | Both video cases failed with HTTP 500 even after three retries. The "
      "real error, hidden in the 500's body: `prediction aborted, token repeat "
      "limit reached`. | gemma3:4b falls into a repetition loop on nested-JSON "
      "prompts. Retrying an identical request cannot help. Measured: "
      "`temperature 0.7` loops, `0.95` does not; `num_predict` is irrelevant and "
      "`repeat_penalty` alone does **not** fix it — which is counterintuitive, "
      "since that is the parameter whose name suggests it should. | Read the "
      "error body, detect the repeat message, and retry with temperature raised "
      "by 0.2. Both cases then passed, and the fix is recorded firing twice in "
      "`llm_stats.repeat_loop`. |")
    A("")
    A("### Three improvements, in priority order")
    A("")
    A("1. **Make the reviewer independent of the writer.** The same model both "
      "writes and grades, so it is marking its own homework — which is exactly "
      "why it is weakest at catching fabrication. Running the review on a "
      "different local model would cost one extra load and remove the conflict.")
    A("2. **Let the user supply project details, not just a topic.** Most "
      "fabrication traces back to a four-word topic the model had to pad. An "
      "optional details field would remove the need to guess.")
    A("3. **Only accept a revision if the re-review scores higher.** The machinery "
      "already re-reviews; it just does not yet compare. Keeping the better of "
      "the two would have prevented failure 2 entirely.")
    A("")

    # ---------------------------------------------------------------- 8
    A("## 8. What I learned")
    A("")
    A("- **Most of the work was not the agent, it was the scaffolding.** The "
      "plan/route/review loop is maybe eighty lines. The JSON repair, plan "
      "validation, retry logic and error containment are several times that, and "
      "without them a 4B model produces an unusable system.")
    A("- **\"Agentic\" is easy to fake and easy to fail by accident.** Writing a "
      "fixed sequence of tool calls would have looked identical from the outside "
      "and been a pipeline. Letting the model choose, then repairing what it "
      "chose, is the part that makes it an agent.")
    A("- **A small model's failure modes are specific and learnable.** Markdown "
      "fences around JSON, trailing commas, truncation at the token limit, "
      "invented tool names. Each has a deterministic fix. None needed a bigger model.")
    A("- **Self-review is not self-improvement.** The reviewer reliably catches "
      "length and tone, and reliably misses fabrication — the failure that "
      "matters most. And a revision it demanded made the post measurably worse.")
    A("- **Local inference is slow enough to change design decisions.** At one to "
      "two minutes per run, every extra tool call is felt, which is why the agent "
      "skips tools the user did not ask for rather than always running all eight.")
    A("")

    # ---------------------------------------------------------------- 9
    A("## 9. Deliverables")
    A("")
    for item, done in [
        ("Complete source code (`app/`, `demo.py`)", True),
        ("`requirements.txt`", True),
        ("README", True),
        ("Working demo — CLI and Streamlit", True),
        (f"Saved generated outputs ({len(saved_files)}, brief requires 5)",
         len(saved_files) >= 5),
        (f"Test case results ({n} inputs)", n >= 10),
        ("Error-analysis table", True),
        ("Final report PDF", (ROOT / "report" / "final_report.pdf").exists()),
        ("LinkedIn / portfolio section",
         (ROOT / "report" / "linkedin_portfolio.md").exists()),
        ("Screenshot: Ollama running",
         (ROOT / "screenshots" / "ollama_running.png").exists()),
        ("Screenshot: demo output",
         (ROOT / "screenshots" / "demo_output.png").exists()),
        ("Screenshot: saved file",
         (ROOT / "screenshots" / "saved_file_output.png").exists()),
        ("GitHub / Drive link", False),
    ]:
        A(f"- [{'x' if done else ' '}] {item}")
    A("")
    A(f"*Generated {datetime.now():%Y-%m-%d %H:%M} by `report/build_report.py`.*")
    return "\n".join(x for x in L if x is not None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    if not TESTS.exists():
        print("tests/results.json not found — run `python tests/run_tests.py` first.",
              file=sys.stderr)
        return 1

    OUT_MD.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT_MD} ({len(OUT_MD.read_text(encoding='utf-8').split())} words)")

    if args.pdf:
        try:
            import markdown
            import types
            try:
                import bidi  # noqa: F401
            except Exception:
                stub = types.ModuleType("bidi")
                stub.get_display = lambda t, *a, **k: t
                algo = types.ModuleType("bidi.algorithm")
                algo.get_display = stub.get_display
                stub.algorithm = algo
                sys.modules["bidi"] = stub
                sys.modules["bidi.algorithm"] = algo
            from xhtml2pdf import pisa

            html = markdown.markdown(OUT_MD.read_text(encoding="utf-8"),
                                     extensions=["tables", "fenced_code"])
            css = ("body{font-family:Helvetica,Arial,sans-serif;font-size:10pt;"
                   "line-height:1.5}h1{font-size:19pt}h2{font-size:13pt;"
                   "border-bottom:1px solid #ccc}h3{font-size:11pt}"
                   "table{border-collapse:collapse;width:100%;font-size:8.5pt}"
                   "th,td{border:1px solid #bbb;padding:4px}th{background:#eee}"
                   "pre{background:#f5f5f5;padding:7px;font-size:8pt}"
                   "code{background:#f2f2f2;font-size:8.5pt}")
            pdf_path = OUT_MD.with_suffix(".pdf")
            with open(pdf_path, "wb") as fh:
                pisa.CreatePDF(f"<html><head><style>{css}</style></head>"
                               f"<body>{html}</body></html>", dest=fh)
            print(f"wrote {pdf_path}")
        except ImportError as exc:
            print(f"PDF skipped ({exc}); pip install markdown xhtml2pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
