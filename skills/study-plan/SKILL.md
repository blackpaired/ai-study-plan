---
name: study-plan
description: Turns lecture notes, Moodle videos and Anki decks into a day-by-day study plan up to the exam and writes it straight into the Anki add-on "Smart Study Plan" – pages, linked videos and new cards per day, fitted to the daily study time and the exam date. Reads videos from Moodle through a login window the user signs into (links only, no downloads), bundles chapters, videos and Anki subdecks into topics and lets the add-on schedule them. Can also extend an existing plan (e.g. add videos). Use when the user says "study plan", "exam plan", "exam prep", "plan this until my exam", "put this into my Anki", "add the videos to my plan", or invokes /study-plan.
---

# Study plan – from your materials to a finished plan in Anki

The user is studying for an exam and uses **Anki** with the add-on **Smart Study Plan** (window via Tools → Study Plan… or the "Study Plan" link at the top of Anki). You build a plan that shows up there ready to use: every day with reviews, script pages, the videos of the day (as a clickable link) and new cards.
Language: the language the user writes in, short and relaxed.
Goal: the user only says **what** (files, Moodle course, decks), **until when** (exam) and **how long per day** – you do the rest.

Argument (optional): folders/files, Moodle link, exam date, study time. Ask for what is missing in step 2.

**Running in a chat app** (no local Anki, no shell): this skill needs local access to Anki's add-on folder and collection. Explain that briefly and offer the plan as a day-by-day Markdown table instead (same rules for topics and videos), which the user can enter in the add-on by hand.

Helper scripts in this skill's folder (always go through them, never touch the collection directly):
```bash
python3 -I <skill-folder>/study_plan.py addon                       # add-on folder + existing plans
python3 -I <skill-folder>/study_plan.py decks [word]                # decks with card counts (total / new)
python3 -I <skill-folder>/study_plan.py build <plan.json> --dry-run # schedule and show, save nothing
python3 -I <skill-folder>/study_plan.py build <plan.json>           # schedule and save into the add-on
python3 -I <skill-folder>/study_plan.py show <plan-id>              # saved plan day by day
python3 -I <skill-folder>/study_plan.py replan <plan-id>            # spread again from today on
node <skill-folder>/moodle_links.mjs login "<course-url>"            # login window, the user signs in
node <skill-folder>/moodle_links.mjs videos "<course-url>" --deep --json <file>
```
`study_plan.py` reads Anki from a **copy** of the collection (Anki may stay open) and schedules with the add-on's own code – so the plan is the same as if the user had clicked "Create plan" in the add-on. An existing plan is backed up first (`<id>.json.bak-<time>`); finished items are kept.

## Ground rules

1. **Link videos, never download them.** The plan gets the Moodle link of the video (or activity). Never save files from Moodle.
2. **Invent nothing.** Video titles, lengths, chapters and page numbers only from Moodle, the materials or the decks. If a length is missing, use the source's default length (`defaultMin`) and say so in the summary.
3. **The user logs in.** Never type a password or fill in a login page. If the course needs a login, open the login window and let the user sign in.
4. **Dry run first, then save.** Always `--dry-run` first, show it briefly, fix overload, then save.
5. **Respect existing plans.** If there already is a plan for the same exam (`addon`), **extend** it (same `id`, keep existing sources, topics and finished items) instead of creating a new one.

## Workflow

### 1. Take stock
- `study_plan.py addon`: which plans exist? If one fits the exam, look at it with `show` and use its JSON (in the add-on folder `user_files/plans/<id>.json`) as the base.
- Convert the scripts to .md to find chapters and page numbers:
  ```bash
  <skill-folder>/to_md.sh "<folder-or-file>"
  ```
  The table of contents (or the headings) gives the topics with page ranges. For scans, render the first pages as images (`pdftoppm -r 100 -png -f 1 -l 6 file.pdf <temp-folder>/toc`) and look at them yourself. Never modify the originals.
- `study_plan.py decks <word>`: matching Anki decks and subdecks with the number of new cards.

### 2. Ask briefly (one round of multiple-choice questions if your tool has them, max. 4, only what is missing)
- **Exam:** date (and time if known), interim dates (credit tests, dissection labs)
- **Study time per day** (e.g. 2 h / 4 h / 6 h / 8 h) and **days off** (e.g. Sunday)
- **Anki decks:** which of the decks found belong to it, which are only reviewed (`reviewOnly`)
- **Start:** today (recommended) or another date
If the user skips this or says "just do it": start today, exam date from what they said, 4 h/day, no days off – and say so.

