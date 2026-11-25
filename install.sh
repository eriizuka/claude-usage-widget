#!/usr/bin/env bash
# Claude Usage Widget installer (Linux). Run from the repo folder:  ./install.sh [--no-startup]
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIDGET="$REPO/widget/widget.pyw"
VENV="$REPO/.venv"

echo "1/4 Python, Tk and Pillow"
command -v python3 >/dev/null || { echo "python3 not found. Install it with your package manager." >&2; exit 1; }
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "Tkinter is missing. Install it, then run this again:" >&2
  echo "  Debian/Ubuntu: sudo apt install python3-tk python3-venv   Fedora: sudo dnf install python3-tkinter   Arch: sudo pacman -S tk" >&2
  exit 1
fi
# a private virtual environment keeps Pillow away from the system Python (PEP 668)
python3 -m venv --system-site-packages "$VENV" || { echo "Could not create a venv. On Debian/Ubuntu: sudo apt install python3-venv" >&2; exit 1; }
"$VENV/bin/python" -m pip install --quiet --upgrade -r "$REPO/requirements.txt"
PY="$VENV/bin/python"
command -v xprop >/dev/null || echo "    Tip: install xprop (x11-utils) so the corner buttons stay above your panel."

echo "2/4 Claude Code plugin (saves your plan limits)"
if command -v claude >/dev/null; then
  claude plugin marketplace add "$REPO"
  claude plugin install usage-widget@claude-usage-widget
  echo "    Plugin installed: limits appear after your next new Claude Code conversation."
else
  echo "    The claude CLI was not found, so the plugin was not installed. The widget still shows tokens, cost and context."
  echo "    For the 5-hour and weekly limits: npm install -g @anthropic-ai/claude-code, then run this installer again."
fi

echo "3/4 Launchers"
ENTRY="[Desktop Entry]
Type=Application
Name=Claude Usage
Comment=Claude plan usage widget
Exec=\"$PY\" \"$WIDGET\"
Icon=$REPO/widget/icon.png
Terminal=false
Categories=Utility;"
write() { mkdir -p "$1"; printf '%s\n' "$ENTRY" > "$1/claude-usage-widget.desktop"; chmod +x "$1/claude-usage-widget.desktop"; }
write "$HOME/.local/share/applications"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
[ -d "$DESK" ] && write "$DESK" && (gio set "$DESK/claude-usage-widget.desktop" metadata::trusted true 2>/dev/null || true)
[ "${1:-}" = "--no-startup" ] || write "${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
# the widget would otherwise add its own desktop launcher on first run
mkdir -p "$HOME/.claude-usage-widget"
"$PY" - <<'EOF'
import json, os
p = os.path.expanduser("~/.claude-usage-widget/config.json")
try: c = json.load(open(p))
except Exception: c = {}
c["shortcut"] = True; json.dump(c, open(p, "w"))
EOF

echo "4/4 Starting the widget"
setsid "$PY" "$WIDGET" >/dev/null 2>&1 < /dev/null &
echo "Done. Drag to move, double-click to switch size, right-click (or the X) to close."
