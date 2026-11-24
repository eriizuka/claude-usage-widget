"""Floating Claude usage widget. Drag to move, double-click to switch size, right-click to close."""
import ctypes, datetime as dt, functools, glob, json, os, subprocess, sys, threading, time, tkinter as tk, traceback
from PIL import Image, ImageDraw, ImageFont, ImageTk

PROJECTS = os.path.expanduser("~/.claude/projects")  # transcripts: tokens, cost and context
DATA = os.path.expanduser("~/.claude-usage-widget")  # written by the plugin; also holds config and log
os.makedirs(DATA, exist_ok=True)
LIMITS, CFG, LOG = (os.path.join(DATA, n) for n in ("limits.json", "config.json", "errors.log"))
# US$ per million tokens (input, output, cache read); the first key contained in the model id wins
PRICES = {"opus-5-5": (4, 20, .2), "sonnet-5-5": (2, 10, .1), "haiku-5-5": (.1, .5, .01), "fable-5-2": (8, 40, .2),
          "opus": (5, 25, .5), "sonnet": (2, 10, .2), "haiku": (1, 5, .1), "fable": (10, 50, 1)}
CTX, STALE_MIN, SS = 400_000, 30, 3  # context window, limits stale after 30 min, supersampling
BG, TRACK, WH, DIM, MUT = (14, 15, 20), (44, 46, 56), (255, 255, 255), (201, 205, 214), (138, 143, 153)
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
    return f"resets in {h // 24}d {h % 24}h" if h >= 24 else f"resets in {h}h{int(s % 3600 // 60):02d}"

def age_text(m):
    return "no limits yet" if m is None else "limits just now" if m < 1 else \
        f"limits {m // 60}h{m % 60:02d} old" if m >= 60 else f"limits {m} min old"

@functools.lru_cache(maxsize=32)
def font(px, bold=False):
    try: return ImageFont.truetype("C:/Windows/Fonts/" + ("segoeuib.ttf" if bold else "segoeui.ttf"), int(px))
    except OSError: return ImageFont.load_default()

def color(p): return (0, 230, 118) if p < 60 else (255, 214, 0) if p < 85 else (255, 23, 68)

