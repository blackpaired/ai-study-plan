#!/usr/bin/env python3
"""Connects the skill to the Anki add-on "Smart Study Plan".
Reads Anki only from a COPY of the collection (Anki may stay open) and plans with the
add-on's own planning code, so the plan looks exactly as if you had clicked
"Create plan" in the add-on.

Usage:  python3 -I study_plan.py <command> [...]
  addon                      show the add-on folder and existing plans
  decks [word]               decks with card counts (total / new), to pick the Anki sources
  show <plan-id>             print a plan day by day (with video links)
  build <plan.json>          read a plan file (settings, sources, topics), schedule the days
                             and save it in the add-on. An existing plan with the same ID is
                             backed up first as <id>.json.bak-<time>; finished items are kept.
  replan <plan-id>           spread an existing plan again from today on (e.g. after missed days)

Options: --addon <folder>    add-on folder, if it is not found automatically
         --profile <folder>  Anki profile folder (default: the only one or "User 1")
         --dry-run           only plan and show, save nothing

Exit code 0 = ok, 1 = error in the input, 3 = Anki's Python library or the add-on is missing.
"""
import glob
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types

ANKI_DIRS = [os.path.expanduser(p) for p in ("~/.local/share/Anki2", "~/Library/Application Support/Anki2",
                                             "~/AppData/Roaming/Anki2")]


def fail(text, code=1):
    print("ERROR: " + text, file=sys.stderr)
    sys.exit(code)


def anki_dir():
    return next((d for d in ANKI_DIRS if os.path.isdir(d)), ANKI_DIRS[0])


def addon_folder(choice=None):
    if choice:
        return os.path.expanduser(choice)
    for d in sorted(glob.glob(os.path.join(anki_dir(), "addons21", "*"))):
        if os.path.isfile(os.path.join(d, "planner.py")) and os.path.isfile(os.path.join(d, "store.py")):
            return d
    fail("Add-on 'Smart Study Plan' not found (folder with planner.py in Anki2/addons21/). "
         "Pass it with --addon <folder>.", 3)


def modules(addon):
    """Load planner and ankidata without the add-on's __init__.py (that one needs Anki's GUI)."""
    try:
        import anki.collection  # noqa: F401
    except ImportError:
        fail("Anki's Python library is missing (ships with Anki 23.10+, otherwise: pip install anki).", 3)
    pkg = types.ModuleType("sp_addon")
    pkg.__path__ = [addon]
    sys.modules["sp_addon"] = pkg
    return importlib.import_module("sp_addon.planner"), importlib.import_module("sp_addon.ankidata")


def collection(profile=None):
    """Open a copy of collection.anki2 (+ WAL) – the real collection is never touched."""
    if profile:
        path = os.path.join(os.path.expanduser(profile), "collection.anki2")
    else:
        cands = sorted(glob.glob(os.path.join(anki_dir(), "*", "collection.anki2")))
        path = next((c for c in cands if os.sep + "User 1" + os.sep in c), cands[0] if cands else None)
    if not path or not os.path.isfile(path):
        fail("Anki collection not found. Pass it with --profile <folder>.", 3)
    tmp = tempfile.mkdtemp(prefix="study_plan_")
    for ext in ("", "-wal"):
        if os.path.exists(path + ext):
            shutil.copy2(path + ext, os.path.join(tmp, "collection.anki2" + ext))
    from anki.collection import Collection
    return Collection(os.path.join(tmp, "collection.anki2")), tmp


def plans_folder(addon):
    return os.path.join(addon, "user_files", "plans")


def load(addon, pid):
    path = os.path.join(plans_folder(addon), pid + ".json")
    if not os.path.isfile(path):
        fail(f"Plan '{pid}' not found ({path}).")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def newest(addon, col, pid):
    """Plan from the file or the collection – the newer one counts (it may have come from another device via sync)."""
    path = os.path.join(plans_folder(addon), pid + ".json")
    from_file = None
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            from_file = json.load(f)
    from_col = (col.get_config("lernplan_plans", None) or {}).get(pid)
    stamp = lambda p: -1 if p is None else float(p.get("savedAt") or 0)
    return from_col if stamp(from_col) > stamp(from_file) else from_file


def save(addon, plan):
    plan["savedAt"] = time.time()  # newer than the copy in the collection -> the add-on takes it over
    folder = plans_folder(addon)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, plan["id"] + ".json")
    if os.path.exists(path):
        backup = path + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    print(f"Saved: {path}")
    print("The add-on takes the plan into the collection the next time it opens or syncs (AnkiWeb sync).")


