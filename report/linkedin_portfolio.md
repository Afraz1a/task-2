# LinkedIn / Portfolio Report

> **Put this in your own words before posting.** The assignment asks for this
> section in the intern's own voice. Everything below is accurate to the
> project and follows the brief's template, but it is a draft to edit, not a
> post to paste. Replace `[link]` with your repository or Drive URL and attach
> the screenshots.

---

## Project Title

**TrendPilot — A Local Agentic AI Content Assistant Built on Ollama**

## 1. Project Overview

I built an agentic AI assistant that turns a one-line project topic into a
complete content plan: a hook, a platform-specific post, hashtags, a video
script, titles and thumbnail text, a critique of its own output, and a saved
file. It runs entirely on my own machine through Ollama — no API key, no cloud,
no per-token cost, and no data leaving the laptop.

The point of the project was not text generation. It was building the machinery
that makes a small, unreliable local model produce dependable output: planning
its own tool sequence, repairing plans it gets wrong, and reviewing and
correcting its own work.

## 2. Tools and Technologies Used

Python, Ollama, `gemma3:4b`, Streamlit, JSON-based tool contracts. No hosted
model API anywhere in the stack.

I chose `gemma3:4b` over `llama3.1:8b` after running both across the same ten
test cases: gemma3 averaged about **108 s** per run against llama3.1's **145 s**,
with no noticeable drop in copy quality. On a 6 GB card the 4B model also sits
entirely in VRAM, where the 8B model competes with whatever else is resident —
a constraint that caused a real failure, described below.

## 3. Agent Design

The agent is given a tool menu and the user's request, and returns its own
execution plan as JSON. Nothing about the order is hardcoded. Ask for *a post*
and it omits the reel-script tool; ask for *a reel* and it includes it.

```
User input -> Planner (LLM) -> plan repair -> execute tools
                                   |
                            content_reviewer
                              PASS / REVISE
                                   |
                            file_saver (always last)
```

**Eight tools implemented**, against the brief's minimum of three:
`memory_recall`, `trend_idea_generator`, `caption_writer`, `hashtag_generator`,
`reel_script_generator`, `title_thumbnail_generator`, `content_reviewer` and
`file_saver`. Two of the eight — `file_saver` and `memory_recall` — call no
model at all. That mattered to me: an agent whose every tool is another LLM call
has not really left the chatbot behind.

Each tool declares what it requires and what it produces, so a plan can be
checked for executability *before* it runs rather than failing three tools in.

## 4. Results

| Metric | Value |
|---|---|
| Test cases run | 10 |
| Passed | **10 / 10** |
| Tools implemented | 8 (brief requires 3) |
| Saved outputs | 54 files across posts, scripts and results |
| Model | `gemma3:4b` via Ollama, fully local |
| Average run | ~108 s |

## 5. Testing and Error Analysis

Ten test cases across different topics, platforms, tones and output types. All
ten pass, where passing means every requested output was produced and saved,
with no tool errors and a reviewer score of 3 or above.

**Eight distinct failures were found and fixed during development.** The four
most instructive:

- **The agent invented a capability.** It described my helmet-detection project
  as a real-time rider alert system. It is not — it detects whether riders wear
  helmets. My prompt forbade inventing *metrics* but said nothing about
  inventing *capabilities*, and a 4B model fills a four-word topic with
  plausible fiction. Fixed with a grounding rule that overrides all other
  instructions, plus a fabrication check in the reviewer.

- **Self-correction made the output worse.** After one revision the reviewer's
  own score *fell* from 4.0 to 3.3: the model shortened the post to address a
  length complaint and stripped the substance out with it. I capped revision at
  a single pass and re-review after revising, so the saved file reports the post
  that actually shipped.

- **Fuzzy tool matching sent `caption_generator` to `hashtag_generator`.** Every
  tool name ends in `_generator` or `_writer`, so the shared suffix outweighed
  the meaningful word in character-level similarity. Fixed by weighting the head
  word decisively.

- **A request for a "short post" produced a video script — twice.** The check
  for whether the user wanted video matched the substring `short`, meant for
  *YouTube Shorts*, inside *short post*. Fixed with whole-word matching.

The hardest one to diagnose: both video cases failed with HTTP 500 even after
three retries. The real error was hidden inside the 500's body —
`prediction aborted, token repeat limit reached`. gemma3:4b falls into a
repetition loop on nested-JSON prompts, and retrying an identical request cannot
help. I measured it: temperature 0.7 loops, 0.95 does not, `num_predict` is
irrelevant, and `repeat_penalty` alone does **not** fix it — which is
counterintuitive, since that is the parameter whose name suggests it should. The
fix reads the error body, detects the repeat message and retries with
temperature raised by 0.2.

## 6. What I Learned

- **Most of the work in a local-model agent is error handling, not prompting.**
  The interesting code is the part that assumes the model will get it wrong.
- **A small model given a menu will invent items that are not on it.** Plans
  have to be repaired, not trusted: drop unknown tools, fuzzy-match near misses,
  enforce ordering, and guarantee the save step runs.
- **Self-correction is not free.** I assumed a review-and-revise loop could only
  improve things. It measurably made output worse, and I only knew because the
  reviewer scored both versions.
- **Read the whole error, not the status code.** An HTTP 500 that three retries
  could never fix turned out to carry the real cause in its body.
- **The counterintuitive result is the one worth reporting.** `repeat_penalty`
  not fixing a repeat loop is the single most useful thing I learned here, and I
  would not have believed it without testing it.

## 7. Future Improvements

- Let the agent call `memory_recall` on its own rather than only on request
- Stream tool output to the interface instead of printing on completion
- Add a larger model as an optional backend for users with more VRAM
- Expand the test suite beyond ten cases, with adversarial topics

## 8. LinkedIn Post Draft

> Today I completed AIRI Team PITB — AI Internship Task 2, where I built an
> agentic AI assistant that runs **entirely on my own machine**.
>
> **TrendPilot** turns a one-line project topic into a full content plan — hook,
> post, hashtags, video script, titles, a critique of its own output, and a
> saved file. No API key, no cloud, no per-token cost. Just Ollama and
> `gemma3:4b` on my laptop.
>
> It is an agent, not a chatbot: it is shown a menu of 8 tools and writes its
> own execution plan. Nothing about the order is hardcoded.
>
> The part I did not expect: **most of the work was error handling, not
> prompting.** A 4B model invents tools that do not exist, hallucinates
> capabilities your project does not have, and falls into token repeat loops on
> nested JSON. My favourite finding — `repeat_penalty` does *not* fix a repeat
> loop. Raising temperature does. I would not have believed that without
> measuring it.
>
> I also learned that self-correction can make things worse. After one revision
> pass, the reviewer's own score dropped from 4.0 to 3.3. I capped it at a
> single pass.
>
> 10/10 test cases passing, 8 documented failures and their fixes.
>
> Tools: Python · Ollama · gemma3:4b · Streamlit
>
> #AgenticAI #LocalLLM #Ollama #ArtificialIntelligence #MachineLearning #Python
> #AIRI #PITB #AIInternship

---

*Code, tests and full write-up: [link]*
