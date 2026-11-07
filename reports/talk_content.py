"""
talk_content.py: the spoken words for both presentation options, in one place.

Where it fits
-------------
Shared by reports/build_slides.py (speaker notes in the PowerPoint) and
reports/build_scripts.py (the two Word speaker scripts), so the slides and the
scripts can never say different things. Edit the talk HERE, then rebuild both.

Two options (Dale, 2026-11-07), each 10 to 12 minutes of speaking + 3 minutes Q&A:
  OPTION_A  PowerPoint with a short live dashboard demo
  OPTION_B  Live dashboard walkthrough only (no slides)

Every number below was checked against the primary main run
(data/real/gp4_main_20261105_191049_analysis) and the two papers. If the
analysis changes, re-check the numbers here.

Speakers are a suggested split (EDIT HERE): Soni opens, Toner explains the
AI system, Warner presents results and closes. Swap names freely.
Writing rules: no em dashes; short spoken sentences; about 130 words a minute.
"""

from __future__ import annotations

WORDS_PER_MINUTE = 130  # CONFIG: comfortable presenting pace used for the timing estimates

SPEAKERS = {"S": "Krishna Soni", "T": "Michael Toner", "W": "Dale Warner"}  # EDIT HERE

DASHBOARD_URL = "https://gp4-saturation.streamlit.app/"
REPO_URL = "https://github.com/WarnerMBAN/gp4-sensory-marketing"