def check(planner, plan):
    """Rough check of the plan file before scheduling."""
    for k in ("id", "title", "exam", "start"):
        if not plan.get(k):
            fail(f"Plan file: '{k}' is missing.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", plan["id"]):
        fail("Plan file: 'id' may only contain letters, digits, - and _.")
    try:
        if planner.s2d(plan["exam"]) < planner.s2d(plan["start"]):
            fail("Plan file: the exam is before the start.")
    except ValueError:
        fail("Plan file: dates as YYYY-MM-DD, please.")
    ids = {s["id"] for s in plan.get("sources", [])}
    for s in plan.get("sources", []):
        if s.get("type") not in ("pages", "videos", "tasks", "anki"):
            fail(f"Source '{s.get('id')}': unknown type '{s.get('type')}'.")
        for v in s.get("videos", []) + s.get("tasks", []):
            if v.get("url") and not str(v["url"]).startswith(("http://", "https://", "file://")):
                fail(f"'{v.get('name')}': link must start with http(s):// or file://.")
    for t in plan.get("topics", []):
        for key in ("pages", "videos", "tasks", "anki"):
            for sid in t.get(key, {}):
                if sid not in ids:
                    fail(f"Topic '{t.get('name')}': source '{sid}' does not exist.")


def complete(plan, old):
    """Fields the add-on expects; finished items are taken over from the old plan."""
    empty = {"examTime": "", "status": "active", "minutesPerDay": 180, "offWeekdays": [], "dayMinutes": {},
             "dayNotes": {}, "order": "auto", "milestones": [], "sources": [], "topics": [], "days": [],
             "done": {}, "autoDone": {}, "notes": []}
    for k, v in empty.items():
        plan.setdefault(k, v)
    if old:
        for k in ("days", "done", "autoDone", "simHistory", "review", "maintenance"):
            if k in old and not plan.get(k):
                plan[k] = old[k]
    return plan


def schedule(planner, ankidata, col, addon, plan):
    """Like generate_all() in the add-on: plans with an earlier exam take their time first."""
    today = ankidata.today(col)
    budget = None
    try:
        with open(os.path.join(addon, "user_files", "profile.json"), encoding="utf-8") as f:
            budget = json.load(f).get("budget")
    except (OSError, ValueError):
        pass
    taken = {}
    for path in sorted(glob.glob(os.path.join(plans_folder(addon), "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                p = json.load(f)
        except (OSError, ValueError):
            continue
        if p.get("id") == plan["id"] or p.get("status") != "active" or not p.get("days"):
            continue
        if (p.get("exam", ""), p["id"]) < (plan["exam"], plan["id"]) and p["exam"] >= today.isoformat():
            for d, m in planner.day_load(p, today).items():
                taken[d] = taken.get(d, 0) + m
    st = ankidata.stats(col, plan)
    return planner.build(plan, st["counts"], today, planner.evaluate(plan, st),
                         forecast=ankidata.forecast(col, plan), taken=taken, budget=budget)


def show(plan):
    srcs = {s["id"]: s for s in plan.get("sources", [])}
    print(f"\n{plan['title']}  –  exam {plan['exam']}  –  {plan.get('minutesPerDay')} min/day")
    for day in plan.get("days", []):
        items = [it for it in day["items"] if not it.get("moved")]
        total = sum(it.get("min", 0) for it in items)
        print(f"\n{day['d']}  ({round(total / 60, 1)} h)")
        for it in items:
            mark = "x" if it["id"] in plan.get("done", {}) or it["id"] in plan.get("autoDone", {}) else " "
            src = srcs.get(it.get("source"), {}).get("name", "")
            line = f"  [{mark}] {it.get('text', '')}"
            if src and it.get("kind") != "reviews":
                line += f"  ({src})"
            if it.get("min"):
                line += f"  {it['min']} min"
            print(line)
            if it.get("url"):
                print(f"        {it['url']}")
    for n in plan.get("notes", []):
        print(f"\nNote: {n}")


def main():
    args = sys.argv[1:]
    opt = {}
    for name in ("--addon", "--profile"):
        if name in args:
            i = args.index(name)
            opt[name] = args[i + 1]
            del args[i:i + 2]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    addon = addon_folder(opt.get("--addon"))

    if cmd == "addon":
        print(f"Add-on: {addon}")
        for path in sorted(glob.glob(os.path.join(plans_folder(addon), "*.json"))):
            with open(path, encoding="utf-8") as f:
                p = json.load(f)
            print(f"  {p['id']:<16} {p['title']}  (exam {p['exam']}, {p.get('status', 'active')})")
        return

    if cmd == "show":
        show(load(addon, args[1]))
        return

    planner, ankidata = modules(addon)
    col, tmp = collection(opt.get("--profile"))
    try:
        if cmd == "decks":
            word = args[1].lower() if len(args) > 1 else ""
            for name in ankidata.deck_names(col):
                if word and word not in name.lower():
                    continue
                q = planner.deck_query(name)
                total = len(col.find_cards(q))
                new = len(col.find_cards(f"{q} is:new -is:suspended"))
                print(f"{total:6} {new:6}  {name}")
            print("(columns: total cards, of which new)")
            return
        if cmd == "build":
            with open(args[1], encoding="utf-8") as f:
                plan = json.load(f)
            check(planner, plan)
            plan = complete(plan, newest(addon, col, plan["id"]))
        elif cmd == "replan":
            plan = newest(addon, col, args[1])
            if not plan:
                fail(f"Plan '{args[1]}' not found.")
        else:
            fail(f"unknown command '{cmd}'.")
        schedule(planner, ankidata, col, addon, plan)
        show(plan)
        if not dry:
            save(addon, plan)
    finally:
        col.close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
