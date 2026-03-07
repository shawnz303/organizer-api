#!/usr/bin/env bash
# Export current todos to TODOS.md and push to git
set -e

API_URL="${API_URL:-http://localhost:8000}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/TODOS.md"

# Verify server is up
if ! curl -sf "$API_URL/health" > /dev/null; then
  echo "Error: server not reachable at $API_URL" >&2
  exit 1
fi

python3 - <<PYEOF
import json, sys
from datetime import datetime
from urllib.request import urlopen

data = json.loads(urlopen("$API_URL/api/v1/todos?limit=500").read())
todos = data.get("data", [])

pending = [t for t in todos if t["status"] == "pending"]
in_prog = [t for t in todos if t["status"] == "in_progress"]
done    = [t for t in todos if t["status"] == "done"]

def fmt_due(t):
    if t.get("due_date"):
        try:
            d = datetime.fromisoformat(t["due_date"].replace("Z", ""))
            return d.strftime("%Y-%m-%d")
        except Exception:
            return t["due_date"][:10]
    return ""

def todo_line(t, checked=False):
    box = "[x]" if checked else "[ ]"
    due = f" — due {fmt_due(t)}" if fmt_due(t) else ""
    cat = f" \`{t['category']}\`" if t.get("category") else ""
    tags = f" {' '.join('#'+g for g in t['tags'])}" if t.get("tags") else ""
    return f"- {box} **#{t['id']}** {t['title']}{due} [{t['priority']}]{cat}{tags}"

lines = [
    "# Todo List",
    f"_Last exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_",
    f"_{len(pending)} pending · {len(in_prog)} in progress · {len(done)} done_",
    "",
]

if pending:
    lines.append("## Pending")
    for t in pending:
        lines.append(todo_line(t))
    lines.append("")

if in_prog:
    lines.append("## In Progress")
    for t in in_prog:
        lines.append(todo_line(t))
    lines.append("")

lines.append("## Done")
if done:
    for t in done:
        lines.append(todo_line(t, checked=True))
else:
    lines.append("_Nothing done yet._")

with open("$OUT", "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"Exported {len(todos)} todos to $OUT")
PYEOF

# Commit and push if there are changes
cd "$REPO_ROOT"
if git diff --quiet TODOS.md; then
  echo "No changes to TODOS.md"
  exit 0
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
git add TODOS.md
git commit -m "docs: sync TODOS.md ($(date -u '+%Y-%m-%d %H:%M UTC'))"
git push -u origin "$BRANCH"
echo "Pushed TODOS.md to $BRANCH"