# ---------------------------------------------------------------------------
# Option A: PowerPoint + short live demo. One entry per slide.
# "actions" are stage directions, not spoken. "extra_seconds" covers clicking
# and pauses that word counts do not capture (demo, slide changes).
# ---------------------------------------------------------------------------
OPTION_A = [
    {"slide": 1, "title": "Can AI agents see what people see?", "speaker": "S", "extra_seconds": 5,
     "actions": [],
     "text": "Good morning. We are Group 1: Krishna Soni, Michael Toner and Dale Warner. Our question is simple: "
             "can AI agents see what people see? We took a published sensory marketing experiment and ran it "
             "again, with AI agents in place of people."},
    {"slide": 2, "title": "Does a more vivid colour make a product look bigger?", "speaker": "S", "extra_seconds": 0,
     "actions": [],
     "text": "Colour is one of the cheapest things a marketer controls. Changing the colour of a product, a package "
             "or an online photo costs almost nothing. Hagtvedt and Brasel asked whether colour saturation, "
             "meaning how vivid a colour is, changes how big a product looks. These are the two images from their "
             "study: the same red laptop, exactly the same size, once vivid and once muted. If vivid colour makes "
             "a product look bigger, that is a lever for packaging and online product photos, and a risk when "
             "you want something to look compact. What we measure is perceived size: how big people think the "
             "screen is."},
    {"slide": 3, "title": "The theory: saturation, arousal, attention, size", "speaker": "S", "extra_seconds": 0,
     "actions": [],
     "text": "Their explanation is a chain of three steps. Saturated colours are more arousing. Arousal draws "
             "attention. And things that hold our attention are judged to be larger. The authors confirmed this chain "
             "statistically. In Study 3, the one we "
             "replicated, 77 undergraduates each saw only one of the two images, a between-subjects design. They "
             "estimated the screen size from 10 to 20 inches, rated attention on two seven-point items, and "
             "reported arousal and mood on nine-point scales. Mood is a useful control: it is not part of the "
             "theory, so it should not change. Keep that in mind; it matters later."},
    {"slide": 4, "title": "Two human studies, two different answers on size", "speaker": "S", "extra_seconds": 5,
     "actions": [],
     "text": "Here is what people did. In the original study, the vivid laptop was judged almost an inch larger: "
             "15.3 versus 14.4 inches. Attention and arousal rose too, each with an effect size of about 0.3, a "
             "moderate effect. Mood did not move. But a 2022 replication with 823 adults in Japan found the "
             "attention and arousal effects again, and no size effect at all: an r of 0.01. So the two human "
             "benchmarks disagree on the headline result, which is why we compare our agents with both. "
             "Michael will now explain how we built the agents."},
    {"slide": 5, "title": "Our AI-agent system", "speaker": "T", "extra_seconds": 0,
     "actions": [],
     "text": "Thanks, Krishna. Each AI agent is one simulated participant: a single, separate call to OpenAI's "
             "GPT-4o mini, a vision model, so it actually looks at the image. We created 77 agents, the same as "
             "the original study, and randomly assigned 39 to the vivid image and 38 to the muted one, using a "
             "fixed seed so anyone can reproduce the assignment. Each agent gets a one-line persona, a male or "
             "female undergraduate student, 49 percent male like the original sample. Every call is fresh, with "
             "no memory of other agents, which reproduces the between-subjects design. The model must answer in "
             "a fixed format, and Python checks that every answer is a whole number inside its scale, retrying "
             "up to three times. Everything is logged. And one rule was non-negotiable: all settings were fixed "
             "and signed off before the first real run, so we could not tune the model to look more human. For every agent we record the model, the settings, a fingerprint of the prompt and of the image, the "
             "tokens, timestamps and the raw answer, so every number in this talk traces back to a single call."},
    {"slide": 6, "title": "What each agent sees, and what it never sees", "speaker": "T", "extra_seconds": 0,
     "actions": [],
     "text": "This is what an agent actually receives: the image, then the original questions, almost word for "
             "word. Estimate the screen size in whole inches from 10 to 20; rate two attention statements from "
             "one to seven; report arousal and mood from one to nine. Just as important is what the agent never "
             "gets. The prompt never mentions colour, saturation, the conditions or the hypothesis, and the image "
             "files have neutral names. Our code checks for forbidden words before any call. Some things we could "
             "not reproduce: the image is small and on screen rather than projected, there is no snack incentive, "
             "and a language model has no real eyes, attention or arousal. Every deviation is listed in our "
             "repository. We also ran 20 extra agents who were asked to explain their answers. That run is used only to "
             "interpret the results, never in the main analysis. Dale will now show you what the agents said."},
    {"slide": 7, "title": "The agents saw a big difference, almost like a switch", "speaker": "W", "extra_seconds": 0,
     "actions": [],
     "text": "Thanks, Michael. All 77 agents gave valid answers on the first try, and the whole run cost about "
             "four cents. Here is the headline. Agents who saw the vivid laptop estimated 14.7 inches; agents who "
             "saw the muted one estimated 13.3. That is a very large effect, an r of 0.70. But look at how they "
             "answered. Almost four out of five agents in the vivid group said exactly 15 inches, and more than "
             "four out of five in the muted group said exactly 13. People give a spread of answers. The agents "
             "behave almost like a switch. The spread tells the same story. The AI's standard deviation for size is about half of the humans', "
             "and for attention about a tenth. 86 percent of agents gave a set of answers identical to another "
             "agent's."},
    {"slide": 8, "title": "Right direction, wrong pattern", "speaker": "W", "extra_seconds": 5,
     "actions": [],
     "text": "This chart is the core of our comparison. Each row is a measure. Blue squares are the original "
             "study, orange diamonds the replication, and green circles our AI agents, each with a 95 percent "
             "confidence interval. On size, the AI effect is more than twice the original's, and nowhere near the "
             "replication's zero. On attention, the AI points the same way but the effect is small and not "
             "significant. Arousal is the real match, almost identical to the original. And mood, our control, "
             "moved for the AI when it did not move for people. Right direction, wrong pattern. The supposed "
             "mechanism through attention is not there. The statistics back this up. A Fisher z test shows the AI size effect is significantly larger than "
             "the original's. An equivalence test rules out the replication's no-effect result: the AI difference "
             "is 1.35 inches, far outside a half-inch band. And an accidental repeat run gave almost the same size "
             "effect, an r of 0.63, so this is stable, not a fluke. Let me show you this live."},
    {"slide": 9, "title": "Live demo: the dashboard", "speaker": "W", "extra_seconds": 35,
     "actions": ["Switch to the browser tab with the dashboard (already open, see the checklist).",
                 "Click 5. Human vs AI. Hover over the green Size circle to show the exact numbers.",
                 "Click 6. Explore data. Set Condition to high only: point at the column of 15s.",
                 "Switch back to PowerPoint, slide 10."],
     "text": "This is our dashboard, public at gp4 saturation dot streamlit dot app. Everything we just showed is "
             "here and interactive. On the Human versus AI page, hovering shows the exact effect sizes. On the "
             "Explore data page you can see every agent's answers. Filter to the vivid condition and look at the "
             "screen sizes: fifteen, fifteen, fifteen."},
    {"slide": 10, "title": "Why would AI agents behave like this?", "speaker": "W", "extra_seconds": 0,
     "actions": [],
     "text": "Why would AI behave like this? The model has no eyes and no nervous system. Our best explanation "
             "is that it maps a vivid image onto learned associations, vivid, premium, bigger, and then gives "
             "the single most typical answer, which removes the natural spread that people show. We checked this "
             "with 20 extra agents who explained their answers: all 20 talked about colour and style, and not "
             "one mentioned size. Krishna will wrap up."},
    {"slide": 11, "title": "What we learned", "speaker": "S", "extra_seconds": 5,
     "actions": [],
     "text": "Thanks, Dale. So, can AI agents see what people see? Partly. They pick up the direction of the "
             "colour effect and they match human arousal. But they exaggerate the size effect, miss the attention mechanism, react "
             "on mood when they should not, and give nearly identical answers. Our advice to researchers: AI "
             "agents are a fast, cheap first look at whether a visual cue matters, not a substitute for people, "
             "and their effect sizes should not be trusted."
             " What should researchers be careful about? Fix the settings before looking at results, never reveal "
             "the hypothesis, send the real stimulus, and compare effects, not just averages, because a similar "
             "average can hide a very different pattern. Our main limitations are one model, one prompt, and "
             "published summary statistics instead of raw human data. Thank you. We are happy to take questions."},
    {"slide": 12, "title": "Questions", "speaker": "S", "extra_seconds": 0, "actions": ["Leave this slide up for Q&A."],
     "text": ""},
]