### 3. Get the videos from Moodle (links only)
```bash
node <skill-folder>/moodle_links.mjs videos "<course-url>" --deep --json <temp-folder>/course.json
```
- Exit code 2 ("Not logged in"): run `moodle_links.mjs login "<course-url>"`, ask the user to log in in the window that opens, then run `videos` again. The login is kept in the separate profile as long as the university session is valid.
- Result per activity: `section`, `name`, `type`, `url`; with `--deep` also `video` (true/false) and `minutes` (real length from the video player, e.g. Opencast). `--deep` only opens player pages (lti, h5p, page, url …), never files.
- **Videos** = entries with `video: true`. H5P activities are usually interactive slides, not videos – only include them if the user wants (then as `tasks`). Don't open files (`resource`).
- Only take videos that belong to the exam material, and say which ones you left out.
- Plan time per video: real length ×1.3 rounded up (pausing, rewinding) – mention that in the summary.
- If your agent can control the user's browser directly, that works too. If neither works: ask the user to save the course page with Ctrl+S and read the HTML file.

### 4. Build topics (the core: everything fits together)
A **topic** bundles what belongs together: script pages + videos + Anki subdeck. The add-on schedules each topic in this order: **read → video → new cards**. So the user watches the video on exactly the day they learn the cards for it.
- Create topics following the course structure (Moodle sections) or the script chapters.
- For each topic, the matching subdeck as a search within the source: `"anki": {"<source-id>": "deck:\"Deck::Subdeck\""}`. Without a matching subdeck: the whole source deck only for exactly one topic, otherwise leave it out (leftover cards come at the end).
- Assign each video to exactly **one** topic. Videos without a topic are scheduled at the end – better assign them yourself.
- Interim dates as `milestones`, topics linked via `"milestone": "<id>"`; dissection-lab dates with `"prep": true`.

### 5. Write the plan file
In a temporary folder (or next to the materials as `<Title>_Study-Plan.json`). Structure (fields as in the add-on):
```json
{
 "id": "anatomy1", "title": "Anatomy exam", "subtitle": "short summary of the content",
 "exam": "2026-11-05", "examTime": "09:00", "start": "2026-10-27",
 "minutesPerDay": 240, "offWeekdays": [6], "dayMinutes": {"2026-11-01": 120},
 "milestones": [{"id": "m1", "name": "Credit test 1", "date": "2026-11-02", "time": "", "prep": false}],
 "sources": [
  {"id": "script", "type": "pages", "name": "Script", "file": "/path/script.pdf", "pageOffset": 0, "minPerUnit": 6},
  {"id": "vid", "type": "videos", "name": "Moodle videos", "defaultMin": 20, "minPerUnit": null,
   "videos": [{"id": "v1", "name": "Shoulder joint", "min": 18, "url": "https://moodle.example.edu/mod/..."}]},
  {"id": "joints", "type": "anki", "name": "Joints", "decks": ["Deck::Joints"], "minPerUnit": 1, "maxNew": 120},
  {"id": "table", "type": "anki", "name": "Muscle table (review only)", "decks": ["Deck::Table"], "minPerUnit": 0.4, "reviewOnly": true}
 ],
 "topics": [
  {"id": "k1", "name": "Shoulder", "pages": {"script": [12, 30]}, "videos": {"vid": ["v1"]},
   "anki": {"joints": "deck:\"Deck::Joints::Shoulder\""}, "milestone": "m1"}
 ]
}
```
- `offWeekdays`: 0 = Monday … 6 = Sunday. `dayMinutes`: exceptions for single days.
- `minPerUnit`: minutes per page / per new card; for videos the video's `min` counts.
- IDs only letters, digits, `-`, `_`. For an existing plan, keep **its** source and topic IDs.

### 6. Dry run, fix, save
1. `study_plan.py build <file> --dry-run` and check the output:
   - **Notes** at the end (e.g. "too full", "reviews alone take more time"): adjust study time, `maxNew` or scope with the user.
   - Are videos on the same day as the cards of their topic? Are the links there?
2. Show the user briefly: number of days, hours per day, which videos on which day (the first days in detail, the rest summarised).
3. If it fits → `study_plan.py build <file>` (saves, creates a backup).
4. Tell the user: reopen the Study Plan window in Anki (if it is open, close it first, otherwise editing there overwrites the new state). Videos open there with "open ↗"; Anki items are ticked off automatically, pages and videos by hand.

### 7. Later
- **Extend** (new videos, new deck, different date): take the plan JSON from the add-on, change it, `build` again.
- **Fell behind** (missed days): `study_plan.py replan <id>` spreads everything open from today on.

## What to avoid
- Opening or changing the real Anki collection – only through the script (copy).
- Downloading videos or saving Moodle content.
- Typing a password or filling in login pages.
- Saving without `--dry-run`.
- Creating a new plan when one already exists for the same exam.
