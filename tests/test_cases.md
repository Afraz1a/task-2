# Test cases

**Model:** `gemma3:4b`  
**Run at:** 2026-09-28T04:40:45  
**Total time:** 742.2s (74.2s per case)  
**Result:** 10/10 passed

`PASS` means the agent produced and saved every output that was asked for, with no tool errors and a reviewer score of 3 or above. `PARTIAL` means a file was still saved but something was missing. Whether the copy reads *well* is a separate, human judgement - see the error analysis in the report.

| # | Topic | Platform | Tone | Asked for | Tools used | Result | Review | Saved |
|---|---|---|---|---|---|---|---|---|
| 1 | YOLOv8 helmet detection | LinkedIn | professional | post and hashtags | trend idea, caption writer, hashtag, content reviewer, file saver | **PASS** | REVISE 3.67/5 | `yolov8_helmet_detection_linkedin_20260928_042930.md` |
| 2 | AI internship experience | LinkedIn | motivational | post | trend idea, caption writer, content reviewer, file saver | **PASS** | REVISE 3.17/5 | `ai_internship_experience_linkedin_20260928_043034.md` |
| 3 | Python learning journey | Instagram | funny | reel script | trend idea, reel script, caption writer, hashtag, title thumbnail, content reviewer, file saver | **PASS** | REVISE 4.33/5 | `python_learning_journey_instagram_20260928_043205.md` |
| 4 | Machine learning project | X | short and catchy | short post | trend idea, caption writer, hashtag, content reviewer, file saver | **PASS** | REVISE 3.17/5 | `machine_learning_project_x_20260928_043304.md` |
| 5 | Data annotation struggles | LinkedIn | humorous | post | trend idea, caption writer, content reviewer, file saver | **PASS** | REVISE 3.17/5 | `data_annotation_struggles_linkedin_20260928_043411.md` |
| 6 | Model failed in production | Instagram | meme style | reel script | trend idea, reel script, hashtag, content reviewer, file saver | **PASS** | REVISE 3.67/5 | `model_failed_in_production_instagram_20260928_043508.md` |
| 7 | Final year project | LinkedIn | professional | portfolio post | trend idea, caption writer, hashtag, title thumbnail, content reviewer, file saver | **PASS** | REVISE 3.33/5 | `final_year_project_linkedin_20260928_043623.md` |
| 8 | Computer vision project | YouTube Shorts | exciting | video script | trend idea, reel script, caption writer, hashtag, title thumbnail, content reviewer, file saver | **PASS** | REVISE 3.83/5 | `computer_vision_project_youtube_shorts_20260928_043821.md` |
| 9 | Debugging FastAPI | X | funny | short post | trend idea, caption writer, hashtag, content reviewer, file saver | **PASS** | REVISE 3.33/5 | `debugging_fastapi_x_20260928_043936.md` |
| 10 | Open-source contribution | LinkedIn | inspirational | post | trend idea, caption writer, hashtag, content reviewer, file saver | **PASS** | REVISE 3.5/5 | `open_source_contribution_linkedin_20260928_044045.md` |

## Per-case detail

### Test 1 — YOLOv8 helmet detection

- **Input:** platform `LinkedIn`, tone `professional`, asked for `post and hashtags`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'hashtag_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, hashtag_generator, content_reviewer, file_saver
- **Output size:** 115 caption words, 6 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.67/5), revised once
- **Time:** 67.5s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** Hook is weak and doesn’t immediately convey the core finding.; The explanation of the bias could be simplified for a broader audience.; Hashtags are somewhat redundant – ‘AI’ is too generic.

### Test 2 — AI internship experience

- **Input:** platform `LinkedIn`, tone `motivational`, asked for `post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, content_reviewer, file_saver
- **Output size:** 106 caption words, 0 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.17/5), revised once
- **Time:** 63.4s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** Hook is weak and generic. ‘A wall’ is overused. The initial sentence doesn’t immediately grab attention. ‘Iterative exploration’ is repeated unnecessarily. The description lacks a specific, engaging detail about the work. The concluding sentence feels tacked on and doesn’t offer a strong takeaway.

### Test 3 — Python learning journey

- **Input:** platform `Instagram`, tone `funny`, asked for `reel script`
- **Plan the model proposed:** `['trend_idea_generator', 'reel_script_generator', 'caption_writer', 'hashtag_generator', 'title_thumbnail_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, reel_script_generator, caption_writer, hashtag_generator, title_thumbnail_generator, content_reviewer, file_saver
- **Output size:** 96 caption words, 12 hashtags, 4 scenes
- **Reviewer:** REVISE (avg 4.33/5), revised once
- **Time:** 91.0s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** The hook is weak. ‘My Python code almost broke me’ is a cliché and doesn’t immediately grab attention. It relies on a common, slightly overused sentiment.; While clear for someone in the field, the explanation of a syntax error could be more concise and directly tied to the visual. It’s a bit verbose.; The reel script is good, but scene 4 feels slightly forced – the ‘Want to tame the syntax?’ is a call to action that could be more integrated naturally into the narrative.

### Test 4 — Machine learning project

- **Input:** platform `X`, tone `short and catchy`, asked for `short post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'hashtag_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, hashtag_generator, content_reviewer, file_saver
- **Output size:** 15 caption words, 3 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.17/5), revised once
- **Time:** 59.5s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** The hook is weak and relies on a slightly odd observation. It needs a stronger, more engaging element.; The caption is too long for X. It needs significant trimming to focus on the core idea.; The tone is neutral and doesn’t fully capture ‘short and catchy’.

### Test 5 — Data annotation struggles

- **Input:** platform `LinkedIn`, tone `humorous`, asked for `post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, content_reviewer, file_saver
- **Output size:** 100 caption words, 0 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.17/5), revised once
- **Time:** 66.7s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** Hook is weak and doesn't preview the content effectively.; The language is somewhat dry and lacks impact. It reads like a project report, not a compelling LinkedIn post.; Paragraphs are too long. LinkedIn users scan, not read lengthy blocks of text.

