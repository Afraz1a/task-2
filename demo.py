"""
TrendPilot CLI demo.

    python demo.py                      interactive
    python demo.py --topic "..." --platform LinkedIn --tone professional
    python demo.py --history            show what has been generated before
    python demo.py --check              verify Ollama and the model are ready

Run it from the project root so `outputs/` lands in the right place.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))

from agent import TrendPilotAgent            # noqa: E402
from memory import Memory                    # noqa: E402
from ollama_client import OllamaClient       # noqa: E402

PLATFORMS = ["LinkedIn", "Instagram", "X", "YouTube Shorts", "TikTok", "Facebook"]
TONES = ["professional and exciting", "motivational", "funny", "humorous",
         "short and catchy", "inspirational", "meme style"]
OUTPUT_TYPES = ["post", "post and hashtags", "reel script",
                "post and reel script", "full content plan"]

DEFAULT_MODEL = "gemma3:4b"


def choose(label: str, options: list, default: int = 0) -> str:
    print(f"\n{label}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}" + ("   (default)" if i - 1 == default else ""))
    raw = input("Choose a number, or press Enter for the default: ").strip()
    if not raw:
        return options[default]
    try:
        idx = int(raw) - 1
        return options[idx] if 0 <= idx < len(options) else options[default]
    except ValueError:
        return options[default]


def check(model: str) -> int:
    client = OllamaClient(model=model)
    print("\nChecking the environment")
    print("-" * 52)
    if not client.is_up():
        print("  x Ollama is not running at http://localhost:11434")
        print("    Start Ollama, then try again.")
        return 1
    print("  ok Ollama is running")

    installed = client.available_models()
    print(f"  ok models installed: {', '.join(installed) or 'none'}")
    resolved = client.resolve_model()
    if resolved != model:
        print(f"  ! '{model}' is not installed - falling back to '{resolved}'")
        print(f"    For the recommended model run: ollama pull {model}")
    else:
        print(f"  ok using {resolved}")

    print("  .. sending a test prompt", end="", flush=True)
    try:
        reply = client.ask("Reply with exactly the word: ready", num_predict=12)
        print(f"\r  ok model replied: {reply.strip()[:40]}")
    except Exception as exc:
        print(f"\r  x model call failed: {exc}")
        return 1
    print("-" * 52)
    print("Environment is ready.\n")
    return 0


def history() -> int:
    mem = Memory()
    stats = mem.stats()
    if not stats.get("runs"):
        print("\nNo previous runs yet.\n")
        return 0
    print(f"\nMemory: {stats['runs']} runs across {', '.join(stats['platforms'])}")
    if stats.get("mean_review_score") is not None:
        print(f"Mean reviewer score {stats['mean_review_score']}/5, "
              f"pass rate {stats['pass_rate']}, {stats['revised']} revised")
    print("-" * 64)
    for r in mem.recent(limit=10):
        print(f"  {r['timestamp']}  [{r['platform']}]  {r['topic'][:46]}")
        if r.get("angle"):
            print(f"      angle: {r['angle'][:60]}")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="TrendPilot - local agentic content assistant")
    ap.add_argument("--topic")
    ap.add_argument("--platform", default=None)
    ap.add_argument("--tone", default=None)
    ap.add_argument("--output-type", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--quiet", action="store_true", help="hide the agent trace")
    ap.add_argument("--check", action="store_true", help="verify the environment and exit")
    ap.add_argument("--history", action="store_true", help="show previous runs and exit")
    args = ap.parse_args()

    if args.check:
        return check(args.model)
    if args.history:
        return history()

    print("\n" + "=" * 64)
    print("  TrendPilot - local agentic AI content assistant")
    print("  AIRI Team PITB - AI Internship Task 2")
    print("=" * 64)

    client = OllamaClient(model=args.model)
    if not client.is_up():
        print("\nOllama is not running at http://localhost:11434.")
        print("Start Ollama and try again, or run: python demo.py --check\n")
        return 1

    topic = args.topic or input("\nWhat is your topic? ").strip()
    if not topic:
        print("A topic is required.")
        return 1

    platform = args.platform or choose("Which platform?", PLATFORMS)
    tone = args.tone or choose("What tone?", TONES)
    output_type = args.output_type or choose("What do you want?", OUTPUT_TYPES)

    agent = TrendPilotAgent(model=args.model, verbose=not args.quiet)
    ctx = agent.run(topic=topic, platform=platform, tone=tone,
                    output_type=output_type)

    print("\n" + "=" * 64)
    print("  FINAL OUTPUT")
    print("=" * 64)
    import tools as toolmod
    print(toolmod.render_markdown(ctx))
    if ctx.get("saved_markdown"):
        print(f"\nSaved to: {ctx['saved_markdown']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
