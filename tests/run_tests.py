"""
Run the ten test cases the brief specifies and record what happened.

    python tests/run_tests.py              all ten
    python tests/run_tests.py --only 1 3   just those cases
    python tests/run_tests.py --model llama3.1:latest

Writes `tests/test_cases.md` (the human-readable results table the brief asks
for) and `tests/results.json` (the raw record, used to build the error-analysis
table). Every case is wrapped so that one failure does not stop the run - a
crashed case is recorded as a failure and the suite continues, because "it threw
an exception" is itself a result worth reporting.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from agent import TrendPilotAgent          # noqa: E402
from ollama_client import STATS            # noqa: E402

# The ten cases from section 16 of the brief, verbatim.
CASES = [
    (1, "YOLOv8 helmet detection", "LinkedIn", "professional", "post and hashtags"),
    (2, "AI internship experience", "LinkedIn", "motivational", "post"),
    (3, "Python learning journey", "Instagram", "funny", "reel script"),
    (4, "Machine learning project", "X", "short and catchy", "short post"),
    (5, "Data annotation struggles", "LinkedIn", "humorous", "post"),
    (6, "Model failed in production", "Instagram", "meme style", "reel script"),
    (7, "Final year project", "LinkedIn", "professional", "portfolio post"),
    (8, "Computer vision project", "YouTube Shorts", "exciting", "video script"),
    (9, "Debugging FastAPI", "X", "funny", "short post"),
    (10, "Open-source contribution", "LinkedIn", "inspirational", "post"),
]


def judge(ctx: dict) -> tuple[str, str]:
    """
    Decide whether a case succeeded, and say why.

    Deliberately mechanical. Whether the copy is *good* is a human judgement and
    belongs in the error analysis; this only checks the agent did its job.
    """
    problems = []
    if ctx.get("tool_errors"):
        problems.append(f"{len(ctx['tool_errors'])} tool error(s)")
    if not ctx.get("saved_markdown"):
        problems.append("nothing saved")

    wants_video = any(w in ctx.get("output_type", "").lower()
                      for w in ("reel", "video", "script"))
    if wants_video and not ctx.get("reel_script"):
        problems.append("asked for a script, none produced")
    if not wants_video and not ctx.get("caption"):
        problems.append("asked for a post, no caption produced")

    review = ctx.get("review") or {}
    if review.get("average") is not None and review["average"] < 3:
        problems.append(f"reviewer scored it {review['average']}/5")

    if not problems:
        return "PASS", "all requested outputs produced and saved"
    return ("PARTIAL" if ctx.get("saved_markdown") else "FAIL"), "; ".join(problems)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma3:4b")
    ap.add_argument("--only", nargs="*", type=int)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cases = [c for c in CASES if not args.only or c[0] in args.only]
    agent = TrendPilotAgent(model=args.model, verbose=not args.quiet)
    results = []

    print(f"\nRunning {len(cases)} test case(s) on {args.model}")
    print("=" * 66)

    suite_started = time.time()
    for num, topic, platform, tone, output_type in cases:
        print(f"\n### Test {num}: {topic} / {platform} / {tone}")
        started = time.time()
        try:
            ctx = agent.run(topic=topic, platform=platform, tone=tone,
                            output_type=output_type)
            status, note = judge(ctx)
            review = ctx.get("review") or {}
            results.append({
                "test": num, "topic": topic, "platform": platform, "tone": tone,
                "output_type": output_type, "status": status, "note": note,
                "tools_used": ctx.get("tools_used", []),
                "tool_errors": ctx.get("tool_errors", []),
                "plan_raw": ctx.get("plan_raw", []),
                "plan_repairs": ctx.get("plan_repairs", []),
                "review_verdict": review.get("verdict"),
                "review_average": review.get("average"),
                "review_problems": review.get("problems", []),
                "revised": bool(ctx.get("revised")),
                "caption_words": len((ctx.get("caption") or "").split()),
                "hashtags": len(ctx.get("hashtags") or []),
                "scenes": len(ctx.get("reel_script") or []),
                "saved_file": ctx.get("saved_markdown"),
                "seconds": round(time.time() - started, 1),
            })
        except Exception as exc:                      # noqa: BLE001
            # A crash is a result. Record it rather than losing the whole suite.
            print(f"  !! case crashed: {exc}")
            traceback.print_exc(limit=2)
            results.append({
                "test": num, "topic": topic, "platform": platform, "tone": tone,
                "output_type": output_type, "status": "CRASH",
                "note": f"{type(exc).__name__}: {exc}",
                "tools_used": [], "tool_errors": [], "plan_repairs": [],
                "seconds": round(time.time() - started, 1),
            })
        print(f"  -> {results[-1]['status']} ({results[-1]['seconds']}s)")

    elapsed = round(time.time() - suite_started, 1)
    out_dir = Path(__file__).resolve().parent

    # A partial re-run (--only) must not wipe the other cases' results. Merge
    # into whatever is already on disk, replacing only the cases just run.
    if args.only:
        previous = []
        results_path = out_dir / "results.json"
        if results_path.exists():
            try:
                previous = json.loads(
                    results_path.read_text(encoding="utf-8")).get("results", [])
            except json.JSONDecodeError:
                previous = []
        rerun = {r["test"] for r in results}
        merged = [r for r in previous if r["test"] not in rerun] + results
        results = sorted(merged, key=lambda r: r["test"])
        print(f"  merged {len(rerun)} re-run case(s) into {len(results)} total")

    payload = {
        "model": args.model,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "total_seconds": elapsed,
        "llm_stats": dict(STATS),
        "results": results,
    }
    (out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "test_cases.md").write_text(render(payload), encoding="utf-8")

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n" + "=" * 66)
    print(f"  {len(results)} cases in {elapsed}s  ->  "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"  tests/test_cases.md and tests/results.json written")
    return 0


def render(payload: dict) -> str:
    rs = payload["results"]
    ok = sum(1 for r in rs if r["status"] == "PASS")
    L = [
        "# Test cases",
        "",
        f"**Model:** `{payload['model']}`  ",
        f"**Run at:** {payload['run_at']}  ",
        f"**Total time:** {payload['total_seconds']}s "
        f"({round(payload['total_seconds'] / max(len(rs), 1), 1)}s per case)  ",
        f"**Result:** {ok}/{len(rs)} passed",
        "",
        "`PASS` means the agent produced and saved every output that was asked "
        "for, with no tool errors and a reviewer score of 3 or above. `PARTIAL` "
        "means a file was still saved but something was missing. Whether the "
        "copy reads *well* is a separate, human judgement - see the error "
        "analysis in the report.",
        "",
        "| # | Topic | Platform | Tone | Asked for | Tools used | Result | Review | Saved |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rs:
        tools = ", ".join(t.replace("_generator", "").replace("_", " ")
                          for t in r.get("tools_used", [])) or "-"
        saved = Path(r["saved_file"]).name if r.get("saved_file") else "-"
        rev = (f"{r.get('review_verdict')} {r.get('review_average')}/5"
               if r.get("review_verdict") else "-")
        L.append(f"| {r['test']} | {r['topic']} | {r['platform']} | {r['tone']} "
                 f"| {r['output_type']} | {tools} | **{r['status']}** | {rev} "
                 f"| `{saved}` |")

    L += ["", "## Per-case detail", ""]
    for r in rs:
        L += [f"### Test {r['test']} — {r['topic']}", "",
              f"- **Input:** platform `{r['platform']}`, tone `{r['tone']}`, "
              f"asked for `{r['output_type']}`",
              f"- **Plan the model proposed:** `{r.get('plan_raw') or 'n/a'}`"]
        if r.get("plan_repairs"):
            L.append(f"- **Plan repairs applied:** {'; '.join(r['plan_repairs'])}")
        L += [f"- **Tools called:** {', '.join(r.get('tools_used', [])) or 'none'}",
              f"- **Output size:** {r.get('caption_words', 0)} caption words, "
              f"{r.get('hashtags', 0)} hashtags, {r.get('scenes', 0)} scenes",
              f"- **Reviewer:** {r.get('review_verdict', '-')} "
              f"(avg {r.get('review_average', '-')}/5)"
              + (", revised once" if r.get("revised") else ""),
              f"- **Time:** {r['seconds']}s",
              f"- **Result:** {r['status']} — {r['note']}"]
        if r.get("review_problems"):
            L.append("- **Reviewer flagged:** "
                     + "; ".join(str(p) for p in r["review_problems"][:3]))
        if r.get("tool_errors"):
            L.append("- **Tool errors:** "
                     + "; ".join(f"{e['tool']}: {e['error'][:90]}"
                                 for e in r["tool_errors"]))
        L.append("")

    stats = payload.get("llm_stats", {})
    if stats:
        L += ["## Model call statistics", "",
              "| Metric | Value |", "|---|---|"]
        L += [f"| {k.replace('_', ' ')} | {v} |" for k, v in sorted(stats.items())]
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
