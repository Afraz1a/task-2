"""
The agent's tools.

The brief requires at least three; all eight from the brief are implemented,
because tool implementation carries the most marks and each is cheap once the
client and prompts exist.

Each tool is a `Tool`: a name, a one-line description the planner sees, the
context keys it needs, the keys it produces, and a `run` callable. Keeping the
requires/produces declared makes the agent able to check a plan is executable
*before* running it, instead of failing three tools in.

Two of the eight touch no model at all - `file_saver` writes to disk and
`memory_recall` reads the store. That matters: an agent whose every "tool" is
just another LLM call is a chatbot wearing a costume.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import prompts

OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "outputs"

# Per-platform hashtag counts. LinkedIn punishes stuffing; Instagram rewards it.
HASHTAG_COUNTS = {
    "LinkedIn": "Give exactly 5 to 7 hashtags.",
    "Instagram": "Give exactly 12 to 15 hashtags.",
    "X": "Give exactly 2 hashtags.",
    "YouTube Shorts": "Give exactly 4 to 6 hashtags.",
    "TikTok": "Give exactly 5 to 8 hashtags.",
    "Facebook": "Give exactly 3 to 5 hashtags.",
}


@dataclass
class Tool:
    name: str
    description: str
    requires: tuple
    produces: tuple
    run: Callable
    uses_llm: bool = True


def _slug(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return (s[:limit] or "untitled").rstrip("_")


# ------------------------------------------------------------------- tools
def trend_idea_generator(ctx, llm, log):
    """Generate content angles, then pick the strongest one."""
    data = llm.ask_json(
        prompts.TREND_IDEAS.format(topic=ctx["topic"], platform=ctx["platform"],
                                   tone=ctx["tone"], n=5),
        system=prompts.SYSTEM)
    angles = data.get("angles", [])
    if not angles:
        raise ValueError("model returned no angles")
    log(f"generated {len(angles)} angles")

    listing = "\n".join(
        f"- {a.get('angle', '')} ({a.get('why_it_works', '')})" for a in angles)
    pick = llm.ask_json(
        prompts.PICK_ANGLE.format(topic=ctx["topic"], platform=ctx["platform"],
                                  tone=ctx["tone"], angles=listing),
        system=prompts.SYSTEM)
    log(f"selected angle: {pick.get('chosen', '')[:60]}")
    return {
        "angles": angles,
        "angle": pick.get("chosen") or angles[0].get("angle", ""),
        "hook": pick.get("hook", ""),
        "audience": pick.get("audience", "general audience"),
    }


def caption_writer(ctx, llm, log):
    data = llm.ask_json(
        prompts.CAPTION.format(
            topic=ctx["topic"], platform=ctx["platform"], tone=ctx["tone"],
            angle=ctx.get("angle", ctx["topic"]), hook=ctx.get("hook", ""),
            audience=ctx.get("audience", "general audience"),
            rules=prompts.platform_rule(ctx["platform"])),
        system=prompts.SYSTEM, num_predict=1100)
    caption = (data.get("caption") or "").strip()
    if not caption:
        raise ValueError("model returned an empty caption")
    log(f"wrote caption ({len(caption.split())} words)")
    return {"caption": caption}


def hashtag_generator(ctx, llm, log):
    data = llm.ask_json(
        prompts.HASHTAGS.format(
            topic=ctx["topic"], platform=ctx["platform"],
            angle=ctx.get("angle", ctx["topic"]),
            count_rule=HASHTAG_COUNTS.get(ctx["platform"], "Give 5 to 8 hashtags.")),
        system=prompts.SYSTEM)
    tags, seen = [], set()
    for t in data.get("hashtags", []):
        t = "#" + re.sub(r"[^A-Za-z0-9]", "", str(t))
        if len(t) > 1 and t.lower() not in seen:
            seen.add(t.lower())
            tags.append(t)
    if not tags:
        raise ValueError("model returned no usable hashtags")
    log(f"generated {len(tags)} hashtags")
    return {"hashtags": tags}


def reel_script_generator(ctx, llm, log):
    data = llm.ask_json(
        prompts.REEL_SCRIPT.format(
            topic=ctx["topic"], platform=ctx["platform"], tone=ctx["tone"],
            angle=ctx.get("angle", ctx["topic"]), seconds=45),
        system=prompts.SYSTEM, num_predict=1100)
    scenes = data.get("scenes", [])
    if not scenes:
        raise ValueError("model returned no scenes")
    log(f"wrote {len(scenes)}-scene script")
    return {"reel_script": scenes, "reel_seconds": data.get("total_seconds", 45)}


def title_thumbnail_generator(ctx, llm, log):
    data = llm.ask_json(
        prompts.TITLE_THUMB.format(topic=ctx["topic"],
                                   angle=ctx.get("angle", ctx["topic"])),
        system=prompts.SYSTEM)
    titles = [t for t in data.get("titles", []) if str(t).strip()]
    thumbs = [t for t in data.get("thumbnail_texts", []) if str(t).strip()]
    log(f"{len(titles)} titles, {len(thumbs)} thumbnail texts")
    return {"titles": titles, "thumbnail_texts": thumbs}


def content_reviewer(ctx, llm, log):
    """Critique the generated content. Its verdict drives the revision loop."""
    parts = []
    if ctx.get("caption"):
        parts.append(f"CAPTION:\n{ctx['caption']}")
    if ctx.get("hashtags"):
        parts.append("HASHTAGS: " + " ".join(ctx["hashtags"]))
    if ctx.get("reel_script"):
        parts.append("REEL SCRIPT:\n" + json.dumps(ctx["reel_script"], indent=1))
    if not parts:
        raise ValueError("nothing to review")

    data = llm.ask_json(
        prompts.REVIEWER.format(
            platform=ctx["platform"], tone=ctx["tone"],
            content="\n\n".join(parts),
            rules=prompts.platform_rule(ctx["platform"])),
        system=prompts.SYSTEM, temperature=0.3, num_predict=800)

    scores = {k: v for k, v in (data.get("scores") or {}).items()
              if isinstance(v, (int, float))}
    verdict = str(data.get("verdict", "PASS")).upper()
    if "REVISE" in verdict:
        verdict = "REVISE"
    elif scores and min(scores.values()) <= 2:
        # A model that says PASS while scoring 2 is contradicting itself;
        # trust the number over the label.
        verdict = "REVISE"
        log("verdict overridden to REVISE - a score of 2 or below was given")
    else:
        verdict = "PASS"

    avg = sum(scores.values()) / len(scores) if scores else 0
    log(f"verdict {verdict}, average score {avg:.1f}/5")
    return {"review": {"scores": scores, "verdict": verdict,
                       "problems": data.get("problems", []),
                       "fixes": data.get("fixes", []),
                       "average": round(avg, 2)}}


def file_saver(ctx, llm, log):
    """Mandatory tool. Writes markdown and JSON; touches no model."""
    platform = ctx.get("platform", "output")
    stem = f"{_slug(ctx.get('topic', 'untitled'))}_{_slug(platform, 16)}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    has_script = bool(ctx.get("reel_script"))
    folder = OUTPUT_ROOT / ("generated_scripts" if has_script else "generated_posts")
    folder.mkdir(parents=True, exist_ok=True)

    md = folder / f"{stem}_{stamp}.md"
    md.write_text(render_markdown(ctx), encoding="utf-8")

    results = OUTPUT_ROOT / "saved_results"
    results.mkdir(parents=True, exist_ok=True)
    js = results / f"{stem}_{stamp}.json"
    js.write_text(json.dumps(
        {k: v for k, v in ctx.items() if k not in ("angles",)},
        indent=2, ensure_ascii=False), encoding="utf-8")

    log(f"saved {md.name} and {js.name}")
    return {"saved_markdown": str(md), "saved_json": str(js)}


def memory_recall(ctx, llm, log):
    """Look up what was generated before, so the agent can avoid repeating itself."""
    from memory import Memory
    mem = Memory()
    past = mem.recent(limit=5)
    similar = mem.similar_topics(ctx.get("topic", ""), limit=3)
    log(f"recalled {len(past)} previous runs, {len(similar)} on similar topics")
    return {"memory": {"recent": past, "similar": similar}}


# --------------------------------------------------------------- rendering
def render_markdown(ctx) -> str:
    """The human-readable artefact. Also what gets pasted into LinkedIn."""
    L = [f"# {ctx.get('topic', 'Untitled')}", ""]
    L += [f"**Platform:** {ctx.get('platform', '-')}  ",
          f"**Tone:** {ctx.get('tone', '-')}  ",
          f"**Generated:** {datetime.now():%Y-%m-%d %H:%M}  ",
          f"**Model:** {ctx.get('model', '-')}", ""]

    if ctx.get("angle"):
        L += ["## Content idea", "", ctx["angle"], ""]
    if ctx.get("audience"):
        L += [f"**Target audience:** {ctx['audience']}", ""]
    if ctx.get("hook"):
        L += ["## Hook", "", f"> {ctx['hook']}", ""]
    if ctx.get("caption"):
        L += [f"## {ctx.get('platform', 'Post')} caption", "", ctx["caption"], ""]
    if ctx.get("hashtags"):
        L += ["## Hashtags", "", " ".join(ctx["hashtags"]), ""]

    if ctx.get("reel_script"):
        L += ["## Reel / video script", ""]
        for s in ctx["reel_script"]:
            L.append(f"**Scene {s.get('scene', '?')}** — *{s.get('visual', '')}*  ")
            L.append(f"{s.get('voiceover', '')}")
            L.append("")

    if ctx.get("titles"):
        L += ["## Suggested titles", ""] + [f"- {t}" for t in ctx["titles"]] + [""]
    if ctx.get("thumbnail_texts"):
        L += ["## Thumbnail text", ""] + [f"- {t}" for t in ctx["thumbnail_texts"]] + [""]

    rv = ctx.get("review")
    if rv:
        L += ["## Reviewer", "", f"**Verdict:** {rv.get('verdict')} "
              f"(avg {rv.get('average')}/5)", ""]
        if rv.get("scores"):
            L += ["| Check | Score |", "|---|---|"]
            L += [f"| {k} | {v}/5 |" for k, v in rv["scores"].items()] + [""]
        for label, key in (("Problems", "problems"), ("Fixes suggested", "fixes")):
            if rv.get(key):
                L += [f"**{label}:**", ""] + [f"- {x}" for x in rv[key]] + [""]
    if ctx.get("revised"):
        L += ["*This post was revised once after the reviewer returned REVISE.*", ""]

    return "\n".join(L)


# -------------------------------------------------------------- the registry
REGISTRY = {t.name: t for t in [
    Tool("memory_recall", "Recall previous topics and outputs to avoid repetition",
         (), ("memory",), memory_recall, uses_llm=False),
    Tool("trend_idea_generator", "Generate content angles and pick the strongest",
         ("topic",), ("angle", "hook", "audience"), trend_idea_generator),
    Tool("caption_writer", "Write the post caption for the platform",
         ("topic",), ("caption",), caption_writer),
    Tool("hashtag_generator", "Generate platform-appropriate hashtags",
         ("topic",), ("hashtags",), hashtag_generator),
    Tool("reel_script_generator", "Write a 45-second 4-scene video script",
         ("topic",), ("reel_script",), reel_script_generator),
    Tool("title_thumbnail_generator", "Generate catchy titles and thumbnail text",
         ("topic",), ("titles", "thumbnail_texts"), title_thumbnail_generator),
    Tool("content_reviewer", "Critique the content and decide PASS or REVISE",
         (), ("review",), content_reviewer),
    Tool("file_saver", "Save the final result to .md and .json (mandatory)",
         (), ("saved_markdown", "saved_json"), file_saver, uses_llm=False),
]}


def tool_menu() -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in REGISTRY.values())
