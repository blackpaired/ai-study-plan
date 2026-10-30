#!/usr/bin/env bash
# Installs the study-plan skill for your terminal AI agent.
# Usage: open a terminal in this folder and run
#   bash install.sh [skills-folder]
# Default: ~/.claude/skills (a skills folder several AI tools read).
# Pass the folder your AI tool loads skills from to install somewhere else.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
skills="${1:-$HOME/.claude/skills}"

mkdir -p "$skills"
rm -rf "$skills/study-plan"
cp -r "$here/skills/study-plan" "$skills/"
chmod +x "$skills/study-plan/to_md.sh" "$skills/study-plan/study_plan.py" "$skills/study-plan/moodle_links.mjs"

echo "Skill installed:  $skills/study-plan/"
echo
echo "Required programs:"
missing=0
check() { if command -v "$1" >/dev/null 2>&1; then echo "  ok       $1"; else echo "  MISSING  $1  ($2)"; missing=1; fi; }
check python3     "Python 3"
check node        "Node.js 22 or newer (for reading Moodle videos)"
check markitdown  "pip install 'markitdown[all]'  or  pipx install 'markitdown[all]'"
check pdftotext   "poppler: sudo pacman -S poppler / sudo apt install poppler-utils / brew install poppler"
if command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1 || command -v google-chrome >/dev/null 2>&1 \
   || command -v google-chrome-stable >/dev/null 2>&1 || [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
  echo "  ok       chromium/chrome"
else
  echo "  MISSING  chromium/chrome  (for the Moodle login window)"; missing=1
fi
if python3 -c "import anki.collection" >/dev/null 2>&1; then
  echo "  ok       anki (Python library)"
else
  echo "  MISSING  anki (Python library)  (ships with Anki 23.10+ on Linux packages, otherwise: pip install anki)"; missing=1
fi
addon=""
for d in "$HOME/.local/share/Anki2/addons21"/* "$HOME/.local/share/Anki2/addons21"/*/plan \
         "$HOME/Library/Application Support/Anki2/addons21"/* "$HOME/Library/Application Support/Anki2/addons21"/*/plan; do
  [ -f "$d/planner.py" ] && [ -f "$d/store.py" ] && addon="$d" && break
done
if [ -n "$addon" ]; then
  echo "  ok       Smart Study add-on  ($addon)"
else
  echo "  MISSING  Smart Study add-on  (https://github.com/TruckDrive/smart-study)"; missing=1
fi

echo
[ "$missing" = 0 ] && echo "All set!" || echo "Please install the missing programs (see above)."
echo "Then (re)start your AI agent and type  /study-plan <folder>"
echo "(or just ask: \"make me a study plan until my exam on <date>, 4 hours a day\")"
