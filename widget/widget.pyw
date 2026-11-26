"""Floating Claude usage widget for Windows and Linux. Drag to move, double-click to switch size, right-click to close."""
import ctypes, datetime as dt, functools, glob, json, locale, os, shutil, subprocess, sys, threading, time, tkinter as tk, traceback
from PIL import Image, ImageDraw, ImageFont, ImageTk

WIN, HERE = sys.platform == "win32", os.path.dirname(os.path.abspath(__file__))
PROJECTS = os.path.expanduser("~/.claude/projects")  # transcripts: tokens, cost and context
DATA = os.path.expanduser("~/.claude-usage-widget")  # written by the plugin; also holds config and log
os.makedirs(DATA, exist_ok=True)
LIMITS, CFG, LOG = (os.path.join(DATA, n) for n in ("limits.json", "config.json", "errors.log"))
# US$ per million tokens (input, output, cache read); the first key contained in the model id wins
PRICES = {"opus-5-5": (4, 20, .2), "sonnet-5-5": (2, 10, .1), "haiku-5-5": (.1, .5, .01), "fable-5-2": (8, 40, .2),
          "opus": (5, 25, .5), "sonnet": (2, 10, .2), "haiku": (1, 5, .1), "fable": (10, 50, 1)}
SNAP_L, SNAP_R, SNAP_Y, SNAP_M = 51, 27, 204, 2  # snap buttons: centres, in px from the right edge / from the top
CTX, STALE_MIN, SS = 400_000, 30, 3  # context window, limits stale after 30 min, supersampling
BG, TRACK, WH, DIM, MUT = (14, 15, 20), (44, 46, 56), (255, 255, 255), (201, 205, 214), (138, 143, 153)
# UI text in the system display language (English when it is not one of these)
STRINGS = {
    "en": ("5 hours", "Week", "Context", "Today", "resets in", "no limits yet", "limits just now", "limits {} old", "double-click: compact", "W"),
    "pt": ("5 horas", "Semana", "Contexto", "Hoje", "zera em", "limites sem dados", "limites agora", "limites de {} atrás", "2 cliques: compacto", "S"),
    "es": ("5 horas", "Semana", "Contexto", "Hoy", "reinicia en", "sin datos de límites", "límites ahora", "límites de hace {}", "doble clic: compacto", "S")}
try: LANG = (locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "en") if WIN else
              next((v for k in ("LC_ALL", "LC_MESSAGES", "LANG") if (v := os.environ.get(k))), "en"))[:2].lower()
except Exception: LANG = "en"
H5, WEEK, CONTEXT, TODAY, RESETS, NO_LIMITS, LIMITS_NOW, LIMITS_AGE, DBL, W = STRINGS.get(LANG, STRINGS["en"])
try: ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels: no blur at 125%
except Exception: pass

def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(f"{time.ctime()}\n{msg}\n")
    except OSError: pass

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

_cache = {}  # path -> (mtime, [(timestamp, model, usage)])
def entries(path):
    m = os.path.getmtime(path)
    if _cache.get(path, (None,))[0] != m:
        rows, seen = [], set()
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"usage"' not in line: continue
                try: j = json.loads(line); msg = j["message"]; u = msg["usage"]
                except Exception: continue
                key = msg.get("id") or j.get("uuid")
                if j.get("type") == "assistant" and key not in seen:
                    seen.add(key); rows.append((j.get("timestamp", ""), msg.get("model", ""), u))
        _cache[path] = (m, rows)
    return _cache[path][1]

