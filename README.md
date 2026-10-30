# AI Study Plan

A skill for **terminal AI agents** (AI coding agents / agentic CLIs such as Claude Code, Codex CLI, Gemini CLI, OpenCode …) that turns your study materials into a **day-by-day study plan up to your exam** and writes it straight into the Anki add-on [**Smart Study**](https://github.com/TruckDrive/smart-study). You only say *what* you study, *when* the exam is and *how long* you want to study per day.

## What you get

- **A finished plan in Anki**: every day with reviews, script pages, the **videos of the day** (as a link you click in Anki) and new cards.
- **Everything in the right order**: script chapters, lecture videos and Anki subdecks are bundled into topics. Each topic is scheduled as *read → watch the video → learn the cards*, so you watch a video on exactly the day you learn the cards for it.
- **Videos from Moodle, linked, never downloaded**: a separate login window opens, **you** log in, and the skill reads the titles, links and the **real video length** from the course page.
- **Real numbers**: the plan uses your actual new-card counts and Anki's review forecast, so review time is planned too. Anki may stay open (the skill reads a copy of your collection).
- **The add-on's own planning**: the plan looks exactly as if you had clicked *Create plan* in the add-on, with weak-spot round, mock exam and a light last day.
- **On all your devices**: the add-on keeps the plan in your Anki collection too, so AnkiWeb sync brings it to your laptop.
- **Extend instead of starting over**: add videos or decks to an existing plan; everything you already did stays ticked off. Fell behind? One command spreads the rest from today on.

## Example

[`examples/example-plan.json`](examples/example-plan.json) is a small plan file the skill writes before scheduling. After scheduling, a day in the add-on looks like this:

```
2026-10-27  (2.9 h)
  [ ] Reviews (approx. 95)                                   28 min
  [ ] Shoulder joint  (Moodle videos)                         5 min
        https://moodle.example.edu/mod/lti/view.php?id=101
  [ ] 23 new cards · Joints: shoulder  (Joints)              23 min
  [ ] Elbow joint  (Moodle videos)                            6 min
        https://moodle.example.edu/mod/lti/view.php?id=102
  [ ] 27 new cards · Joints: elbow  (Joints)                 27 min
```

## How it works

1. **Take stock:** existing plans in the add-on, your Anki decks with their new-card counts, and the chapters of your scripts (converted to Markdown with `markitdown`).
2. **Ask briefly:** exam date, study time per day, days off, which decks belong to it – only what you haven't said yet.
3. **Read Moodle:** `moodle_links.mjs` opens the course in a separate Chromium profile. If you're not logged in, a window opens and you log in yourself. It then lists the activities, opens only the video player pages (never files) and reads each video's length.
4. **Build topics:** chapters + videos + subdecks that belong together.
5. **Schedule:** `study_plan.py` runs the add-on's own planner on a copy of your collection, shows a dry run, and after your OK saves the plan into the add-on (with a backup of the old one).

## Requirements

- A terminal AI agent that can read files and run shell commands. Skill support is a plus, but not required.
- Linux or macOS
- [Anki](https://apps.ankiweb.net) 23.10+ with the [Smart Study](https://github.com/TruckDrive/smart-study) add-on
- Anki's Python library (`python3 -c "import anki"` must work; Linux packages ship it, otherwise `pip install anki`)
- Python 3, [Node.js](https://nodejs.org) 22+ and Chromium or Chrome (for the Moodle login window)
- [`markitdown`](https://github.com/microsoft/markitdown): `pipx install 'markitdown[all]'`, and `poppler` (`sudo pacman -S poppler` / `sudo apt install poppler-utils` / `brew install poppler`)

## Installation

```bash
git clone https://github.com/blackpaired/ai-study-plan.git
cd ai-study-plan
bash install.sh
```

By default the script copies the skill to `~/.claude/skills/study-plan/`, a folder several AI tools read skills from (`SKILL.md` is an open format used by many AI agents). If your AI tool loads skills from a different folder, pass it:

```bash
bash install.sh ~/.my-ai-tool/skills
```

The script also checks for Anki's Python library, the add-on and the other programs.

To install by hand instead:

```bash
mkdir -p <skills-folder>
cp -r skills/study-plan <skills-folder>/
chmod +x <skills-folder>/study-plan/*.sh <skills-folder>/study-plan/*.py <skills-folder>/study-plan/*.mjs
```

Then restart your AI agent.

**Tool without skill support?** It still works: tell the AI *"follow the instructions in `<skills-folder>/study-plan/SKILL.md`: plan ~/Documents/Anatomy/ until 5 November, 4 hours a day"*.

## Use in AI chat apps

This skill needs your local Anki (add-on folder and collection), so it only works fully in a terminal AI agent. In AI chat apps that accept skills as a ZIP (download **`study-plan.zip`** from the [latest release](https://github.com/blackpaired/ai-study-plan/releases/latest)), the AI makes the same plan as a day-by-day table that you can enter in the add-on by hand.

Some apps allow only 200 characters for a skill description, so the ZIP has a shorter one. To build the ZIP yourself: `bash package_zip.sh` (creates `dist/study-plan.zip`).

## Usage

In your AI agent type:

```
/study-plan ~/Documents/Anatomy/
```

Plain language works too:

- *"Make me a study plan until 5 November, 4 hours a day, Sundays off, with the videos from https://moodle.example.edu/course/view.php?id=1007"*
- *"Add the Moodle videos to my anatomy plan"*
- *"I missed two days, plan the rest again"*

Then open **Tools → Smart Study → Study Plan** in Anki.

### The helper scripts on their own

```bash
python3 -I <skills-folder>/study-plan/study_plan.py decks anatomy          # decks with total / new cards
python3 -I <skills-folder>/study-plan/study_plan.py build plan.json --dry-run
python3 -I <skills-folder>/study-plan/study_plan.py show <plan-id>
python3 -I <skills-folder>/study-plan/study_plan.py replan <plan-id>
node <skills-folder>/study-plan/moodle_links.mjs login "<course-url>"
node <skills-folder>/study-plan/moodle_links.mjs videos "<course-url>" --deep --json course.json
```

## Works well with

- [smart-study](https://github.com/TruckDrive/smart-study): the Anki add-on this skill fills.
- [ai-study-anki](https://github.com/blackpaired/ai-study-anki): turns your materials into Anki cards for the plan.
- [ai-study-notes](https://github.com/blackpaired/ai-study-notes): study notes that explain the connections, exported as a PDF.
- [ai-study-tutor](https://github.com/blackpaired/ai-study-tutor): teaches you the material step by step.
- [ai-study-quiz](https://github.com/blackpaired/ai-study-quiz): quizzes you like an oral examiner.

## Important

- **Your password stays with you.** You log in to Moodle yourself in the login window; the AI never types it. The login is kept in a separate browser profile (`~/.local/share/study-plan-browser`); delete that folder to log out completely. While the login window runs, it listens on a local port (127.0.0.1:9233) only.
- **Nothing is downloaded** from Moodle: only titles, links and video lengths are read. Respect your university's terms of use.
- Your Anki collection is never changed; only the add-on's plan file is written (with a backup).
- The AI can make mistakes. Check the dry run before saving.
- Every session uses your AI usage (tokens / plan limits).

---

*This repo was created with the help of Claude Opus 5.5.*
