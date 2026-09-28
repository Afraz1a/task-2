"""Quick check that the JSON parsing fix recovers from trailing garbage."""
import sys
sys.path.insert(0, "app")
from ollama_client import _parse_json

raw = '{"verdict": "REVISE"} extra junk after'
value, err = _parse_json(raw, dict)
print("parsed:", value)
print("error :", err)
print("PASS" if value == {"verdict": "REVISE"} else "FAIL")