# ---------------------------------------------------------------------------
# Option B: live dashboard only. One entry per dashboard page (or part of one).
# ---------------------------------------------------------------------------
OPTION_B = [
    {"page": "1. Overview", "speaker": "S", "extra_seconds": 10,
     "actions": ["Dashboard already open on 1. Overview, sidebar shows REAL | main | 2026-11-05 19:10."],
     "text": "Good morning. We are Group 1: Krishna Soni, Michael Toner and Dale Warner, and this is our live "
             "dashboard. Our question, from the course brief: to what extent can AI agents reproduce human perceptions and "
             "sensory marketing effects? Put simply, can AI agents see what people see? We took a published sensory marketing "
             "experiment and ran it again with AI agents in place of people. The marketing problem is on screen. "
             "Colour is one of the cheapest things a marketer controls. Hagtvedt and Brasel asked whether colour "
             "saturation, how vivid a colour is, changes how big a product looks. If it does, that is a lever "
             "for packaging and product photos. The seven pages on the left follow our story: the original study, our AI system, the results, the "
             "comparison with people, and what it means. The box on the left gives away our answer, Pattern D, and the "
             "table shows why. We will come back to both."},
    {"page": "2. Original study", "speaker": "S", "extra_seconds": 15,
     "actions": ["Click 2. Original study.", "Point at the two laptop images.",
                 "Scroll to the human results table, then to Proposed mechanism."],
     "text": "These are the two images from the study: the same red laptop, exactly the same size, vivid on the "
             "left and muted on the right. In Study 3, 77 undergraduates each saw only one image. They estimated "
             "the screen size from 10 to 20 inches, rated attention on two seven-point items, and reported "
             "arousal and mood on nine-point scales. Mood is a control: it should not change. In the original, "
             "the vivid laptop was judged almost an inch larger, 15.3 versus 14.4 inches, and attention and "
             "arousal rose too, each with an effect size of about 0.3. The proposed mechanism is a chain: "
             "saturation raises arousal, arousal draws attention, and attention makes things look bigger, and the authors "
             "confirmed that chain statistically. But a 2022 replication with 823 adults in Japan found the attention and arousal effects and no size "
             "effect at all. That sample was different: online adults, surveyed in Japanese, with a seven-point arousal "
             "scale, so for arousal we compare effect sizes only. The two human benchmarks disagree, so we "
             "compare our agents with both. Michael "
             "will now explain the agents."},
    {"page": "3. AI-agent system", "speaker": "T", "extra_seconds": 20,
     "actions": ["Click 3. AI-agent system. Point along the flow diagram from left to right.",
                 "Scroll to Settings for this run, then to Exact prompt (version v1).",
                 "Open the Deviations expander for a few seconds, then close it."],
     "text": "Thanks, Krishna. This diagram is our whole system, left to right. Each AI agent is one simulated "
             "participant: a single, separate call to OpenAI's GPT-4o mini, a vision model, so it actually looks "
             "at the image. We created 77 agents and randomly assigned 39 to the vivid image and 38 to the muted "
             "one, with a fixed seed. Each agent gets a one-line persona, a male or female undergraduate, 49 "
             "percent male. Every call is fresh, with no memory of other agents. Here are the settings, and here "
             "is the exact prompt: the original questions, almost word for word. It never mentions colour, "
             "saturation, the conditions or the hypothesis, and the image files have neutral names. Answers must "
             "come back in a fixed format; Python checks every one and retries up to three times. All settings "
             "were signed off before the first real run, so we could not tune the model to look more human. For every agent we record the model, the settings, a fingerprint of the prompt and of the image, the "
             "tokens, timestamps and the raw answer, so every number in this talk traces back to a single call. "
             "What we could not reproduce is listed here: a small on-screen image, no snack incentive, and no "
             "real eyes or arousal. We also ran 20 extra agents who were asked to explain their answers. That run is used only to "
             "interpret the results, never in the main analysis. Dale will show the results."},
    {"page": "4. Results", "speaker": "W", "extra_seconds": 15,
     "actions": ["Click 4. Results. Point at the Data quality boxes.",
                 "On the Size tab, scroll to the screen-size bar chart.",
                 "Click the Mood (placebo) tab briefly."],
     "text": "Thanks, Michael. All 77 agents gave valid answers on the first try, and the run cost about four "
             "cents. On size, agents who saw the vivid laptop estimated 14.7 inches, and those who saw the muted "
             "one 13.3: a very large effect. This bar chart shows how they answered. Almost four out of five "
             "vivid-group agents said exactly 15 inches, and more than four out of five muted-group agents said "
             "exactly 13. People give a spread of answers; the agents behave almost like a switch. The spread tells the same story. The AI's standard deviation for size is about half of the humans', "
             "and for attention about a tenth. 86 percent of agents gave a set of answers identical to another "
             "agent's. On the arousal tab, the AI difference is close to the human one. And on the "
             "mood tab, the control measure, the AI moved when people did not."},
    {"page": "5. Human vs AI", "speaker": "W", "extra_seconds": 15,
     "actions": ["Click 5. Human vs AI. Hover over the green Size circle.",
                 "Scroll to Outcome: pattern D."],
     "text": "This chart is the core of our comparison. Blue squares are the original study, orange diamonds the "
             "replication, green circles our agents, each with a 95 percent confidence interval. On size, the "
             "AI effect is more than twice the original's and nowhere near the replication's zero. On attention "
             "it points the same way but is small and not significant. Arousal is the real match, almost "
             "identical to the original. And mood moved when it should not. That is our outcome, pattern D: "
             "exaggerated, with a halo. Right direction, wrong pattern. The statistics back this up. A Fisher z test shows the AI size effect is significantly larger than "
             "the original's. An equivalence test rules out the replication's no-effect result: the AI difference "
             "is 1.35 inches, far outside a half-inch band. And an accidental repeat run gave almost the same size "
             "effect, an r of 0.63, so this is stable, not a fluke."},
    {"page": "6. Explore data", "speaker": "W", "extra_seconds": 15,
     "actions": ["Click 6. Explore data. Set Condition to high only; point at the screen_size column."],
     "text": "Every agent's answers are here, with the variable dictionary, and you can download the full file."
             " That is our AI-generated dataset. Filter to the vivid condition and look "
             "at the screen sizes: fifteen, fifteen, fifteen. Why? The model has no eyes. Our best explanation is "
             "that it maps a vivid image onto learned associations, vivid, premium, bigger, and gives the most "
             "typical answer. In 20 extra agents who explained themselves, all 20 talked about colour and style, "
             "and none mentioned size. Krishna will wrap up."},
    {"page": "7. Limitations", "speaker": "S", "extra_seconds": 10,
     "actions": ["Click 7. Limitations. Leave it on screen for Q&A."],
     "text": "Thanks, Dale. So, can AI agents see what people see? Partly. They pick up the direction of the "
             "colour effect and match human arousal, but they exaggerate size, miss the attention mechanism, react on mood, and "
             "give nearly identical answers. AI agents are a fast, cheap first look at whether a visual cue "
             "matters, not a substitute for people. What should researchers be careful about? Fix the settings before looking at results, never reveal "
             "the hypothesis, send the real stimulus, and compare effects, not just averages, because a similar "
             "average can hide a very different pattern. Our main "
             "limitations are one model, one prompt, and summary statistics instead of raw human data. Thank you; "
             "we are happy to take questions."},
]

