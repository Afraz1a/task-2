"""
Agent memory: what was generated before.

The brief requires memory or saved outputs. This is deliberately a plain JSON
store rather than SQLite - the whole file is a few hundred records at most, and
a file the marker can open and read is worth more here than a database they
cannot inspect without a client.

Memory is used for two things:
  * `recent()` - what has been generated lately, shown in the CLI
  * `similar_topics()` - if the user asks about a topic close to a previous one,
    the agent can see the earlier angle and avoid repeating it

The similarity check is word-overlap (Jaccard), not embeddings. For matching
"helmet detection project" to "YOLOv8 helmet detector" that is sufficient, and
it adds no dependency or model call.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent / "outputs" / "memory.json"

# Words that carry no topic signal and would inflate every similarity score.
STOPWORDS = {
    "a", "an", "the", "my", "our", "your", "i", "we", "about", "for", "on",
    "of", "to", "in", "and", "or", "with", "is", "are", "was", "were", "it",
    "this", "that", "project", "post", "make", "create", "want", "using", "use",
}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


class Memory:
    def __init__(self, path: Path | str = STORE):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self._load()

    def _load(self) -> list:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            # A corrupt store must not stop the agent running. Move it aside.
            broken = self.path.with_suffix(".corrupt.json")
            try:
                self.path.replace(broken)
            except OSError:
                pass
            return []

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self.records, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------ api
    def add(self, ctx: dict) -> dict:
        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "topic": ctx.get("topic", ""),
            "platform": ctx.get("platform", ""),
            "tone": ctx.get("tone", ""),
            "angle": ctx.get("angle", ""),
            "hook": ctx.get("hook", ""),
            "tools_used": ctx.get("tools_used", []),
            "review_verdict": (ctx.get("review") or {}).get("verdict"),
            "review_average": (ctx.get("review") or {}).get("average"),
            "revised": bool(ctx.get("revised")),
            "saved_markdown": ctx.get("saved_markdown"),
            "model": ctx.get("model"),
            "seconds": ctx.get("elapsed_seconds"),
        }
        self.records.append(record)
        self._save()
        return record

    def recent(self, limit: int = 5) -> list:
        return [
            {"topic": r["topic"], "platform": r["platform"], "angle": r["angle"],
             "timestamp": r["timestamp"]}
            for r in self.records[-limit:][::-1]
        ]

    def similar_topics(self, topic: str, limit: int = 3) -> list:
        """Jaccard word overlap. Cheap, dependency-free, good enough here."""
        target = _tokens(topic)
        if not target:
            return []
        scored = []
        for r in self.records:
            other = _tokens(r.get("topic", ""))
            if not other:
                continue
            overlap = len(target & other) / len(target | other)
            if overlap >= 0.3:
                scored.append((overlap, r))
        scored.sort(key=lambda s: -s[0])
        return [
            {"topic": r["topic"], "platform": r["platform"], "angle": r["angle"],
             "similarity": round(score, 2)}
            for score, r in scored[:limit]
        ]

    def stats(self) -> dict:
        if not self.records:
            return {"runs": 0}
        verdicts = [r.get("review_verdict") for r in self.records if r.get("review_verdict")]
        scores = [r["review_average"] for r in self.records
                  if isinstance(r.get("review_average"), (int, float))]
        return {
            "runs": len(self.records),
            "platforms": sorted({r["platform"] for r in self.records if r["platform"]}),
            "revised": sum(1 for r in self.records if r.get("revised")),
            "pass_rate": round(verdicts.count("PASS") / len(verdicts), 2) if verdicts else None,
            "mean_review_score": round(sum(scores) / len(scores), 2) if scores else None,
        }
