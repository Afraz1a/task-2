"""
The agent: plan, route, execute, review, revise, save.

What makes this an agent rather than a pipeline is that **the plan is not
hardcoded**. The model is shown the tool menu and the user's request and decides
which tools to run. Ask for "a post" and it skips the reel script; ask for "a
reel" and it includes it.

That freedom needs a guard rail, because a 4B model will happily invent a tool
called `viral_maximizer`. So every plan goes through `repair_plan`, which:

  * drops tools that do not exist (fuzzy-matching near-misses first)
  * enforces the ordering constraints the tools actually have
  * guarantees `file_saver` runs last, since the brief makes saving mandatory
  * falls back to a sensible default plan if nothing usable survives

The second agentic behaviour is self-correction: `content_reviewer` scores the
output and returns PASS or REVISE, and on REVISE the agent rewrites the caption
with the critique fed back, then re-reviews. It revises at most once - a small
model asked to revise repeatedly drifts rather than improves.
"""

from __future__ import annotations

import difflib
import json
import re
import time
from datetime import datetime

import prompts
import tools as toolmod
from memory import Memory
from ollama_client import OllamaClient, OllamaError

# Ordering constraints. Everything else the planner is free to arrange.
FIRST = "trend_idea_generator"      # other tools build on its angle
SECOND_LAST = "content_reviewer"    # must see the finished content
LAST = "file_saver"                 # mandatory, and saves whatever exists

DEFAULT_PLAN = ["memory_recall", "trend_idea_generator", "caption_writer",
                "hashtag_generator", "content_reviewer", "file_saver"]


def _best_match(name: str, known: list) -> str | None:
    """
    Find the tool a mistyped name meant.

    Plain difflib is wrong here: every tool ends in `_generator` or `_writer`,
    so "caption_generator" scores as close to "hashtag_generator" as to
    "caption_writer" on raw character overlap. The head word carries the
    meaning, so it is weighted far more heavily than the rest of the string.
    """
    want = re.split(r"[^a-z0-9]+", name.lower().strip())
    want = [w for w in want if w]
    if not want:
        return None

    best, best_score = None, 0.0
    for tool in known:
        parts = tool.split("_")
        score = difflib.SequenceMatcher(None, name.lower(), tool).ratio()
        if parts[0] == want[0]:
            score += 1.0                      # same subject: decisive
        elif parts[0] in want:
            score += 0.5                      # subject appears somewhere
        if score > best_score:
            best, best_score = tool, score
    # 0.6 keeps the old difflib-only threshold for genuinely unrelated names.
    return best if best_score >= 0.6 else None


def _wants_video(output_type: str, platform: str = "") -> bool:
    """
    Did the user actually ask for a video?

    Substring matching on "short" is tempting because of "YouTube Shorts", but
    it also matches "short post" - and that bug put a 4-scene video script into
    two X posts during testing before it was caught. Match whole words, and
    treat "shorts" (plural) as the video signal rather than "short".
    """
    words = set(re.split(r"[^a-z]+", str(output_type).lower()))
    if words & {"reel", "reels", "video", "script", "shorts"}:
        return True
    # "a post for YouTube Shorts" is a video request even if the output type
    # does not say so.
    return "shorts" in str(platform).lower()


def repair_plan(raw_plan, wants_video: bool = False) -> tuple[list, list]:
    """
    Turn whatever the model produced into an executable plan.

    Returns (plan, notes) where notes records every correction made, so the
    report can show how often the planner needed fixing.
    """
    notes = []
    known = list(toolmod.REGISTRY)
    plan = []

    for item in (raw_plan or []):
        name = str(item).strip()
        if name in toolmod.REGISTRY:
            if name not in plan:
                plan.append(name)
            continue
        # Near-miss: "caption_generator" -> "caption_writer"
        match = _best_match(name, known)
        if match:
            notes.append(f"renamed unknown tool '{name}' to '{match}'")
            if match not in plan:
                plan.append(match)
        else:
            notes.append(f"dropped unknown tool '{name}'")

    if not plan:
        notes.append("plan was empty or unusable - fell back to the default plan")
        plan = list(DEFAULT_PLAN)

    # trend_idea_generator supplies the angle every writer tool reads.
    if FIRST in plan and plan.index(FIRST) != 0:
        plan.remove(FIRST)
        plan.insert(0, FIRST)
        notes.append(f"moved {FIRST} to the front")
    if FIRST not in plan and any(
            t in plan for t in ("caption_writer", "reel_script_generator",
                                "title_thumbnail_generator")):
        plan.insert(0, FIRST)
        notes.append(f"inserted {FIRST} - writer tools need an angle")

    # The user asked for a video but the planner forgot it.
    if wants_video and "reel_script_generator" not in plan:
        plan.insert(max(1, len(plan) - 1), "reel_script_generator")
        notes.append("inserted reel_script_generator - the user asked for a video")

    # Reviewer second to last, saver last, both exactly once.
    for name in (SECOND_LAST, LAST):
        while plan.count(name) > 1:
            plan.remove(name)
    if SECOND_LAST in plan:
        plan.remove(SECOND_LAST)
    plan.append(SECOND_LAST)
    if LAST in plan:
        plan.remove(LAST)
    plan.append(LAST)
    if LAST not in (raw_plan or []):
        notes.append(f"appended {LAST} - saving is mandatory")

    return plan, notes


