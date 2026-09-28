# 🚀 TrendPilot

**A local agentic AI assistant that turns a project topic into a complete content plan.**
Runs entirely on your own machine through Ollama — no API key, no cloud, no per-token cost.

AIRI Team PITB — AI Internship Task 2

---

## What it does

You give it a topic, a platform and a tone. It gives you back a hook, a caption,
hashtags, a video script, titles, thumbnail text, a critique of its own output, and
a saved file.

```
Topic:     YOLOv8 helmet detection system for motorcycle riders
Platform:  LinkedIn
Tone:      professional and exciting
Wants:     post and hashtags
```

```
[Planning]
  reasoning: focuses on a strong angle first, then the post and hashtags,
             then review and save
  plan: trend_idea_generator -> caption_writer -> hashtag_generator
        -> content_reviewer -> file_saver

[Tool Called]: trend_idea_generator     generated 5 angles, selected one
[Tool Called]: caption_writer           wrote caption (127 words)
[Tool Called]: hashtag_generator        generated 6 hashtags
[Tool Called]: content_reviewer         verdict REVISE, average score 4.0/5
[Self-correction]: reviewer returned REVISE - rewriting
[Tool Called]: file_saver               saved .md and .json

[Done] 5 tools, 108s
```

## Why this is an agent and not a chatbot

The distinction the brief draws is real, and it is easy to fail by accident. A
script that calls five functions in a fixed order is a pipeline wearing an
agent's clothes. Three things here are genuinely agentic:

**1. The agent chooses its own tools.** The model is shown the tool menu and the
user's request, and returns a plan. Ask for "a post" and it skips the reel script
generator. Ask for "a reel" and it includes it. The order is not hardcoded.

**2. It reviews its own work and acts on the verdict.** `content_reviewer` scores
the output on six criteria and returns `PASS` or `REVISE`. On `REVISE` the agent
rewrites the caption with the critique fed back in, then re-reviews. It revises at
most once — a 4B model asked to revise repeatedly drifts rather than improves.

**3. It remembers.** Every run is written to `outputs/memory.json`, and
`memory_recall` surfaces previous topics and similar past work so the agent can
avoid repeating an angle it already used.

## The agent's tools

The brief requires at least three. All eight are implemented.

| Tool | What it does | Calls the model? |
|---|---|---|
| `memory_recall` | Recall previous topics and outputs | no |
| `trend_idea_generator` | Generate 5 angles, then pick the strongest | yes |
| `caption_writer` | Write the platform-specific post | yes |
| `hashtag_generator` | Platform-appropriate hashtags | yes |
| `reel_script_generator` | 4-scene, 45-second video script | yes |
| `title_thumbnail_generator` | Catchy titles and thumbnail text | yes |
| `content_reviewer` | Critique and decide `PASS` / `REVISE` | yes |
| `file_saver` | Write `.md` and `.json` (**mandatory**) | no |

Two of the eight touch no model at all. That matters: an agent whose every "tool"
is just another LLM call has not really left the chatbot behind.

## Quick start

**1. Install Ollama** from [ollama.com](https://ollama.com), then pull the model:

```bash
ollama pull gemma3:4b
```

**2. Install the Python dependency** (the agent needs only `requests`):

```bash
pip install -r requirements.txt
```

**3. Check everything is wired up:**

```bash
python demo.py --check
```

```
  ok Ollama is running
  ok models installed: gemma3:4b
  ok using gemma3:4b
  ok model replied: ready
Environment is ready.
```

**4. Run it:**

```bash
python demo.py
```

Or skip the prompts:

```bash
python demo.py --topic "my final year project on helmet detection" --platform LinkedIn --tone motivational
```

Or use the web demo:

```bash
streamlit run app/streamlit_app.py
```

Other commands:

```bash
python demo.py --history          # what the agent has generated before
python tests/run_tests.py         # run all ten test cases
```

## Project layout

```
agentic_ai_task_2/
├── app/
│   ├── main.py             entry point used by the demos
│   ├── agent.py            plan → route → execute → review → revise → save
│   ├── tools.py            the eight tools and the registry
│   ├── memory.py           JSON memory store with similarity recall
│   ├── prompts.py          every prompt template, in one place
│   ├── ollama_client.py    HTTP client with JSON repair and retries
│   └── streamlit_app.py    optional web demo
├── outputs/
│   ├── generated_posts/    saved .md posts
│   ├── generated_scripts/  saved .md scripts
│   ├── saved_results/      full run context as .json
│   └── memory.json         the agent's memory
├── tests/
│   ├── run_tests.py        runs the brief's ten test cases
│   ├── test_cases.md       results table
│   └── results.json        raw results
├── screenshots/
├── report/final_report.pdf
├── demo.py
├── requirements.txt
└── README.md
```

## Engineering notes

These are the problems that actually cost time, and how they were handled.

**A 4B model does not reliably emit JSON.** Asked for an object it will fence it
in markdown, wrap it in prose, add trailing commas, use smart quotes, or stop
mid-object at the token limit. `ollama_client.ask_json` tries Ollama's native JSON
mode, a direct parse, extraction from surrounding prose, repair of the common
malformations, and finally one re-ask with the parse error fed back. Seven
malformation cases are covered by tests.

**A 4B model invents tools.** Given a menu it will still return
`viral_maximizer`. `repair_plan` drops unknown tools, fuzzy-matches near misses,
enforces the ordering the tools actually require, and guarantees `file_saver`
runs last. If nothing usable survives it falls back to a default plan, so the run
never dies at the planning stage.

**Fuzzy matching on tool names needs care.** Every tool ends in `_generator` or
`_writer`, so plain `difflib` matched `caption_generator` to `hashtag_generator` —
the shared suffix outweighed the meaningful word. The matcher now weights the head
word decisively.

**Ollama returns 500 while a model loads into VRAM.** On a 6 GB card, `llama3.1`
(4.9 GB) and `gemma3:4b` (3.3 GB) cannot both be resident, and the second one to
load fails until the first is evicted. The client retries server errors with
backoff and fails fast on client errors.

**One failing tool must not lose the run.** Each tool call is wrapped; a failure
is logged into `tool_errors` and the agent continues, so `file_saver` still writes
whatever was produced. This is not hypothetical — it happened during development
and the partial output was still usable.

## Model

Built and tested on **`gemma3:4b`** (3.3 GB, the brief's recommended model),
running fully on GPU on an RTX 4050. `llama3.1:8b` also works and was used during
development; it is slower — roughly 145 s per run against 108 s for gemma3:4b —
without producing noticeably better copy at this task.

Any Ollama model works: pass `--model`. If the named model is missing the client
falls back to whatever is installed rather than crashing.

## Results and limitations

Test results are in [`tests/test_cases.md`](tests/test_cases.md); the failure
analysis is in the final report.

Known limitations, stated plainly:

- **The model will still invent things.** A grounding rule in the system prompt
  cut this sharply — an early run described the helmet project as a real-time
  rider alert system, which it is not — but a 4B model given a four-word topic
  fills gaps with plausible fiction. Give it a fuller topic and it behaves better.
- **The reviewer is the same model that wrote the post**, so it is not an
  independent check. It reliably catches length and tone problems; it is weaker at
  catching fabrication, which is exactly what it should be best at.
- **Revision does not always improve the output.** In one measured run the
  reviewer's own score fell from 4.0 to 3.3 after revision.
- **Everything is local, so everything is slow.** A full run is one to two
  minutes. That is the price of no API key and no per-token cost.
