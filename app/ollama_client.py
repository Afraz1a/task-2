"""
Ollama client with the robustness a 4B model actually needs.

A local 4B model is not a hosted frontier model. Asked for JSON it will wrap the
object in prose, fence it in markdown, emit trailing commas, use single quotes,
or stop mid-object when it hits the token limit. Every one of those failures
appeared while building this project.

So `ask_json` does not simply call `json.loads`. It tries, in order:

  1. Ollama's native JSON mode (`format: json`), which constrains decoding
  2. a direct parse
  3. extraction of the outermost {...} or [...] from surrounding prose
  4. repair of the common malformations
  5. one re-ask with the parse error fed back to the model

If all five fail it raises, and the agent falls back to a non-JSON path rather
than crashing. Failure counts are tracked so the error analysis can report how
often this happens - see `STATS`.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field

import requests

DEFAULT_MODEL = "gemma3:4b"
DEFAULT_HOST = "http://localhost:11434"

# Counters surfaced in the report's error analysis.
STATS = Counter()


class OllamaError(RuntimeError):
    pass


@dataclass
class OllamaClient:
    model: str = DEFAULT_MODEL
    host: str = DEFAULT_HOST
    timeout: int = 180
    temperature: float = 0.7
    num_predict: int = 900
    # Every prompt and response, for the report and for debugging.
    transcript: list = field(default_factory=list)

    # ---------------------------------------------------------------- health
    def is_up(self) -> bool:
        try:
            requests.get(f"{self.host}/api/tags", timeout=5).raise_for_status()
            return True
        except Exception:
            return False

    def available_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=10)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def free_vram_for_our_model(self) -> list[str]:
        """
        Unload any other model currently resident in VRAM.

        On a 6 GB card, gemma3:4b (3.3 GB) and llama3.1 (4.9 GB) do not both
        fit. If the other one is still loaded when a request comes in, Ollama
        has to evict it to make room and returns a 500 while that happens -
        this is exactly the "500 Server Error" failure seen after three
        retries in testing. Retrying does not help because the request that
        triggers the eviction is the one that fails; asking Ollama to unload
        the other model *before* the real request avoids the collision
        instead of retrying through it.

        Best-effort: swallows errors, since this is a courtesy pass, not the
        request that actually matters.
        """
        freed = []
        try:
            r = requests.get(f"{self.host}/api/ps", timeout=5)
            r.raise_for_status()
            loaded = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return freed
        target = self.resolve_model()
        for name in loaded:
            if name == target:
                continue
            try:
                requests.post(f"{self.host}/api/generate",
                              json={"model": name, "keep_alive": 0}, timeout=15)
                freed.append(name)
            except Exception:
                pass
        return freed

    def resolve_model(self) -> str:
        """
        Fall back to any installed model if the configured one is missing, so a
        missing `ollama pull` degrades instead of crashing.
        """
        installed = self.available_models()
        if not installed:
            raise OllamaError(
                f"Ollama is not reachable at {self.host}. Start it, then run "
                f"`ollama pull {self.model}`.")
        if self.model in installed:
            return self.model
        # "gemma3:4b" should still match a listed "gemma3:4b-it-q4_K_M"
        for name in installed:
            if name.split(":")[0] == self.model.split(":")[0]:
                return name
        STATS["model_fallback"] += 1
        return installed[0]

    # ------------------------------------------------------------------ text
    def ask(self, prompt: str, system: str | None = None,
            temperature: float | None = None, num_predict: int | None = None,
            json_mode: bool = False) -> str:
        payload = {
            "model": self.resolve_model(),
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_predict": self.num_predict if num_predict is None else num_predict,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        started = time.time()
        # Ollama returns 500 while a model is loading into VRAM, and on a 6 GB
        # card that happens whenever another model is still resident - a second
        # model simply will not fit. It clears on its own once the old one is
        # evicted, so a short backoff recovers where a crash would not.
        text, last_exc = None, None
        for attempt in range(3):
            try:
                r = requests.post(f"{self.host}/api/generate", json=payload,
                                  timeout=self.timeout)
                # Ollama reports model-level failures as 500 with a JSON body,
                # so read the body before raising - the message decides whether
                # a retry can possibly help.
                detail = ""
                if r.status_code >= 500:
                    try:
                        detail = str(r.json().get("error", ""))
                    except ValueError:
                        detail = r.text[:200]
                r.raise_for_status()
                text = r.json().get("response", "").strip()
                break
            except requests.Timeout as exc:
                STATS["timeout"] += 1
                raise OllamaError(f"model timed out after {self.timeout}s") from exc
            except requests.RequestException as exc:
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status < 500:
                    STATS["request_error"] += 1
                    raise OllamaError(f"Ollama rejected the request: {exc}") from exc

                # "prediction aborted, token repeat limit reached" means the
                # model fell into a repetition loop. Measured on gemma3:4b:
                # temperature 0.7 loops on nested-JSON prompts every time,
                # 0.95 does not. Retrying the same request is pointless - raise
                # the temperature instead. num_predict makes no difference.
                if "repeat" in detail.lower():
                    STATS["repeat_loop"] += 1
                    old = payload["options"]["temperature"]
                    payload["options"]["temperature"] = min(round(old + 0.2, 2), 1.1)
                    payload["options"]["repeat_penalty"] = 1.2
                    if attempt < 2:
                        continue          # retry immediately, no backoff needed

                STATS["retry"] += 1
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        if text is None:
            STATS["request_error"] += 1
            raise OllamaError(
                f"Ollama failed after 3 attempts: {last_exc}") from last_exc

        elapsed = time.time() - started
        STATS["calls"] += 1
        STATS["seconds"] += int(elapsed)
        self.transcript.append({
            "prompt": prompt[:4000], "system": system,
            "response": text[:4000], "seconds": round(elapsed, 1),
            "json_mode": json_mode,
        })
        return text

    # ------------------------------------------------------------------ json
    def ask_json(self, prompt: str, system: str | None = None,
                 expect: type = dict, retries: int = 1, **kw):
        """Ask for JSON and actually get JSON back. Raises OllamaError if not."""
        raw = self.ask(prompt, system=system, json_mode=True, **kw)
        parsed, err = _parse_json(raw, expect)
        if parsed is not None:
            return parsed

        STATS["json_repair_attempted"] += 1
        for _ in range(max(0, retries)):
            # Show the model its own broken output and the parser's complaint.
            fix_prompt = (
                f"{prompt}\n\n"
                f"Your previous reply could not be parsed as JSON.\n"
                f"Parser error: {err}\n"
                f"Your reply was:\n{raw[:1200]}\n\n"
                f"Reply again with ONLY valid JSON. No prose, no markdown fence.")
            raw = self.ask(fix_prompt, system=system, json_mode=True, **kw)
            parsed, err = _parse_json(raw, expect)
            if parsed is not None:
                STATS["json_repair_succeeded"] += 1
                return parsed

        STATS["json_failed"] += 1
        raise OllamaError(f"could not obtain valid JSON ({err}); last reply: {raw[:300]}")


# ------------------------------------------------------------------ parsing
def _parse_json(raw: str, expect: type):
    """Return (parsed, error). Tries increasingly forgiving strategies."""
    if not raw or not raw.strip():
        return None, "empty response"

    candidates = [raw]

    # Strip a markdown fence if the model added one despite being told not to.
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if fenced:
        candidates.append(fenced.group(1))

    # Grab the outermost object or array out of surrounding prose.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = raw.find(opener), raw.rfind(closer)
        if start != -1 and end > start:
            candidates.append(raw[start:end + 1])

    last_err = "no candidate parsed"
    for cand in candidates:
        cand = cand.strip()
        for attempt in (cand, _repair(cand)):
            value, err = _decode_leading(attempt)
            if value is None:
                last_err = err
                continue
            if expect is dict and isinstance(value, dict):
                return value, None
            if expect is list and isinstance(value, list):
                return value, None
            if expect is None:
                return value, None
            last_err = f"expected {expect.__name__}, got {type(value).__name__}"
    return None, last_err


def _decode_leading(text: str):
    """
    Parse the first complete JSON value and ignore whatever follows it.

    This is the actual cause of most observed failures, not truncation: a
    small model finishes a valid object and then keeps talking, or - on
    gemma3:4b specifically - drifts into a repetition loop that appends
    `"}"}"}...` after an otherwise complete reply. `json.loads` rejects both
    as "Extra data" and discards the perfectly good object it already parsed.
    `raw_decode` stops at the end of the first value instead of demanding the
    whole string be consumed.
    """
    try:
        value, _ = json.JSONDecoder().raw_decode(text.strip())
        return value, None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def _repair(text: str) -> str:
    """Fix the malformations a small model actually produces."""
    out = text
    out = re.sub(r",\s*([}\]])", r"\1", out)          # trailing commas
    out = re.sub(r"//[^\n]*", "", out)                 # // comments
    out = out.replace("“", '"').replace("”", '"')   # smart quotes
    out = out.replace("‘", "'").replace("’", "'")
    # Single-quoted keys/values -> double, when no double quotes are present.
    if '"' not in out and "'" in out:
        out = out.replace("'", '"')
    # An object truncated by the token limit: close what is still open.
    opens, closes = out.count("{"), out.count("}")
    if opens > closes:
        out = out.rstrip().rstrip(",") + "}" * (opens - closes)
    opens, closes = out.count("["), out.count("]")
    if opens > closes:
        out = out.rstrip().rstrip(",") + "]" * (opens - closes)
    return out