def scan():
    """Today's tokens and cost (subagents included) and the context of the latest main conversation."""
    today, tok, cost, latest = dt.date.today(), 0, 0.0, (0, None)
    for p in glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True):
        try:
            m = os.path.getmtime(p)
            if "subagents" not in p.replace("\\", "/").split("/") and m > latest[0]: latest = (m, p)
            rows = entries(p) if dt.date.fromtimestamp(m) >= today else []
        except OSError: continue  # deleted between listing and reading
        for ts, model, u in rows:
            try:
                if dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date() != today: continue
            except ValueError: continue
            g = lambda k: u.get(k, 0)
            w1h = (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0)
            pi, po, pr = next((v for k, v in PRICES.items() if k in model), PRICES["opus-5-5"])
            tok += g("input_tokens") + g("output_tokens") + g("cache_read_input_tokens") + g("cache_creation_input_tokens")
            cost += (g("input_tokens") * pi + g("output_tokens") * po + g("cache_read_input_tokens") * pr
                     + (g("cache_creation_input_tokens") - w1h) * pi * 1.25 + w1h * pi * 2) / 1e6
    try: u = entries(latest[1])[-1][2] if latest[1] else None
    except (OSError, IndexError): u = None
    ctx = u and u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    return tok, cost, ctx

