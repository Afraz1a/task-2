"""
Programmatic entry point for TrendPilot.

`demo.py` is the interactive CLI; this is the importable one-call API, so the
agent can be driven from another script, a notebook, or a web handler without
going through argument parsing.

    from app.main import generate_content

    result = generate_content(
        topic="YOLOv8 helmet detection system",
        platform="LinkedIn",
        tone="professional and exciting",
        output_type="post and hashtags",
    )
    print(result["caption"])
    print(result["saved_markdown"])

Run directly for a single generation:

    python app/main.py "my topic here" --platform Instagram
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import TrendPilotAgent          # noqa: E402
from memory import Memory                  # noqa: E402
from ollama_client import OllamaClient, OllamaError   # noqa: E402
import tools as toolmod                    # noqa: E402

DEFAULT_MODEL = "gemma3:4b"


def generate_content(topic: str, platform: str = "LinkedIn",
                     tone: str = "professional and exciting",
                     output_type: str = "post and hashtags",
                     model: str = DEFAULT_MODEL,
                     verbose: bool = False) -> dict:
    """
    Run the full agent once and return its context.

    The returned dict holds everything the run produced - angle, hook, caption,
    hashtags, reel_script, review, saved_markdown, saved_json, tools_used - plus
    tool_errors, which is empty on a clean run and worth checking on any other.

    Raises OllamaError if Ollama is unreachable. Individual tool failures do not
    raise: they are recorded in ctx["tool_errors"] and the run continues, so a
    partial result is still saved.
    """
    if not topic or not topic.strip():
        raise ValueError("topic is required")

    client = OllamaClient(model=model)
    if not client.is_up():
        raise OllamaError(
            "Ollama is not reachable at http://localhost:11434. "
            "Start Ollama and try again.")

    agent = TrendPilotAgent(model=model, verbose=verbose)
    return agent.run(topic=topic.strip(), platform=platform, tone=tone,
                     output_type=output_type)


def render(ctx: dict) -> str:
    """The markdown artefact for a finished run."""
    return toolmod.render_markdown(ctx)


def history(limit: int = 10) -> list:
    return Memory().recent(limit=limit)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate one content plan.")
    ap.add_argument("topic")
    ap.add_argument("--platform", default="LinkedIn")
    ap.add_argument("--tone", default="professional and exciting")
    ap.add_argument("--output-type", default="post and hashtags")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--json", action="store_true",
                    help="print the full context as JSON instead of markdown")
    args = ap.parse_args()

    try:
        ctx = generate_content(
            topic=args.topic, platform=args.platform, tone=args.tone,
            output_type=args.output_type, model=args.model, verbose=True)
    except OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("\n" + "=" * 64)
    if args.json:
        print(json.dumps({k: v for k, v in ctx.items() if k != "angles"},
                         indent=2, ensure_ascii=False))
    else:
        print(render(ctx))
    return 0


if __name__ == "__main__":
    sys.exit(main())
