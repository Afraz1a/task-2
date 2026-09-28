"""
Prompt templates for every tool and for the planner.

Two things matter when prompting a 4B model, and both were learned the hard way
while building this:

  1. **Show the shape you want.** Describing a JSON schema in prose gets ignored;
     an explicit example of the object gets followed.
  2. **Constrain length in the prompt, not afterwards.** Asking for "a short
     reel script" yields 400 words. Asking for "4 scenes, max 20 words of
     voiceover per scene, 30 seconds total" yields something usable.

Every template below is a `.format()` string. Platform-specific rules are kept
separate so one tool can serve LinkedIn, Instagram, X and YouTube Shorts.
"""

SYSTEM = (
    "You are TrendPilot, a social-media content strategist. "
    "You write specific, concrete copy - never generic filler.\n\n"
    "GROUNDING RULE - this overrides everything else:\n"
    "Write only about what the topic literally says. Never invent capabilities, "
    "features, results, metrics or use-cases the user did not state. If the "
    "topic is short, write about the work itself - the building, the learning, "
    "the process - rather than inventing product features it does not have. "
    "A topic naming a detection system means software that detects things; it "
    "does not mean a device, an app, an alert system or a product, unless the "
    "user said so.\n\n"
    "When asked for JSON you reply with JSON only: no prose, no markdown fence."
)

# --------------------------------------------------------------- platforms
PLATFORM_RULES = {
    "LinkedIn": (
        "Professional but human. 120-200 words. Short paragraphs, one idea per "
        "line. A hook in the first line that works as a preview. No emoji spam - "
        "two at most. End with a question or a takeaway."),
    "Instagram": (
        "Visual-first and punchy. 60-120 words. Emoji are welcome. Line breaks "
        "between thoughts. Hashtags go at the end and can be numerous."),
    "X": (
        "Under 280 characters total. One sharp idea. No hashtag stuffing - two "
        "at most. Written to be quotable."),
    "YouTube Shorts": (
        "Spoken-word script, not prose. Written to be read aloud in 30-60 "
        "seconds. Direct address to the viewer."),
    "TikTok": (
        "Casual, fast, first person. Hook in the first 2 seconds. Written to be "
        "spoken, not read."),
    "Facebook": (
        "Conversational and accessible. 80-150 words. Plain language, no jargon."),
}

def platform_rule(platform: str) -> str:
    return PLATFORM_RULES.get(platform, PLATFORM_RULES["LinkedIn"])


# ----------------------------------------------------------------- planner
PLANNER = """A user wants social-media content. Decide which tools to run, and in what order.

USER REQUEST
  Topic:       {topic}
  Platform:    {platform}
  Tone:        {tone}
  Wants:       {output_type}

AVAILABLE TOOLS
{tool_menu}

RULES
- Choose only tools that serve what the user asked for. If they did not ask for
  a video or reel, do not run reel_script_generator.
- trend_idea_generator must come first if it is used - other tools build on its angle.
- content_reviewer must come second to last.
- file_saver must always be last, and must always be included.

Reply with JSON exactly like this:
{{"reasoning": "one sentence on why these tools", "plan": ["tool_name", "tool_name", "file_saver"]}}"""


# ------------------------------------------------------------------- tools
TREND_IDEAS = """Generate {n} distinct content angles for this topic.

Topic: {topic}
Platform: {platform}
Tone: {tone}

Each angle must be a different way into the story - for example a lesson
learned, a surprising result, a mistake, a before/after, a myth corrected.
Do not repeat the same idea in different words.

Every angle must be about the topic AS STATED. Do not invent features,
products, real-time alerts, hardware or commercial uses that were not mentioned.
If you are unsure what the project does, write about the process of building it.

Reply with JSON exactly like this:
{{"angles": [{{"angle": "short title", "why_it_works": "one sentence"}}]}}"""

PICK_ANGLE = """Choose the single strongest angle for {platform} with a {tone} tone.

Topic: {topic}

Angles:
{angles}

Pick the one most likely to stop someone scrolling. Prefer specific and
surprising over broad and safe.

Reply with JSON exactly like this:
{{"chosen": "the angle text", "hook": "the opening line of the post, max 20 words", "audience": "who this is for"}}"""