def until(t):
    s = max(0, t - time.time()) if isinstance(t, (int, float)) else None
    if s is None: return ""
    h = int(s // 3600)
    return f"{RESETS} {h // 24}d {h % 24}h" if h >= 24 else f"{RESETS} {h}h{int(s % 3600 // 60):02d}"

def age_text(m):
    return NO_LIMITS if m is None else LIMITS_NOW if m < 1 else \
        LIMITS_AGE.format(f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min")

@functools.lru_cache(maxsize=2)
def font_file(bold):  # Segoe UI on Windows; on Linux whatever sans font fontconfig picks (DejaVu, Noto, ...)
    if WIN: return "C:/Windows/Fonts/" + ("segoeuib.ttf" if bold else "segoeui.ttf")
    try: return subprocess.run(["fc-match", "-f", "%{file}", "sans:bold" if bold else "sans"], capture_output=True, text=True, timeout=5).stdout
    except Exception: return "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"

@functools.lru_cache(maxsize=32)
def font(px, bold=False):
    try: return ImageFont.truetype(font_file(bold), int(px))
    except OSError: return ImageFont.load_default()

def color(p): return (0, 230, 118) if p < 60 else (255, 214, 0) if p < 85 else (255, 23, 68)

class Widget:
    def __init__(s):
        s.cfg = {"mode": "big", "x": None, "y": None, **read_json(CFG)}
        r = s.r = tk.Tk(className="claude-usage-widget"); r.overrideredirect(True); r.attributes("-topmost", True)
        s.icon = ImageTk.PhotoImage(Image.open(os.path.join(HERE, "icon.png"))); r.iconphoto(True, s.icon)
        s.k = r.winfo_fpixels("1i") / 96  # screen scale
        s.lbl = tk.Label(r, bd=0, bg="black"); s.lbl.pack()
        for ev, fn in (("<ButtonPress-1>", s.press), ("<B1-Motion>", s.drag), ("<ButtonRelease-1>", s.save),
                       ("<Double-Button-1>", s.toggle), ("<Button-3>", lambda e: r.destroy())): s.lbl.bind(ev, fn)
        r.bind("<<Tick>>", lambda e: s.refresh())
        s.refresh()
        if WIN: r.after(50, s.round_corners)
        threading.Thread(target=s.ticker, daemon=True).start()
        if not s.cfg.get("shortcut"): s.shortcut()
        r.mainloop()

    def shortcut(s):
        """First run: put a 'Claude Usage' shortcut on the desktop (only once, so deleting it sticks)."""
        if not WIN:  # a .desktop launcher in the app menu and on the desktop
            try:
                entry = (f"[Desktop Entry]\nType=Application\nName=Claude Usage\nComment=Claude plan usage widget\n"
                         f"Exec=\"{sys.executable}\" \"{os.path.abspath(__file__)}\"\nIcon={os.path.join(HERE, 'icon.png')}\nTerminal=false\nCategories=Utility;\n")
                desk = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip() if shutil.which("xdg-user-dir") else ""
                for d in filter(None, (os.path.expanduser("~/.local/share/applications"), desk or os.path.expanduser("~/Desktop"))):
                    if not os.path.isdir(d) and d.endswith("Desktop"): continue
                    os.makedirs(d, exist_ok=True); f = os.path.join(d, "claude-usage-widget.desktop")
                    with open(f, "w") as fh: fh.write(entry)
                    os.chmod(f, 0o755)
                s.cfg["shortcut"] = True; s.save()
            except Exception: log(traceback.format_exc())
            return
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\Claude Usage.lnk');"
              f"$s.TargetPath='{exe if os.path.exists(exe) else sys.executable}';$s.Arguments='\"{os.path.abspath(__file__)}\"';"
              f"$s.IconLocation='{os.path.join(HERE, 'icon.ico')}';$s.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=0x08000000, timeout=30)
            s.cfg["shortcut"] = True; s.save()
        except Exception: log(traceback.format_exc())

    def ticker(s):
        """Tk timers can stall after sleep: this thread asks for a refresh every 15 s and
        relaunches the widget if the window goes 2 min without one (time asleep does not count)."""
        threading.Thread(target=s.watchdog, daemon=True).start()
        while True:
            time.sleep(15)
            # blocks while the Tk thread is stuck, which is why the watchdog runs in a thread of its own
            try: s.r.event_generate("<<Tick>>", when="tail")
            except Exception: pass

    def watchdog(s):
        prev = time.time()
        while True:
            time.sleep(15); now = time.time()
            if now - prev > 60: s.last = now  # the computer was asleep: give it time to catch up
            prev = now
            if now - s.last > 120:
                log("no refresh for 2 min: relaunching the widget")
                release()
                subprocess.Popen([sys.executable, os.path.abspath(__file__)]); os._exit(0)

    def round_corners(s):  # Windows 11 rounded corners, no light border
        h = ctypes.windll.user32.GetParent(s.r.winfo_id())
        for attr, val in ((33, ctypes.c_int(2)), (34, ctypes.c_uint(0xFFFFFFFE))):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(h, attr, ctypes.byref(val), 4)

    def press(s, e):
        s.dx, s.dy = e.x_root - s.r.winfo_x(), e.y_root - s.r.winfo_y()
        if s.cfg["mode"] != "big": return
        if e.x > s.lbl.winfo_width() - 44 * s.k and e.y < 40 * s.k: s.save(); s.r.destroy()
        for side, cx in (("left", SNAP_L), ("right", SNAP_R)):  # snap buttons, bottom right of the panel
            if abs(e.x - s.lbl.winfo_width() + cx * s.k) < 13 * s.k and abs(e.y - SNAP_Y * s.k) < 13 * s.k: s.snap(side)
    def snap(s, side):
        """Stick to the bottom-left or bottom-right corner of this monitor, just above the taskbar."""
        s.cfg["snap"] = side; s.draw(); s.save(); s.dx = None  # draw() places it; both sizes stay in the corner
    def work(s):  # work area (screen minus taskbar/panels) of the monitor the widget is on
        if not WIN:  # X11: _NET_WORKAREA from the window manager, else the whole screen
            try:
                v = subprocess.run(["xprop", "-root", "_NET_WORKAREA"], capture_output=True, text=True, timeout=2).stdout
                x, y, w, h = (int(n) for n in v.split("=")[1].replace(",", " ").split()[:4]); return x, y, x + w, y + h
            except Exception: return 0, 0, s.r.winfo_screenwidth(), s.r.winfo_screenheight()
        class MI(ctypes.Structure): _fields_ = [("cb", ctypes.c_ulong), ("mon", ctypes.c_long * 4), ("work", ctypes.c_long * 4), ("f", ctypes.c_ulong)]
        mi = MI(); mi.cb = ctypes.sizeof(MI)
        h = ctypes.windll.user32.MonitorFromWindow(ctypes.windll.user32.GetParent(s.r.winfo_id()), 2)
        if not ctypes.windll.user32.GetMonitorInfoW(h, ctypes.byref(mi)): return 0, 0, s.r.winfo_screenwidth(), s.r.winfo_screenheight()
        return tuple(mi.work)
    def drag(s, e):
        if s.dx is not None: s.r.geometry(f"+{e.x_root - s.dx}+{e.y_root - s.dy}"); s.cfg["snap"] = None
    def save(s, e=None):
        s.r.update_idletasks(); s.cfg.update(x=s.r.winfo_x(), y=s.r.winfo_y())
        try:
            with open(CFG + ".tmp", "w") as f: json.dump(s.cfg, f)
            os.replace(CFG + ".tmp", CFG)
        except OSError: pass
    def toggle(s, e):
        s.cfg["mode"] = "small" if s.cfg["mode"] == "big" else "big"
        s.draw(anchor=None if s.cfg.get("snap") else (e.x_root, e.y_root)); s.save()

    def refresh(s):
        try:
            tok, cost, ctx = scan(); lm = read_json(LIMITS)
            # a window that already reset is void: hide the old number until a new one arrives
            win = {k: v for k in ("five_hour", "seven_day") if isinstance(v := lm.get(k), dict)
                   and not (isinstance(v.get("resets_at"), (int, float)) and v["resets_at"] < time.time())}
            saved = lm.get("fetchedAt", 0) / 1000
            s.d = dict(tok=tok, cost=cost, ctx=ctx, h5=win.get("five_hour", {}), wk=win.get("seven_day", {}),
                       age=int((time.time() - saved) // 60) if saved else None, cpct=ctx and 100 * ctx / CTX)
            s.draw()
        except Exception: log(traceback.format_exc())  # one failed read does not stop the next ones
        s.last = time.time()

    def draw(s, anchor=None):
        im = (s.big if s.cfg["mode"] == "big" else s.small)(s.k * SS, s.d)
        im = im.resize((im.width // SS, im.height // SS), Image.LANCZOS)
        s.photo = ImageTk.PhotoImage(im); s.lbl.config(image=s.photo)
        (l, t, sw, sh), w, h = s.work(), im.width, im.height
        x, y = (anchor[0] - w // 2, anchor[1] - h // 2) if anchor else \
            (sw - w - int(24 * s.k) if s.cfg["x"] is None else s.cfg["x"], int(32 * s.k) if s.cfg["y"] is None else s.cfg["y"])
        if s.cfg.get("snap") and not anchor: x, y = l + SNAP_M if s.cfg["snap"] == "left" else sw - w - SNAP_M, sh - h - SNAP_M
        x, y = min(max(l, x), sw - w), min(max(t, y), sh - h)  # always on screen, never under the taskbar
        s.r.geometry(f"{w}x{h}+{x}+{y}"); s.cfg.update(x=x, y=y); s.r.lift()

    def big(s, k, D):
        W, P = int(280 * k), int(18 * k)
        im = Image.new("RGB", (W, int(232 * k)), BG); d = ImageDraw.Draw(im)
        d.text((P, 22 * k), "Claude", font=font(15 * k, True), fill=WH, anchor="lm")
        cx, cy, a = W - P - 6 * k, 22 * k, 5 * k  # close X
        for p, q in (((cx - a, cy - a), (cx + a, cy + a)), ((cx - a, cy + a), (cx + a, cy - a))): d.line([p, q], fill=WH, width=int(2 * k))
        rows = ((H5, D["h5"].get("utilization"), until(D["h5"].get("resets_at"))),
                (WEEK, D["wk"].get("utilization"), until(D["wk"].get("resets_at"))),
                (CONTEXT, D["cpct"], f"{(D['ctx'] or 0) / 1000:.0f}k / {CTX // 1000}k"))
        for i, (name, pct, extra) in enumerate(rows):
            y, txt = 56 * k + i * 44 * k, "—" if pct is None else f"{pct:.0f}%"
            d.text((P, y), name, font=font(10.5 * k), fill=DIM, anchor="lm")
            d.text((W - P, y), txt, font=font(13 * k, True), fill=WH, anchor="rm")
            d.text((W - P - d.textlength(txt, font=font(13 * k, True)) - 8 * k, y + k), extra, font=font(9.5 * k), fill=DIM, anchor="rm")
            by, bh = y + 17 * k, 7 * k
            d.rounded_rectangle([P, by - bh / 2, W - P, by + bh / 2], radius=bh / 2, fill=TRACK)
            if pct: d.rounded_rectangle([P, by - bh / 2, max(P + (W - 2 * P) * min(pct, 100) / 100, P + bh), by + bh / 2], radius=bh / 2, fill=color(pct))
        y = 56 * k + 3 * 44 * k
        d.text((P, y - 2 * k), f"{TODAY}  {D['tok'] / 1e6:.1f}M tokens  ·  ~US$ {D['cost']:.2f}", font=font(10 * k), fill=DIM, anchor="lm")
        d.text((P, y + 15 * k), age_text(D["age"]) + "  ·  " + DBL, font=font(9 * k), fill=MUT, anchor="lm")
        for side, cx in (("left", SNAP_L), ("right", SNAP_R)):  # monitor icon with the widget in that corner
            x0, y0 = W - cx * k - 9 * k, SNAP_Y * k - 7 * k
            d.rounded_rectangle([x0, y0, x0 + 18 * k, y0 + 14 * k], radius=2.5 * k, outline=DIM, width=int(1.4 * k))
            d.line([x0 + 2 * k, y0 + 11 * k, x0 + 16 * k, y0 + 11 * k], fill=MUT, width=int(1.2 * k))  # taskbar
            bx = x0 + 3 * k if side == "left" else x0 + 10 * k
            d.rounded_rectangle([bx, y0 + 4.5 * k, bx + 5 * k, y0 + 9 * k], radius=1 * k, fill=WH)
        return im

    def small(s, k, D):
        stale = D["age"] is None or D["age"] >= STALE_MIN
        im = Image.new("RGB", (int(176 * k), int((84 if stale else 68) * k)), BG); d = ImageDraw.Draw(im)
        r, w = 21 * k, int(5 * k)
        for i, (lab, pct, lim) in enumerate((("5h", D["h5"].get("utilization"), 1), (W, D["wk"].get("utilization"), 1), ("C", D["cpct"], 0))):
            cx, cy, old = 32 * k + i * 56 * k, 34 * k, lim and stale and pct is not None  # stale number: grey ring
            box = [cx - r, cy - r, cx + r, cy + r]
            d.ellipse(box, outline=TRACK, width=w)
            if pct: d.arc(box, -90, -90 + 3.6 * min(pct, 100), fill=(120, 124, 136) if old else color(pct), width=w)
            d.text((cx, cy - 4 * k), "—" if pct is None else f"{pct:.0f}", font=font(12 * k, True), fill=(150, 154, 166) if old else WH, anchor="mm")
            d.text((cx, cy + 9 * k), lab, font=font(8.5 * k), fill=(190, 195, 206), anchor="mm")
        if stale: d.text((im.width / 2, 74 * k), age_text(D["age"]), font=font(9 * k, True), fill=(255, 214, 0), anchor="mm")
        return im

def single_instance():
    """True if no other widget is open. Windows: a named mutex; Linux: a lock file (retried briefly so a relaunch
    can wait for the old process to exit)."""
    global LOCK
    if WIN:
        LOCK = ctypes.windll.kernel32.CreateMutexW(None, False, "ClaudeUsageWidget")
        return ctypes.windll.kernel32.GetLastError() != 183  # 183: already exists
    import fcntl
    LOCK = open(os.path.join(DATA, ".lock"), "w")
    for _ in range(20):
        try: fcntl.flock(LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB); return True
        except OSError: time.sleep(0.25)
    return False

def release(): ctypes.windll.kernel32.CloseHandle(LOCK) if WIN else LOCK.close()

if single_instance(): Widget()