class Widget:
    def __init__(s):
        s.cfg = {"mode": "big", "x": None, "y": None, **read_json(CFG)}
        r = s.r = tk.Tk(); r.overrideredirect(True); r.iconbitmap(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")); r.attributes("-topmost", True)
        s.k = r.winfo_fpixels("1i") / 96  # screen scale
        s.lbl = tk.Label(r, bd=0, bg="black"); s.lbl.pack()
        for ev, fn in (("<ButtonPress-1>", s.press), ("<B1-Motion>", s.drag), ("<ButtonRelease-1>", s.save),
                       ("<Double-Button-1>", s.toggle), ("<Button-3>", lambda e: r.destroy())): s.lbl.bind(ev, fn)
        r.bind("<<Tick>>", lambda e: s.refresh())
        s.refresh(); r.after(50, s.round_corners)
        threading.Thread(target=s.ticker, daemon=True).start()
        if not s.cfg.get("shortcut"): s.shortcut()
        r.mainloop()

    def shortcut(s):
        """First run: put a 'Claude Usage' shortcut on the desktop (only once, so deleting it sticks)."""
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\Claude Usage.lnk');"
              f"$s.TargetPath='{exe if os.path.exists(exe) else sys.executable}';$s.Arguments='\"{os.path.abspath(__file__)}\"';"
              f"$s.IconLocation='{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')}';$s.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, creationflags=0x08000000, timeout=30)
            s.cfg["shortcut"] = True; s.save()
        except Exception: log(traceback.format_exc())

    def ticker(s):
        """Tk timers can stall after sleep: this thread asks for a refresh every 15 s and
        relaunches the widget if the window goes 2 min without one (time asleep does not count)."""
        prev = time.time()
        while True:
            time.sleep(15); now = time.time()
            if now - prev > 60: s.last = now
            prev = now
            try: s.r.event_generate("<<Tick>>", when="tail")
            except Exception: pass
            if now - s.last > 120:
                log("no refresh for 2 min: relaunching the widget")
                ctypes.windll.kernel32.CloseHandle(MUTEX)
                subprocess.Popen([sys.executable, os.path.abspath(__file__)]); os._exit(0)

    def round_corners(s):  # Windows 11 rounded corners, no light border
        h = ctypes.windll.user32.GetParent(s.r.winfo_id())
        for attr, val in ((33, ctypes.c_int(2)), (34, ctypes.c_uint(0xFFFFFFFE))):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(h, attr, ctypes.byref(val), 4)

    def press(s, e):
        s.dx, s.dy = e.x_root - s.r.winfo_x(), e.y_root - s.r.winfo_y()
        if s.cfg["mode"] == "big" and e.x > s.lbl.winfo_width() - 44 * s.k and e.y < 40 * s.k: s.save(); s.r.destroy()
    def drag(s, e): s.r.geometry(f"+{e.x_root - s.dx}+{e.y_root - s.dy}")
    def save(s, e=None):
        s.r.update_idletasks(); s.cfg.update(x=s.r.winfo_x(), y=s.r.winfo_y())
        try:
            with open(CFG + ".tmp", "w") as f: json.dump(s.cfg, f)
            os.replace(CFG + ".tmp", CFG)
        except OSError: pass
    def toggle(s, e):
        s.cfg["mode"] = "small" if s.cfg["mode"] == "big" else "big"
        s.draw(anchor=(e.x_root, e.y_root)); s.save()

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
        sw, sh, w, h = s.r.winfo_screenwidth(), s.r.winfo_screenheight(), im.width, im.height
        x, y = (anchor[0] - w // 2, anchor[1] - h // 2) if anchor else \
            (sw - w - int(24 * s.k) if s.cfg["x"] is None else s.cfg["x"], int(32 * s.k) if s.cfg["y"] is None else s.cfg["y"])
        x, y = min(max(0, x), sw - w), min(max(0, y), sh - h - int(56 * s.k))  # always on screen
        s.r.geometry(f"{w}x{h}+{x}+{y}"); s.cfg.update(x=x, y=y); s.r.lift()

    def big(s, k, D):
        W, P = int(280 * k), int(18 * k)
        im = Image.new("RGB", (W, int(232 * k)), BG); d = ImageDraw.Draw(im)
        d.text((P, 22 * k), "Claude", font=font(15 * k, True), fill=WH, anchor="lm")
        cx, cy, a = W - P - 6 * k, 22 * k, 5 * k  # close X
        for p, q in (((cx - a, cy - a), (cx + a, cy + a)), ((cx - a, cy + a), (cx + a, cy - a))): d.line([p, q], fill=WH, width=int(2 * k))
        rows = (("5 hours", D["h5"].get("utilization"), until(D["h5"].get("resets_at"))),
                ("Week", D["wk"].get("utilization"), until(D["wk"].get("resets_at"))),
                ("Context", D["cpct"], f"{(D['ctx'] or 0) / 1000:.0f}k / {CTX // 1000}k"))
        for i, (name, pct, extra) in enumerate(rows):
            y, txt = 56 * k + i * 44 * k, "—" if pct is None else f"{pct:.0f}%"
            d.text((P, y), name, font=font(10.5 * k), fill=DIM, anchor="lm")
            d.text((W - P, y), txt, font=font(13 * k, True), fill=WH, anchor="rm")
            d.text((W - P - d.textlength(txt, font=font(13 * k, True)) - 8 * k, y + k), extra, font=font(9.5 * k), fill=DIM, anchor="rm")
            by, bh = y + 17 * k, 7 * k
            d.rounded_rectangle([P, by - bh / 2, W - P, by + bh / 2], radius=bh / 2, fill=TRACK)
            if pct: d.rounded_rectangle([P, by - bh / 2, max(P + (W - 2 * P) * min(pct, 100) / 100, P + bh), by + bh / 2], radius=bh / 2, fill=color(pct))
        y = 56 * k + 3 * 44 * k
        d.text((P, y - 2 * k), f"Today  {D['tok'] / 1e6:.1f}M tokens  ·  ~US$ {D['cost']:.2f}", font=font(10 * k), fill=DIM, anchor="lm")
        d.text((P, y + 15 * k), age_text(D["age"]) + "  ·  double-click: compact", font=font(9 * k), fill=MUT, anchor="lm")
        return im

    def small(s, k, D):
        stale = D["age"] is None or D["age"] >= STALE_MIN
        im = Image.new("RGB", (int(176 * k), int((84 if stale else 68) * k)), BG); d = ImageDraw.Draw(im)
        r, w = 21 * k, int(5 * k)
        for i, (lab, pct, lim) in enumerate((("5h", D["h5"].get("utilization"), 1), ("W", D["wk"].get("utilization"), 1), ("C", D["cpct"], 0))):
            cx, cy, old = 32 * k + i * 56 * k, 34 * k, lim and stale and pct is not None  # stale number: grey ring
            box = [cx - r, cy - r, cx + r, cy + r]
            d.ellipse(box, outline=TRACK, width=w)
            if pct: d.arc(box, -90, -90 + 3.6 * min(pct, 100), fill=(120, 124, 136) if old else color(pct), width=w)
            d.text((cx, cy - 4 * k), "—" if pct is None else f"{pct:.0f}", font=font(12 * k, True), fill=(150, 154, 166) if old else WH, anchor="mm")
            d.text((cx, cy + 9 * k), lab, font=font(8.5 * k), fill=(190, 195, 206), anchor="mm")
        if stale: d.text((im.width / 2, 74 * k), age_text(D["age"]), font=font(9 * k, True), fill=(255, 214, 0), anchor="mm")
        return im

MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "ClaudeUsageWidget")
if ctypes.windll.kernel32.GetLastError() != 183: Widget()  # 183: a widget is already open