CAPTION = """Write the {platform} post.

Topic:    {topic}
Angle:    {angle}
Hook:     {hook}
Audience: {audience}
Tone:     {tone}

PLATFORM RULES: {rules}

Do not invent numbers, metrics or results that were not given to you, and do
not describe features the topic never mentioned. Writing about what it was like
to build the thing is always safe; describing what the thing can do is only safe
when the topic said so.
Open with the hook, exactly as written above.

Reply with JSON exactly like this:
{{"caption": "the full post text with \\n between paragraphs"}}"""

HASHTAGS = """Generate hashtags for this post.

Topic:    {topic}
Platform: {platform}
Angle:    {angle}

Mix three broad/high-reach tags with several specific/low-competition ones.
{count_rule}
No spaces inside a tag. No duplicates.

Reply with JSON exactly like this:
{{"hashtags": ["#Example", "#Another"]}}"""

REEL_SCRIPT = """Write a {seconds}-second video script.

Topic:    {topic}
Angle:    {angle}
Platform: {platform}
Tone:     {tone}

Exactly 4 scenes. Each scene: max 20 words of voiceover, and a concrete visual
the creator can actually film or screen-record. Scene 1 must hook in under 3
seconds. Scene 4 must end with a call to action.

Reply with JSON exactly like this:
{{"scenes": [{{"scene": 1, "visual": "what is on screen", "voiceover": "what is said"}}], "total_seconds": {seconds}}}"""

TITLE_THUMB = """Generate titles and thumbnail text.

Topic: {topic}
Angle: {angle}

Titles: 3 options, max 60 characters each, curiosity-driven, no clickbait lies.
Thumbnail text: 3 options, max 4 words each, readable on a phone screen.

Reply with JSON exactly like this:
{{"titles": ["..."], "thumbnail_texts": ["..."]}}"""

REVIEWER = """Review this {platform} content critically. You are the last check before it is published.

CONTENT
{content}

Check each of these and answer honestly - do not be polite:
1. Is the hook strong enough to stop a scroll?
2. Is it clear to someone outside the field?
3. Is the length right for {platform}? ({rules})
4. Does the tone match "{tone}"?
5. Are the hashtags relevant and not stuffed?
6. Does it claim any metric, result, feature or capability that the topic
   never mentioned? Be strict here - inventing what a project does is the worst
   failure on this list. Score 1 if anything is fabricated.

Score each 1-5. Anything scoring 3 or below must have a concrete fix, not a
vague suggestion.

Reply with JSON exactly like this:
{{"scores": {{"hook": 4, "clarity": 4, "length": 4, "tone": 4, "hashtags": 4, "no_invented_claims": 5}},
  "verdict": "PASS or REVISE",
  "problems": ["specific problem"],
  "fixes": ["specific, actionable fix"]}}"""

REVISE = """Rewrite this {platform} post to fix the reviewer's complaints. Keep what already works.

ORIGINAL POST
{caption}

REVIEWER PROBLEMS
{problems}

REQUIRED FIXES
{fixes}

PLATFORM RULES: {rules}
Do not invent numbers or results. Do not make it longer unless asked to.

Reply with JSON exactly like this:
{{"caption": "the rewritten post"}}"""

REVISE_SCRIPT = """Rewrite this video script to fix the reviewer's complaints about it.
Keep what already works - only fix what was flagged.

ORIGINAL SCRIPT (4 scenes)
{script}

REVIEWER PROBLEMS
{problems}

REQUIRED FIXES
{fixes}

Same rules as the original: exactly 4 scenes, max 20 words of voiceover per
scene, a concrete visual the creator can actually film or screen-record,
scene 1 hooks in under 3 seconds, scene 4 ends with a call to action. Do not
invent numbers or results.

Reply with JSON exactly like this:
{{"scenes": [{{"scene": 1, "visual": "what is on screen", "voiceover": "what is said"}}]}}"""
