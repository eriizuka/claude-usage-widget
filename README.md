# Claude Usage Widget

A small always-on-top Windows widget that shows how much of your Claude plan you have used.

- **5-hour** and **weekly** plan limits, with time until reset
- **Context** used by your latest Claude Code conversation
- **Today's tokens** and an estimated API-equivalent cost
- Two sizes: a full panel, or three compact rings (5h · W · C). Double-click to switch
- Sharp at any display scale, green → yellow → red as you approach a limit
- Warns when the limit numbers are stale (no Claude Code activity for 30 min)

## Requirements

- Windows 10 or 11
- Python 3.10+ ([python.org](https://www.python.org), with "Add to PATH")
- [Claude Code](https://docs.claude.com/claude-code) (CLI or desktop app) signed in with a Claude plan, for the limits

## Install

```powershell
git clone https://github.com/eriizuka/claude-usage-widget.git
cd claude-usage-widget
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer installs Pillow, adds the `usage-widget` Claude Code plugin, creates a desktop shortcut and a startup
shortcut (skip it with `-NoStartup`), and starts the widget. The limits appear after you start a **new** Claude Code
conversation.

## Usage

| Action | Effect |
| --- | --- |
| Drag | Move the widget (position is remembered) |
| Double-click | Switch between full and compact view |
| Right-click, or the X | Close |

## How it works

- **Limits**: the `usage-widget` plugin hooks Claude Code's session start and every response, and writes the
  5-hour and weekly utilization to `~/.claude-usage-widget/limits.json`. They only update while you use Claude Code.
- **Tokens, cost, context**: the widget reads the local transcripts in `~/.claude/projects`. Cost is an estimate
  at API list prices (see `PRICES` in `widget/widget.pyw`); on a subscription you are not billed this amount.

## Privacy and security

Everything stays on your computer. The plugin has no network access, never reads your conversations and only writes
to `~/.claude-usage-widget`. The widget only reads token counts and model names from the transcripts, and makes no
network requests.

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1 -RemoveData
```

## License

MIT