# ---------------------------------------------------------------------------
# Likely questions with short answers (both options)
# ---------------------------------------------------------------------------
QA = [
    ("Did the model simply know the paper?",
     "Possible, and we cannot rule it out. But the prompt never names the paper, colour or saturation, the image "
     "file names are neutral, and in the 20-agent diagnostic run no explanation mentioned size or the study."),
    ("Is a bigger AI effect (r = .70) a better result?",
     "No. Bigger is not more human. People in the original showed r = .30 and the large replication showed none. "
     "The AI overshoots both, with almost no spread in its answers."),
    ("Why GPT-4o mini, and why temperature 1.0?",
     "It sees images and is cheap enough to run every agent separately. Temperature 1.0 lets answers vary the "
     "way people's do. Both were fixed and signed off before the first real run and never tuned to match humans."),
    ("How can you compare with humans without raw data?",
     "We compare effect sizes (r) with 95% confidence intervals and test the difference with a Fisher z test. "
     "Per-cell sample sizes are not published, so we assume an even split and say so."),
    ("Why is attention not significant when arousal is?",
     "The AI's attention answers barely varied: a standard deviation of about 0.1, against about 1.0 for people. "
     "With so little spread, the test has nothing to work with."),
    ("Why not CrewAI, as in the class demo?",
     "We needed the model to see the real image, so we call OpenAI's API directly behind a swappable client. "
     "We have asked Dr. Zhang to confirm this is acceptable."),
    ("Would more agents change the result?",
     "The main run matches the original's 77. An accidental second run of 77 gave a similar size effect "
     "(r = .63). A run at the replication's 823 would cost about 43 cents; we have asked whether to report it."),
    ("What does the mood result mean?",
     "Mood is not part of the theory, so it should not differ. For people it did not; for the AI it did. That "
     "suggests a halo: the agents rate everything about the vivid laptop more positively."),
    ("What would you do next?",
     "Test other models and prompt wordings as a new, pre-declared version; run at the replication's sample "
     "size; and compare against raw human data if it becomes available."),
]


def words(text: str) -> int:
    """Spoken word count."""
    return len(text.split())


def seconds(entry: dict) -> float:
    """Estimated speaking time for one slide or page, including clicks and pauses."""
    return 60 * words(entry["text"]) / WORDS_PER_MINUTE + entry.get("extra_seconds", 0)


def mmss(total_seconds: float) -> str:
    total = int(round(total_seconds))
    return f"{total // 60}:{total % 60:02d}"


if __name__ == "__main__":
    for name, option in (("Option A", OPTION_A), ("Option B", OPTION_B)):
        total = sum(seconds(e) for e in option)
        print(f"{name}: {sum(words(e['text']) for e in option)} words, about {mmss(total)} "
              f"(at {WORDS_PER_MINUTE} words a minute, with clicks)")
        for key, who in SPEAKERS.items():
            part = sum(seconds(e) for e in option if e["speaker"] == key)
            print(f"   {who}: {mmss(part)}")
