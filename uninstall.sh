#!/usr/bin/env bash
# Removes the launchers, the venv and the Claude Code plugin. Add --remove-data to also delete ~/.claude-usage-widget.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pkill -f "widget/widget.pyw" 2>/dev/null
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
rm -f "$HOME/.local/share/applications/claude-usage-widget.desktop" "$DESK/claude-usage-widget.desktop" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/claude-usage-widget.desktop"
rm -rf "$REPO/.venv"
if command -v claude >/dev/null; then
  claude plugin uninstall usage-widget@claude-usage-widget
  claude plugin marketplace remove claude-usage-widget
fi
[ "${1:-}" = "--remove-data" ] && rm -rf "$HOME/.claude-usage-widget"
echo "Uninstalled. You can delete this folder now."
