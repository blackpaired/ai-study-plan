#!/usr/bin/env bash
# Builds dist/study-plan.zip for AI apps that let you upload skills as a ZIP file.
# Some apps allow at most 200 characters in the skill description, so the ZIP gets this short one;
# the full SKILL.md description stays in the repo.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
short="Builds a day-by-day study plan up to your exam from your notes, Moodle videos and Anki decks, and writes it into the Smart Study Anki add-on. Use for study plan or exam prep."
[ ${#short} -le 200 ] || { echo "Short description is ${#short} characters (max 200)" >&2; exit 1; }
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp -r "$here/skills/study-plan" "$work/study-plan"
rm -rf "$work/study-plan/__pycache__"

SHORT="$short" python3 -I - "$work/study-plan/SKILL.md" <<'PY'
import os, re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
s, n = re.subn(r"^description: .*$", lambda m: "description: " + os.environ["SHORT"], s, count=1, flags=re.M)
assert n == 1, "no description line found"
open(p, "w", encoding="utf-8").write(s)
PY
mkdir -p "$here/dist"
rm -f "$here/dist/study-plan.zip"
python3 -I -c 'import shutil, sys; shutil.make_archive(sys.argv[1], "zip", sys.argv[2], sys.argv[3])' "$here/dist/study-plan" "$work" "study-plan"
echo "Built: $here/dist/study-plan.zip"