class TrendPilotAgent:
    def __init__(self, model: str = "gemma3:4b", verbose: bool = True,
                 max_revisions: int = 1):
        self.llm = OllamaClient(model=model)
        self.verbose = verbose
        self.max_revisions = max_revisions
        self.memory = Memory()
        self.trace: list = []

    # ---------------------------------------------------------------- output
    def _say(self, text: str) -> None:
        self.trace.append(text)
        if self.verbose:
            print(text)

    def _tool_log(self, tool_name: str):
        def log(message):
            self._say(f"          {message}")
        return log

    # ------------------------------------------------------------------ plan
    def plan(self, ctx: dict) -> list:
        wants_video = _wants_video(ctx["output_type"], ctx["platform"])
        try:
            data = self.llm.ask_json(
                prompts.PLANNER.format(
                    topic=ctx["topic"], platform=ctx["platform"],
                    tone=ctx["tone"], output_type=ctx["output_type"],
                    tool_menu=toolmod.tool_menu()),
                system=prompts.SYSTEM, temperature=0.2, num_predict=400)
            raw = data.get("plan", [])
            reasoning = data.get("reasoning", "")
        except OllamaError as exc:
            self._say(f"  ! planner failed ({exc}); using the default plan")
            raw, reasoning = [], ""

        plan, notes = repair_plan(raw, wants_video=wants_video)
        if reasoning:
            self._say(f"  reasoning: {reasoning}")
        self._say("  plan: " + " -> ".join(plan))
        for n in notes:
            self._say(f"  ! plan repaired: {n}")
        ctx["plan_raw"] = raw
        ctx["plan_repairs"] = notes
        return plan

    # --------------------------------------------------------------- execute
    def run(self, topic: str, platform: str = "LinkedIn",
            tone: str = "professional and exciting",
            output_type: str = "post") -> dict:
        started = time.time()
        ctx = {
            "topic": topic, "platform": platform, "tone": tone,
            "output_type": output_type, "model": self.llm.resolve_model(),
            "started": datetime.now().isoformat(timespec="seconds"),
            "tools_used": [], "tool_errors": [],
        }

        self._say(f"\n{'=' * 64}")
        self._say(f"TOPIC    : {topic}")
        self._say(f"PLATFORM : {platform}   TONE: {tone}   WANTS: {output_type}")
        self._say(f"MODEL    : {ctx['model']}")
        self._say(f"{'=' * 64}")

        # A second model still resident from a previous run is the actual
        # cause of the 500 errors seen mid-run - see free_vram_for_our_model.
        freed = self.llm.free_vram_for_our_model()
        if freed:
            self._say(f"[VRAM]     unloaded {', '.join(freed)} to make room")

        self._say("[Planning]")

        plan = self.plan(ctx)
        self._say("")

        for name in plan:
            tool = toolmod.REGISTRY[name]
            self._say(f"[Tool Called]: {name}")
            try:
                produced = tool.run(ctx, self.llm, self._tool_log(name))
                ctx.update(produced or {})
                ctx["tools_used"].append(name)
            except (OllamaError, ValueError, KeyError, OSError) as exc:
                # One failing tool must not lose the whole run - the saver at
                # the end still writes whatever was produced up to this point.
                self._say(f"          ! failed: {exc}")
                ctx["tool_errors"].append({"tool": name, "error": str(exc)})
                continue

            # Self-correction, immediately after review and before saving.
            if name == SECOND_LAST:
                self._maybe_revise(ctx)

        ctx["elapsed_seconds"] = round(time.time() - started, 1)
        self.memory.add(ctx)
        self._say(f"\n[Done] {len(ctx['tools_used'])} tools, "
                  f"{ctx['elapsed_seconds']}s"
                  + (f", {len(ctx['tool_errors'])} tool error(s)"
                     if ctx["tool_errors"] else ""))
        if ctx.get("saved_markdown"):
            self._say(f"[Saved] {ctx['saved_markdown']}")
        return ctx

    # -------------------------------------------------------------- revision
    # Complaints that name the script rather than the caption. The reviewer
    # sees both (content_reviewer includes the reel script when one exists),
    # but revision used to rewrite only the caption - a script flagged as
    # broken would be correctly identified and then shipped anyway. This is
    # what caused the corrupted "timing calculation" scene to reach a saved
    # file: the reviewer named the problem, nothing acted on it.
    _SCRIPT_WORDS = {"script", "scene", "scenes", "voiceover", "visual",
                     "timing", "video"}

    def _revise_targets(self, problems: list) -> tuple[bool, bool]:
        """Which of (caption, script) the reviewer's complaints are about."""
        text = " ".join(problems).lower()
        words = set(re.split(r"[^a-z]+", text))
        mentions_script = bool(words & self._SCRIPT_WORDS)
        # A complaint list that says nothing script-specific is almost always
        # about the caption; treat unmentioned as "the caption", not "both".
        return True, mentions_script

    def _maybe_revise(self, ctx: dict) -> None:
        review = ctx.get("review") or {}
        if review.get("verdict") != "REVISE" or not ctx.get("caption"):
            return
        if self.max_revisions < 1:
            return

        problems = review.get("problems", [])
        fixes = review.get("fixes", [])
        do_caption, do_script = self._revise_targets(problems)
        do_script = do_script and bool(ctx.get("reel_script"))

        self._say("[Self-correction]: reviewer returned REVISE - rewriting")
        if do_caption:
            self._revise_caption(ctx, problems, fixes)
        if do_script:
            self._revise_script(ctx, problems, fixes)

        # Re-review so the saved file reports the content that actually
        # shipped, whichever part(s) were rewritten.
        if ctx.get("revised"):
            try:
                ctx.update(toolmod.content_reviewer(ctx, self.llm, self._tool_log("recheck")))
                self._say(f"          re-review: {ctx['review']['verdict']} "
                          f"(avg {ctx['review']['average']}/5)")
            except (OllamaError, ValueError) as exc:
                self._say(f"          ! re-review failed ({exc})")

    def _revise_caption(self, ctx: dict, problems: list, fixes: list) -> None:
        try:
            data = self.llm.ask_json(
                prompts.REVISE.format(
                    platform=ctx["platform"], caption=ctx["caption"],
                    problems="\n".join(f"- {p}" for p in problems) or "- none given",
                    fixes="\n".join(f"- {f}" for f in fixes) or "- none given",
                    rules=prompts.platform_rule(ctx["platform"])),
                system=prompts.SYSTEM, num_predict=1100)
        except OllamaError as exc:
            self._say(f"          ! caption revision failed ({exc}); keeping the original")
            return

        new_caption = (data.get("caption") or "").strip()
        if not new_caption:
            self._say("          ! caption revision returned nothing; keeping the original")
            return

        ctx["caption_original"] = ctx["caption"]
        ctx["caption"] = new_caption
        ctx["revised"] = True
        self._say(f"          caption rewritten ({len(new_caption.split())} words)")

    def _revise_script(self, ctx: dict, problems: list, fixes: list) -> None:
        try:
            data = self.llm.ask_json(
                prompts.REVISE_SCRIPT.format(
                    script=json.dumps(ctx["reel_script"], indent=1),
                    problems="\n".join(f"- {p}" for p in problems) or "- none given",
                    fixes="\n".join(f"- {f}" for f in fixes) or "- none given"),
                system=prompts.SYSTEM, num_predict=1100)
        except OllamaError as exc:
            self._say(f"          ! script revision failed ({exc}); keeping the original")
            return

        new_scenes = data.get("scenes") or []
        if not new_scenes:
            self._say("          ! script revision returned nothing; keeping the original")
            return

        ctx["reel_script_original"] = ctx["reel_script"]
        ctx["reel_script"] = new_scenes
        ctx["revised"] = True
        self._say(f"          script rewritten ({len(new_scenes)} scenes)")
