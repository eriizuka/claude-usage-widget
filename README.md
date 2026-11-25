<p align="center"><img src="docs/icon.png" width="112" alt="Claude Usage Widget logo"></p>

<h1 align="center">Claude Usage Widget</h1>

**Never hit your Claude limit by surprise again.**

Claude Usage Widget keeps your plan usage in the corner of your screen, so you see where you stand before you
start a big task, not halfway through it. No dashboards to open, no commands to type: one glance and you know.

### Why you'll like it

- 🎯 **Plan your work around your limits.** See your 5-hour and weekly usage and exactly when each one resets.
- 🧠 **Know when to start fresh.** Watch your conversation's context fill up before it slows Claude down.
- 💰 **See what your day is worth.** Today's tokens and their API-equivalent cost, updated as you work.
- 👀 **Readable at a glance.** Green, yellow, red. Shrink it to three tiny rings or expand it for detail with a double-click.
- 🪶 **Lightweight and out of the way.** Always on top, drag it anywhere, crisp on any display, starts with your computer.
- 🔒 **100% local and private.** No account, no network calls, nothing leaves your computer.
- 🌍 **Speaks your language.** Follows your system language: English, Portuguese and Spanish.
- 🐧 **Windows and Linux.** The same widget on both, with a one-command installer for each.
- ⚡ **Installs in one command.** Clone, run the installer, done.

## Requirements

- **Windows** 10 or 11 with Python 3.10+ ([python.org](https://www.python.org), with "Add to PATH"), or
- **Linux** with Python 3.10+ and Tk (`sudo apt install python3-tk python3-venv` on Debian/Ubuntu,
  `python3-tkinter` on Fedora, `tk` on Arch). An X11 session, or XWayland on Wayland, is needed for the floating window
- [Claude Code](https://docs.claude.com/claude-code) (CLI or desktop app) signed in with a Claude plan, for the limits

## Install

**Windows**

```powershell
git clone https://github.com/eriizuka/claude-usage-widget.git
cd claude-usage-widget
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer installs Pillow, adds the `usage-widget` Claude Code plugin, creates a desktop shortcut and a startup
shortcut (skip it with `-NoStartup`), and starts the widget. The limits appear after you start a **new** Claude Code
conversation.

**Linux**

```bash
git clone https://github.com/eriizuka/claude-usage-widget.git
cd claude-usage-widget
./install.sh
```

The installer creates a private Python environment with Pillow in `.venv`, adds the plugin, puts a **Claude Usage**
launcher in your app menu, on your desktop and in autostart (skip autostart with `--no-startup`), and starts the widget.
Install `xprop` (`x11-utils`) so the corner buttons know where your panel is.

## Usage

| Action | Effect |
| --- | --- |
| Drag | Move the widget (position is remembered) |
| Double-click | Switch between full and compact view |
| Corner buttons (bottom right) | Stick the widget to the bottom-left or bottom-right corner, just above the taskbar or panel |
| Right-click, or the X | Close |

The first time the widget runs it also adds a **Claude Usage** shortcut to your desktop (and, on Linux, to your app menu), even if you start it
without the installer (delete it and it won't come back).

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
powershell -ExecutionPolicy Bypass -File uninstall.ps1 -RemoveData   # Windows
```

```bash
./uninstall.sh --remove-data   # Linux
```

## License

MIT