### Test 6 — Model failed in production

- **Input:** platform `Instagram`, tone `meme style`, asked for `reel script`
- **Plan the model proposed:** `['trend_idea_generator', 'reel_script_generator', 'hashtag_generator', 'file_saver']`
- **Tools called:** trend_idea_generator, reel_script_generator, hashtag_generator, content_reviewer, file_saver
- **Output size:** 0 caption words, 12 hashtags, 4 scenes
- **Reviewer:** REVISE (avg 3.67/5)
- **Time:** 57.7s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** The hook is weak. The 'Model Failed' message is a common, somewhat cliché error. It needs a more immediate, surprising element to grab attention. The zoom is standard but doesn’t add much.; While generally understandable, the script relies heavily on jargon ('model meltdown', 'training data'). A broader audience won’t immediately grasp the core issue – poor data quality.; The length is acceptable, but could be tightened. The voiceover in Scene 2 is particularly wordy.

### Test 7 — Final year project

- **Input:** platform `LinkedIn`, tone `professional`, asked for `portfolio post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'hashtag_generator', 'title_thumbnail_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, hashtag_generator, title_thumbnail_generator, content_reviewer, file_saver
- **Output size:** 91 caption words, 3 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.33/5), revised once
- **Time:** 74.2s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** The hook is weak and doesn’t immediately grab attention. It states a fact rather than posing a question or highlighting intrigue. The phrasing ‘I uncovered’ is passive and doesn’t convey excitement. The description of the research feels like an afterthought. Clarity could be improved for someone outside sustainable fashion – ‘upcycled denim jackets with QR codes’ needs a little context. The length is borderline, but could be tightened. The hashtags are a little heavy on the generic ones.

### Test 8 — Computer vision project

- **Input:** platform `YouTube Shorts`, tone `exciting`, asked for `video script`
- **Plan the model proposed:** `['reel_script_generator', 'caption_writer', 'hashtag_generator', 'title_thumbnail_generator', 'content_reviewer', 'file_saver']`
- **Plan repairs applied:** inserted trend_idea_generator - writer tools need an angle
- **Tools called:** trend_idea_generator, reel_script_generator, caption_writer, hashtag_generator, title_thumbnail_generator, content_reviewer, file_saver
- **Output size:** 87 caption words, 5 hashtags, 4 scenes
- **Reviewer:** REVISE (avg 3.83/5), revised once
- **Time:** 118.7s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** The initial caption’s ‘Hey tech enthusiasts!’ feels immediately out of place in a short. It’s too conversational and doesn’t immediately grab attention. The ‘Wow, look at that!’ feels forced and doesn’t add value. The voiceover in scene 1 is overly dramatic and doesn’t directly relate to the visual. The ‘Let us know in the comments…’ call to action is weak and doesn’t leverage the short format effectively.; The script relies heavily on explaining *how* the system works, which is dense and potentially confusing for a general audience. It’s explaining the *process* of computer vision, not showcasing the output.; The ‘Want to see what your cameras detect? Subscribe now!’ is a generic call to action and doesn’t build excitement or curiosity.

### Test 9 — Debugging FastAPI

- **Input:** platform `X`, tone `funny`, asked for `short post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'hashtag_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, hashtag_generator, content_reviewer, file_saver
- **Output size:** 11 caption words, 3 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.33/5), revised once
- **Time:** 74.3s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** Caption is too long and lacks a strong hook. The 'rubber duck' reference is vague and doesn't immediately resonate. The emoji is unnecessary and doesn't add value.; The caption needs to be more concise and directly address the frustration of FastAPI debugging. It’s not immediately clear to someone outside the field why this is a problem.; The caption exceeds the character limit.

### Test 10 — Open-source contribution

- **Input:** platform `LinkedIn`, tone `inspirational`, asked for `post`
- **Plan the model proposed:** `['trend_idea_generator', 'caption_writer', 'hashtag_generator', 'content_reviewer', 'file_saver']`
- **Tools called:** trend_idea_generator, caption_writer, hashtag_generator, content_reviewer, file_saver
- **Output size:** 108 caption words, 6 hashtags, 0 scenes
- **Reviewer:** REVISE (avg 3.5/5), revised once
- **Time:** 69.2s
- **Result:** PASS — all requested outputs produced and saved
- **Reviewer flagged:** Hook is weak and relies on a negative experience. The opening doesn't immediately grab attention. The phrasing ‘nearly derailed my week’ is a bit melodramatic and doesn’t immediately convey value. The ‘unexpectedly’ feels forced. The description of the communication – ‘focused communication’ – is vague and doesn’t illustrate the actual process. The tone is slightly too earnest and leans into inspirational without concrete detail. The hashtags are a bit broad and could be more targeted.

## Model call statistics

| Metric | Value |
|---|---|
| calls | 83 |
| repeat loop | 1 |
| seconds | 471 |
