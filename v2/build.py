#!/usr/bin/env python3
"""GLASS STAGE v2 — one token source, two grounds, every surface.

    python3 v2/build.py             pull the live EPOQ III spine, write every surface, run the check
    python3 v2/build.py --check     the check only (exit 1 on any off-canon colour)
    python3 v2/build.py --diff-stock   what this build sets over stock Ghostty

The source of truth is the live weblink, never a copy:
    https://www.intelligencematters.se/epoq/system.css
Every colour written here is a canon ink, or a canon alpha flattened onto the ground it
sits on. The check refuses anything else, and it refuses --signal-live on paper, in the
canon's own words: "reads on --glass-stage, never on paper".
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import struct
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "out"
WEB = "https://www.intelligencematters.se/epoq/"
HOME = pathlib.Path.home()
FONT = HOME / "Library" / "Fonts" / "RedHatMono[wght].ttf"
GHOSTTY = pathlib.Path("/Applications/Ghostty.app/Contents/MacOS/ghostty")  # stock defaults: the receipt's baseline

INKS = ("ink", "ink-60", "ink-50", "ink-40", "ink-20", "ink-12", "ink-03",
        "paper", "paper-90", "paper-82", "paper-70", "paper-62",
        "line-structural", "line-box", "line-quiet", "grey-51", "graphite",
        "dusk", "hum", "novel", "glass-stage", "signal-go", "signal-attn", "signal-live")

SHORT = {"glass-stage": "stage", "signal-go": "go", "signal-attn": "attn", "signal-live": "live",
         "line-quiet": "quiet", "line-box": "box", "graphite": "graph", "grey-51": "g51",
         "paper-62": "p62", "paper-70": "p70", "paper-82": "p82", "paper-90": "p90",
         "ink-60": "i60", "ink-50": "i50", "ink-40": "i40"}
NBSP = "\u00a0"

# ── the two grounds ──────────────────────────────────────────────────────────
# Each ground is a register the canon already drew (live styles.css), not an invention.
#   stage  .cli-stage--repl   background --glass-stage · colour --paper ·
#          .cli-prompt-glyph --signal-go · #cli .cli-stage--repl .cli-cursor --signal-live
#   paper  .term              --t-bg paper · --t-ink ink · --t-ink70 ink-60 · --t-ink40 ink-40 ·
#          --t-bar line-quiet · .term-cmd .pr + .term .cli-cursor --signal-go
# Shared: the mark is .cli-receipt-mark (background --hum, colour --ink).
# The violet ramp inverts between grounds: the light violets carry the dark, the dark
# violets carry the paper. --signal-go is "go · light", --signal-attn is "attn · dark".
GROUNDS = {
    "stage": {"ground": "glass-stage", "ink": "paper", "field": "paper-62", "ghost": "grey-51",
              "deep": "graphite", "bar": "graphite", "rule": "grey-51",
              "door": "signal-go", "cursor": "signal-live", "mark": "hum", "mark_ink": "ink",
              "flag": "signal-go", "locator": "hum", "seen": "dusk", "enters": "signal-live",
              "bar_flag": "paper"},
    "paper": {"ground": "paper", "ink": "ink", "field": "ink-60", "ghost": "ink-40",
              "deep": "ink", "bar": "line-quiet", "rule": "line-box",
              "door": "signal-go", "cursor": "signal-go", "mark": "hum", "mark_ink": "ink",
              "flag": "signal-attn", "locator": "dusk", "seen": "signal-go", "enters": "novel",
              "bar_flag": "signal-attn"},
}
# The bar's flag: --graphite carries paper type only (.ctl-pill.ghost) and holds --signal-go at 2.6:1,
# so on the stage the flag on the bar steps up to full paper — LITERAL's own promotion to full ink.

ROLE_NOTE = [
    ("ground", "the surface"),
    ("ink", "what you type · what it stresses"),
    ("field", "what the machine answers"),
    ("ghost", "meta · untracked · asides"),
    ("deep", "slot 0 · deep surfaces"),
    ("bar", "status · menus (the term bar)"),
    ("door", "the prompt"),
    ("cursor", "the cursor"),
    ("mark", "selection · highlight, ink type on it"),
    ("flag", "errors · the no-red flag"),
    ("bar_flag", "the flag on the bar · full ink where the bar can't carry the violet"),
    ("locator", "hunks · paths (SIGNAL only)"),
    ("seen", "slot 5 (SIGNAL only)"),
    ("enters", "additions · success (SIGNAL only)"),
]

# ── the two readings ─────────────────────────────────────────────────────────
# LITERAL — E13 taken at its word: text is ink; colour only where function is needed —
#           the door, the mark, the flag. A program's colour is promoted to full ink.
# SIGNAL  — colour as information: every slot a canon ink.
VARIANTS = {
    "literal": {"label": "LITERAL", "fg": "field", "bold": "ink",
                "slots": ["deep", "flag", "ink", "ink", "ink", "ink", "ink", "field",
                          "ghost", "flag", "ink", "ink", "ink", "ink", "ink", "ink"]},
    "signal": {"label": "SIGNAL", "fg": "ink", "bold": None,
               "slots": ["deep", "flag", "enters", "ink", "locator", "seen", "field", "field",
                         "ghost", "flag", "enters", "ink", "locator", "door", "field", "ink"]},
}
NAMES = {("stage", "literal"): "glass-stage", ("paper", "literal"): "glass-paper",
         ("stage", "signal"): "glass-stage-signal", ("paper", "signal"): "glass-paper-signal"}

# ── the Hermes skin: key → (LITERAL role, SIGNAL role) ──────────────────────
SKIN_KEYS = {
    "background": ("ground", "ground"), "ui_text": ("ink", "ink"),
    "banner_border": ("rule", "rule"), "banner_title": ("ink", "ink"),
    "banner_accent": ("ink", "locator"), "banner_dim": ("field", "field"),
    "banner_text": ("field", "ink"),
    "ui_accent": ("mark", "mark"), "ui_primary": ("mark", "mark"),
    "ui_label": ("field", "locator"), "ui_ok": ("ink", "enters"),
    "ui_warn": ("ink", "locator"), "ui_error": ("flag", "flag"),
    "ui_border": ("rule", "rule"), "ui_tool": ("field", "field"), "ui_thinking": ("field", "field"),
    "prompt": ("ink", "ink"), "shell_dollar": ("door", "door"),
    "input_rule": ("rule", "rule"), "response_border": ("rule", "rule"),
    "session_label": ("field", "field"), "session_border": ("ghost", "ghost"),
    "status_bar_bg": ("bar", "bar"), "status_bar_text": ("field", "field"),
    "status_bar_strong": ("ink", "ink"), "status_bar_dim": ("field", "field"),  # the ghost folds into the field on the bar
    "status_bar_good": ("ink", "enters"), "status_bar_warn": ("ink", "locator"),
    "status_bar_bad": ("bar_flag", "bar_flag"), "status_bar_critical": ("bar_flag", "bar_flag"),
    "voice_status_bg": ("bar", "bar"), "selection_bg": ("mark", "mark"),
    "completion_menu_bg": ("bar", "bar"), "completion_menu_current_bg": ("mark", "mark"),
    "completion_menu_meta_bg": ("bar", "bar"), "completion_menu_meta_current_bg": ("mark", "mark"),
    "diff_added": ("ink", "enters"), "diff_removed": ("flag", "flag"),
    "diff_added_word": ("mark", "enters"), "diff_removed_word": ("flag", "flag"),
    "syntax_keyword": ("ink", "locator"), "syntax_string": ("field", "enters"),
    "syntax_number": ("ink", "seen"), "syntax_comment": ("ghost", "ghost"),
}


# ── the spine ────────────────────────────────────────────────────────────────
def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "glass-stage-v2-build"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class Canon:
    def __init__(self, spine: str):
        self.raw = {m[1]: m[2].strip() for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;]+);", spine)}
        missing = [n for n in INKS if n not in self.raw]
        if missing:
            sys.exit(f"the live spine is missing inks: {missing}")

    def rgba(self, name, seen=()):
        v = self.raw[name]
        m = re.fullmatch(r"var\(\s*--([a-z0-9-]+)\s*(?:,[^)]*)?\)", v)
        if m:
            if m[1] == name or m[1] in seen:
                raise ValueError(f"--{name} cycles")
            return self.rgba(m[1], seen + (name,))
        if v.startswith("#"):
            h = v[1:]
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
        m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", v)
        if m:
            return int(m[1]), int(m[2]), int(m[3]), float(m[4]) if m[4] else 1.0
        raise ValueError(f"--{name} is not a colour: {v}")

    def on(self, name: str, ground: str) -> str:
        r, g, b, a = self.rgba(name)
        R, G, B, _ = self.rgba(ground)
        mix = lambda c, C: round(a * c + (1 - a) * C)  # noqa: E731
        return "#%02X%02X%02X" % (mix(r, R), mix(g, G), mix(b, B))

    def allowed(self, ground: str) -> set:
        return {self.on(n, ground) for n in INKS}


def lum(hx: str) -> float:
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def font_metrics(path: pathlib.Path = FONT) -> dict:
    d = path.read_bytes()
    t = {}
    for i in range(struct.unpack(">H", d[4:6])[0]):
        tag, _, off, _ln = struct.unpack(">4sLLL", d[12 + 16 * i: 28 + 16 * i])
        t[tag.decode("latin-1")] = off
    upm = struct.unpack(">H", d[t["head"] + 18: t["head"] + 20])[0]
    asc, desc, gap = struct.unpack(">hhh", d[t["hhea"] + 4: t["hhea"] + 10])
    adv = struct.unpack(">H", d[t["hmtx"]: t["hmtx"] + 2])[0]
    ul_pos, ul_th = struct.unpack(">hh", d[t["post"] + 8: t["post"] + 12])
    st_th, st_pos = struct.unpack(">hh", d[t["OS/2"] + 26: t["OS/2"] + 30])
    f = lambda v: v / upm  # noqa: E731
    return {"upm": upm, "asc": f(asc), "desc": f(-desc), "gap": f(gap), "adv": f(adv),
            "ul_pos": f(ul_pos), "ul_th": f(ul_th), "st_pos": f(st_pos), "st_th": f(st_th)}


# ── themes + the check ───────────────────────────────────────────────────────
def theme(canon: Canon, gname: str, vname: str, ground: dict | None = None) -> dict:
    g, v = ground or GROUNDS[gname], VARIANTS[vname]
    h = lambda role: canon.on(g[role], g["ground"])  # noqa: E731
    return {"name": NAMES[(gname, vname)], "ground": gname, "variant": vname,
            "background": h("ground"), "foreground": h(v["fg"]), "fg_role": v["fg"],
            "cursor": h("cursor"), "cursor_text": h("ground"),
            "selection_bg": h("mark"), "selection_fg": h("mark_ink"),
            "bold": h(v["bold"]) if v["bold"] else None,
            "slots": [h(r) for r in v["slots"]], "slot_roles": list(v["slots"]),
            "tokens": dict(g), "hex": {r: h(r) for r in g}}


def check(canon: Canon, gname: str, vname: str, ground: dict | None = None) -> list:
    g, v = ground or GROUNDS[gname], VARIANTS[vname]
    t = theme(canon, gname, vname, g)
    used = {g[r] for r in v["slots"]} | {g[r] for r in ("ground", "cursor", "mark", "mark_ink", v["fg"])}
    if v["bold"]:
        used.add(g[v["bold"]])
    problems = []
    if g["ground"] == "paper" and "signal-live" in used:
        problems.append("--signal-live on paper · reads on --glass-stage, never on paper")
    ok = canon.allowed(g["ground"])
    every = [t["background"], t["foreground"], t["cursor"], t["cursor_text"],
             t["selection_bg"], t["selection_fg"], *t["slots"]] + ([t["bold"]] if t["bold"] else [])
    problems += [f"{hx} is no canon ink on --{g['ground']}" for hx in every if hx not in ok]
    return problems


def run_checks(canon: Canon, lock: dict):
    rows, failed = [], False
    rows.append((f"  spine  {len(INKS)} inks · intelligencematters.se/epoq · sha256 "
                 f"{lock['system.css']['sha256'][:12]}", "out"))
    for (gn, vn), name in NAMES.items():
        p = check(canon, gn, vn)
        failed |= bool(p)
        rows.append((f"  {'✓' if not p else '✗'} {name:<19} 16 slots · "
                     + ("every hex a canon ink" if not p else p[0]), "ok" if not p else "err"))
    probe = dict(GROUNDS["paper"], enters="signal-live")
    refused = any("never on paper" in x for x in check(canon, "paper", "signal", probe))
    failed |= not refused
    rows.append(("  ✗ refused  --signal-live on paper · reads on --glass-stage, never on paper"
                 if refused else "  ! self-test failed: live on paper was NOT refused", "err"))
    return rows, failed


# ── Ghostty ──────────────────────────────────────────────────────────────────
def ghostty_theme(t: dict, lock: dict) -> str:
    tok, v = t["tokens"], VARIANTS[t["variant"]]
    L = [f"# {t['name']} — GLASS STAGE v2 · "
         f"{'the stage' if t['ground'] == 'stage' else 'the paper terminal'} · {v['label']}",
         f"# generated by v2/build.py from {WEB}system.css",
         f"# sha256 {lock['system.css']['sha256'][:12]} · {lock['fetched']} · do not hand-edit, re-run the build",
         "", f"# --{tok['ground']}", f"background = {t['background']}",
         f"# --{tok[t['fg_role']]} — the field", f"foreground = {t['foreground']}",
         f"# --{tok['cursor']} — the door", f"cursor-color = {t['cursor']}", f"cursor-text = {t['cursor_text']}",
         f"# the mark (.cli-receipt-mark): --{tok['mark']} ground, --{tok['mark_ink']} type",
         f"selection-background = {t['selection_bg']}", f"selection-foreground = {t['selection_fg']}"]
    if t["bold"]:
        L += ["# stress is promoted to full ink, set in the tism (font-style-bold = Italic)",
              f"bold-color = {t['bold']}"]
    L.append("# slots — " + " · ".join(f"{i} {r}/{SHORT.get(tok[r], tok[r])}"
                                       for i, r in enumerate(t["slot_roles"])))
    L += [f"palette = {i}={hx}" for i, hx in enumerate(t["slots"])]
    return "\n".join(L) + "\n"


def ghostty_config(m: dict, lock: dict) -> str:
    natural = m["asc"] + m["desc"] + m["gap"]
    cell_h = round((1.5 / natural - 1) * 100)
    ul = round((0.5 / (14 * m["ul_th"]) - 1) * 100)
    st = round((0.5 / (14 * m["st_th"]) - 1) * 100)
    bar = round(14 * m["adv"] / 2)
    return f"""# GLASS STAGE v2 — Ghostty · generated by v2/build.py
# {WEB}system.css · sha256 {lock['system.css']['sha256'][:12]} · {lock['fetched']}
# One object, two grounds: the stage in the dark, the paper terminal in the light.
# Ghostty follows the macOS appearance; the two theme files carry every colour.
theme = light:glass-paper,dark:glass-stage
window-theme = auto

# the type — --font-mono at --fz-mono-cli 14 / --lh-mono-cli 1.5
font-family = "Red Hat Mono"
font-size = 14
# Red Hat Mono leads at {natural:.3f} on its own (hhea {round(m['asc'] * m['upm'])} + {round(m['desc'] * m['upm'])} / {m['upm']}): 1.5 / {natural:.3f} = +{cell_h}%
adjust-cell-height = {cell_h}%
font-thicken = false
# E1 — bold is not a voice here. The tism is (E12): SGR bold sets in Red Hat Mono Italic.
font-style-bold = Italic
font-style-bold-italic = Italic
# --hairline is the only stroke: underline + strike thinned to 0.5 at 14 ({14 * m['ul_th']:.2f} / {14 * m['st_th']:.2f} in the font)
adjust-underline-thickness = {ul}%
adjust-strikethrough-thickness = {st}%

# the door — the canon cursor is ▌, half a cell: a bar at half the {14 * m['adv']:.1f} advance
cursor-style = bar
adjust-cursor-thickness = {bar}
cursor-style-blink = true

# the frame — .term-stream pads var(--s-3). The stage is the ground and stays opaque:
# glass is for agency surfaces only (the main-view law, 2026-07-17).
window-padding-x = 24
window-padding-y = 24
window-padding-balance = true
window-padding-color = background
background-opacity = 1
macos-titlebar-style = transparent
macos-option-as-alt = true
bold-is-bright = false
# an unfocused split sinks to --glass-alpha
unfocused-split-opacity = 0.6
minimum-contrast = 1
mouse-hide-while-typing = true
"""


def kv(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*([a-z0-9-]+)\s*=\s*(.*?)\s*$", line)
        if m and not line.lstrip().startswith("#") and m[1] not in out:
            out[m[1]] = m[2]
    return out


def stock_defaults() -> str:
    """Ghostty's own defaults: the baseline every receipt diffs against. v1 is never read."""
    if not GHOSTTY.exists():
        return ""
    try:
        return subprocess.run([str(GHOSTTY), "+show-config", "--default"],
                              capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001 — no Ghostty here: the receipt is left out
        return ""


def diff_stock(v2_config: str) -> list:
    a, b = kv(stock_defaults()), kv(v2_config)
    if not a:
        return []
    rows = [("--- ghostty +show-config --default", "meta"), ("+++ v2/out/ghostty/config", "meta")]
    for k in ("theme", "window-theme", "font-size", "adjust-cell-height", "font-style-bold",
              "cursor-style", "background-opacity", "unfocused-split-opacity"):
        if k not in b or a.get(k) == b[k]:
            continue
        if a.get(k):
            rows.append((f"-{k} = {a[k]}", "del"))
        rows.append((f"+{k} = {b[k]}", "ins"))
    return rows


def shell_prompt(canon: Canon) -> str:
    go = canon.on("signal-go", "paper")
    return f"""# GLASS STAGE v2 — the paper terminal's prompt, after .term-cmd
# .pr in --signal-go (the door); what you type in full ink; the machine answers at the field.
# source from ~/.zshrc for Ghostty shells. generated by v2/build.py
setopt PROMPT_SUBST
PROMPT='%F{{{go}}}op@hub%f:%~$ '
zle_highlight=(default:fg=15)
"""


GIT = {
    "literal": ("# GLASS STAGE v2 · git · LITERAL — .hub-diff: del struck · ins hairline-underlined · all ink\n"
                "[color \"diff\"]\n\tmeta = 8\n\tfrag = 15 italic\n\tfunc = 8\n\tcommit = 15\n"
                "\told = 15 strike\n\tnew = 15 ul\n\twhitespace = reverse 9\n"
                "[color \"status\"]\n\theader = 8\n\tbranch = 15 italic\n\tadded = 15 ul\n"
                "\tchanged = 15\n\tuntracked = 8\n\tdeleted = 15 strike\n"
                "[color \"decorate\"]\n\tbranch = 15 italic\n\tremoteBranch = 15\n\tHEAD = 9\n\ttag = 15\n"),
    "signal": ("# GLASS STAGE v2 · git · SIGNAL — colour as information, every slot a canon ink\n"
               "[color \"diff\"]\n\tmeta = 8\n\tfrag = 12\n\tfunc = 5\n\tcommit = 12\n"
               "\told = 9\n\tnew = 10\n\twhitespace = reverse 9\n"
               "[color \"status\"]\n\theader = 8\n\tbranch = 13\n\tadded = 10\n"
               "\tchanged = 12\n\tuntracked = 8\n\tdeleted = 9\n"
               "[color \"decorate\"]\n\tbranch = 13\n\tremoteBranch = 12\n\tHEAD = 9\n\ttag = 5\n"),
}


# ── the Hermes skin ──────────────────────────────────────────────────────────
def one_ink(art: str, hum: str) -> str:
    """The mark is printed in one ink that holds on both grounds — --hum, the hero."""
    return re.sub(r"#[0-9A-Fa-f]{6}", hum, art.replace("[bold ", "["))


def skin_colors(canon: Canon, gname: str, vname: str) -> dict:
    g, i = GROUNDS[gname], (0 if vname == "literal" else 1)
    return {k: canon.on(g[roles[i]], g["ground"]) for k, roles in SKIN_KEYS.items()}


def hermes_skin(canon: Canon, vname: str, lock: dict) -> str:
    name = "glass-stage" if vname == "literal" else "glass-stage-signal"
    stage = skin_colors(canon, "stage", vname)

    L = [f"# {name} — GLASS STAGE v2 · Hermes skin · {VARIANTS[vname]['label']}",
         f"# generated by v2/build.py from {WEB}system.css · sha256 {lock['system.css']['sha256'][:12]}",
         "# colors = the stage inks · dark_colors = the stage ground · light_colors = the paper terminal, inks + ground.",
         "# No background in colors: the Ink TUI reads the terminal's polarity, so it turns when Ghostty turns.",
         "# The classic CLI (display.interface: cli) reads light_colors once the paired-palette patch lands.",
         f"name: {name}",
         'description: "THE GLASS STAGE v2 — one object, two grounds · EPOQ III canon"', "", "colors:"]
    L += [f'  {k}: "{v}"' for k, v in stage.items() if k != "background"]
    # The grounds ride in the paired blocks. A skin that authors `background` in `colors` owns its
    # polarity (ui-tui theme.ts skinIsLight) and paints the stage over a paper terminal; without
    # one, the TUI reads the host (OSC-11) and overlays light_colors on paper, dark_colors on the stage.
    L += ["", "dark_colors:", f'  background: "{stage["background"]}"']
    L += ["", "light_colors:"]
    L += [f'  {k}: "{v}"' for k, v in skin_colors(canon, "paper", vname).items()]
    L += ["", "spinner:", "  waiting_faces:", '    - "[·]"', '    - "[∙]"', '    - "[•]"',
          "  thinking_faces:", '    - "[·]"', '    - "[∙]"', '    - "[•]"',
          "  thinking_verbs:", '    - "building"', '    - "cutting"', '    - "setting the stage"',
          '    - "driving it live"', "", "branding:", '  agent_name: "JACOB / OPERATOR"',
          '  welcome: "THE GLASS STAGE · LIVE"', '  goodbye: "STAGE CLOSED"',
          '  response_label: " OPERATOR "', '  prompt_symbol: "▮"',
          '  help_header: "THE CONTROL SURFACE"', "", 'tool_prefix: "│"', "",
          "# banner art: the gynoid, an abstract piece made for this skin. Pending.",
          "# Until it lands, Hermes prints its stock logo and caduceus. Nothing is carried from v1."]
    return "\n".join(L) + "\n"


# ── specimens (SVG — terminal art, drawn on the cell grid) ──────────────────
def svg_term(rows, ground_hex, *, cols, label, m, tracked=False, fz=14, frame=None):
    cw = fz * (m["adv"] + (0.3 if tracked else 0.0))
    lh, pad = fz * 1.5, 24
    W, H = pad * 2 + cols * cw, pad * 2 + len(rows) * lh
    base = (lh - fz * (m["asc"] + m["desc"])) / 2 + fz * m["asc"]
    s = [f'<svg class="ws-term" viewBox="0 0 {W:.1f} {H:.1f}" role="img" aria-label="{html.escape(label)}" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="Red Hat Mono, ui-monospace, monospace" '
         f'font-size="{fz}" xml:space="preserve">',
         f'<rect width="{W:.1f}" height="{H:.1f}" fill="{ground_hex}"/>']
    if frame:  # the window edge, drawn as the hairline — the only stroke
        s.append(f'<rect x="0.25" y="0.25" width="{W - 0.5:.1f}" height="{H - 0.5:.1f}" fill="none" '
                 f'stroke="{frame}" stroke-width="0.5"/>')
    for r, (segs, rowbg) in enumerate(rows):
        y = pad + r * lh
        if rowbg:
            s.append(f'<rect x="0" y="{y:.2f}" width="{W:.1f}" height="{lh:.2f}" fill="{rowbg}"/>')
        col = 0
        for text, st in segs:
            x = pad + col * cw
            if st.get("cursor"):
                s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cw / 2:.2f}" height="{lh:.2f}" fill="{st["fill"]}"/>')
                col += 1
                continue
            n = len(text)
            if not n:
                continue
            w = n * cw
            if st.get("bg"):
                s.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{lh:.2f}" fill="{st["bg"]}"/>')
            if text.strip():
                a = f'x="{x:.2f}" y="{y + base:.2f}" fill="{st["fill"]}" textLength="{w:.2f}" lengthAdjust="spacing"'
                if st.get("it"):
                    a += ' font-style="italic"'
                s.append(f"<text {a}>{html.escape(text).replace(' ', NBSP)}</text>")
            if st.get("st"):
                yy = y + base - fz * m["st_pos"]
                s.append(f'<rect x="{x:.2f}" y="{yy - 0.25:.2f}" width="{w:.2f}" height="0.5" fill="{st["fill"]}"/>')
            if st.get("ul"):
                yy = y + base - fz * m["ul_pos"]
                s.append(f'<rect x="{x:.2f}" y="{yy - 0.25:.2f}" width="{w:.2f}" height="0.5" fill="{st["fill"]}"/>')
            col += n
    s.append("</svg>")
    return "".join(s)


def svg_slots(t: dict) -> str:
    cell, gap, fz = 44, 4, 8
    W, H = 8 * cell + 7 * gap, 2 * cell + gap
    s = [f'<svg class="ws-term" viewBox="0 0 {W} {H}" role="img" aria-label="{t["name"]} — the sixteen slots" '
         f'xmlns="http://www.w3.org/2000/svg" font-family="Red Hat Mono, ui-monospace, monospace" font-size="{fz}">']
    for i, (hx, role) in enumerate(zip(t["slots"], t["slot_roles"])):
        x, y = (i % 8) * (cell + gap), (i // 8) * (cell + gap)
        ink = "#000000" if contrast(hx, "#000000") >= contrast(hx, "#FFFFFF") else "#FFFFFF"
        tok = t["tokens"][role]
        s.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{hx}"/>')
        s.append(f'<rect x="{x + 0.25}" y="{y + 0.25}" width="{cell - 0.5}" height="{cell - 0.5}" fill="none" '
                 f'stroke="{t["hex"]["rule"]}" stroke-width="0.5"/>')
        s.append(f'<text x="{x + 5}" y="{y + 12}" fill="{ink}">{i}</text>')
        s.append(f'<text x="{x + 5}" y="{y + cell - 6}" fill="{ink}">{html.escape(SHORT.get(tok, tok))}</text>')
    s.append("</svg>")
    return "".join(s)


def term_style(kind: str, t: dict) -> dict:
    """What a terminal run looks like under a theme — the theme's own colours, nothing else."""
    hx, lit = t["hex"], t["variant"] == "literal"
    fg = t["foreground"]
    table = {
        "door": {"fill": hx["door"]}, "cmd": {"fill": hx["ink"]}, "out": {"fill": fg},
        "meta": {"fill": hx["ghost"]}, "muse": {"fill": hx["mark"]},
        "em": {"fill": t["bold"] or fg, "it": 1},
        "mod": {"fill": hx["ink"] if lit else hx["locator"]},
        "del": {"fill": hx["ink"], "st": 1} if lit else {"fill": hx["flag"]},
        "ins": {"fill": hx["ink"], "ul": 1} if lit else {"fill": hx["enters"]},
        "frag": {"fill": hx["ink"], "it": 1} if lit else {"fill": hx["locator"]},
        "ok": {"fill": fg} if lit else {"fill": hx["enters"]},
        "err": {"fill": hx["flag"]},
        "mark": {"fill": hx["mark_ink"], "bg": hx["mark"]},
        "cursor": {"fill": hx["cursor"], "cursor": 1},
    }
    return table[kind]


def ghostty_rows(t, status_lines, diff_rows, report_rows):
    P = lambda path: [("op@hub", "door"), (f":{path}$ ", "cmd")]  # noqa: E731
    bench = "~/Hermes-Worktrees/glass-stage-v2"
    raw = [[("H H G   C O R T E X", "muse")], [("op@hub › ready", "meta")], [],
           P(bench) + [("git status -sb", "cmd")]]
    for line in status_lines:
        if line.startswith("##"):
            raw.append([(line, "em")])
        elif line.startswith("??"):
            raw.append([("??", "meta"), (line[2:], "out")])
        else:
            raw.append([(line[:2], "mod"), (line[2:], "out")])
    raw += [[], P(bench) + [("python3 v2/build.py --diff-stock", "cmd")]]
    raw += [[(text, kind)] for text, kind in diff_rows]
    raw += [[(" window-theme = ", "out"), ("auto", "mark")], [],
            P(bench) + [("python3 v2/build.py --check", "cmd")]]
    raw += [[(text, kind)] for text, kind in report_rows]
    raw += [P(bench) + [("", "cursor")]]
    return [([(text, term_style(kind, t)) for text, kind in segs], None) for segs in raw]


def rich(line: str, fallback: dict) -> list:
    """Rich console markup → runs: [style] opens, [/] closes, a #hex in the style is the ink."""
    segs, stack, pos = [], [fallback], 0
    for m in re.finditer(r"\[(/?)([^\]]*)\]", line):
        if m.start() > pos:
            segs.append((line[pos:m.start()], stack[-1]))
        if m[1]:
            if len(stack) > 1:
                stack.pop()
        else:
            st = dict(stack[-1])
            hx = re.search(r"#[0-9A-Fa-f]{6}", m[2])
            if hx:
                st["fill"] = hx[0].upper()
            stack.append(st)
        pos = m.end()
    if pos < len(line):
        segs.append((line[pos:], stack[-1]))
    return segs


def tui_rows(skin: dict, hum: str, logo: str, hero: str, facts: dict):
    S = lambda k: {"fill": skin[k]}  # noqa: E731
    width = lambda segs: sum(len(t) for t, _ in segs)  # noqa: E731
    muse = {"fill": hum}
    rows = [(rich(line, muse), None) for line in logo.split("\n")] if logo else []
    rows.append(([], None))
    inner = 136
    title = f" {facts['version']} "[: inner - 4]
    rows.append(([("╭─", S("banner_border")), (title, {"fill": skin["banner_title"], "it": 1}),
                  ("─" * (inner - len(title) - 1) + "╮", S("banner_border"))], None))
    left = [[]] + ([rich(line, muse) for line in hero.split("\n")] if hero else []) + [[]]
    left += [[(facts["model"], S("banner_accent"))], [(facts["cwd"], S("banner_dim"))],
             [("session " + facts["session"], S("banner_dim"))]]
    accent = {"fill": skin["banner_accent"], "it": 1}
    right = [[("Available Tools", accent)],
             [("file: read_file, write_file, patch, search_files", S("banner_text"))],
             [("terminal: terminal, execute_code, process_manage", S("banner_text"))],
             [("web: web_search, web_extract, browser_exec", S("banner_text"))],
             [("agents: delegate_task, clarify, todo_list", S("banner_text"))], [],
             [("Available Skills", accent)],
             [("creative: epoq3-page-production, web-design-workflows", S("banner_text"))],
             [("research: grounded-citations, rss-feeds", S("banner_text"))],
             [("productivity: authored-agency-operations", S("banner_text"))], [],
             [(f"{facts['skills']} skills · /help for commands", S("banner_dim"))]]
    lw = max(width(x) for x in left) + 3
    for i in range(max(len(left), len(right))):
        ls = left[i] if i < len(left) else []
        rs = right[i] if i < len(right) else []
        rows.append(([("│  ", S("banner_border"))] + ls + [(" " * (lw - width(ls)), S("banner_dim"))] + rs
                     + [(" " * max(inner - 2 - lw - width(rs), 0), S("banner_dim")), ("│", S("banner_border"))], None))
    rows.append(([("╰" + "─" * inner + "╯", S("banner_border"))], None))
    rows += [([("THE GLASS STAGE · LIVE", S("banner_dim"))], None), ([], None),
             ([("▮ ", {"fill": skin["shell_dollar"]}), ("lets workshop the designs, totally epoq as canon", S("prompt"))], None),
             ([("│ ", S("banner_dim")), ("read_file  ", S("ui_tool")), ("design/epoq3/USAGE.md · 265–354", S("session_label"))], None),
             ([("│ ", S("banner_dim")), ("terminal   ", S("ui_tool")), ("ghostty +show-config --default --docs", S("session_label"))], None),
             ([("─ OPERATOR ", {"fill": skin["banner_title"], "it": 1}), ("─" * 127, S("response_border"))], None),
             ([("The canon already drew both modes: the paper terminal and the stage.", S("ui_text"))], None),
             ([("[•] ", S("ui_thinking")), ("setting the stage", S("ui_thinking"))], None), ([], None)]
    bar = skin["status_bar_bg"]
    rows.append(([(" ▮ ", {"fill": skin["shell_dollar"]}), (facts["model"], S("status_bar_strong")),
                  ("  │  ctx 38%  │  ", S("status_bar_text")), ("glass-stage", S("status_bar_strong")),
                  ("  │  ", S("status_bar_text")), ("visit open", S("status_bar_good")),
                  ("  │  ", S("status_bar_text")), ("1 error", S("status_bar_bad"))], bar))
    return rows


# ── the workshop page ────────────────────────────────────────────────────────
CSS = """
/* GLASS STAGE v2 · workshop — page-local parts only; every value reads the live spine. */
.ws-term { display: block; width: 100%; height: auto; }
.ws-switch { display: flex; gap: var(--s-1); flex-wrap: wrap; align-items: center; }
body[data-variant="literal"] .ws-v-signal, body[data-variant="signal"] .ws-v-literal { display: none; }
.ws-stack { display: flex; flex-direction: column; gap: var(--s-2); }
.ws-tok { white-space: nowrap; }
.ws-sw { vertical-align: middle; }
.ws-door .ws-send { margin-left: auto; }
.ws-desk .station { margin-top: 0; }
.ws-desk .hub-shell { min-height: var(--stage); }
/* A desktop mock keeps its desktop width; below it the tile scrolls, as the canon's own rails do. */
.ws-desk { overflow-x: auto; }
.ws-desk .hub-shell { min-width: var(--col-2); }
.ws-desk .hub-rail { position: static; height: auto; align-self: stretch; }
.ws-desk .hub-body { display: flex; flex-direction: column; gap: var(--s-2); }
.ws-glass { padding: var(--s-2) var(--s-3); display: flex; flex-direction: column; gap: var(--s-1); }
.ws-door { margin-top: calc(-1 * var(--s-5)); margin-inline: var(--s-3); flex-direction: row; align-items: baseline; font-family: var(--font-mono); font-size: var(--fz-mono-cli); line-height: var(--lh-mono-cli); } /* canon-lint:allow: E9 — the door is the CLI register, sized as .term-body at --fz-mono-cli */
.ws-glass, .ws-glass .serif-body-1, .ws-glass .mono, .ws-glass .ctl-pill { color: var(--paper); } /* canon-lint:allow: E13 — paper type on black glass, an ink-filled surface (the rule's own exception) */
.ws-glass .ws-ph { color: var(--paper-62); } /* canon-lint:allow: E13 — paper tint on black glass, an ink-filled surface */
.ws-desk[data-ground="paper"] .ws-door .cli-cursor { color: var(--signal-go); } /* canon-lint:allow: E13 — the door, as .term .cli-cursor */
.ws-desk[data-ground="stage"] .ws-door .cli-cursor { color: var(--signal-live); } /* canon-lint:allow: E13 — the door, as #cli .cli-stage--repl .cli-cursor */
/* PROPOSAL — the workhorse tier on the stage. The canon's 200/300 rows are paper-native; on the
   stage they take E13's own exception (paper on an ink-filled surface), hairlines sink to --grey-51,
   and the receipt is the canon .term with its own knobs re-pointed — one object, the ground swapped. */
.ws-desk[data-ground="stage"] { background: var(--glass-stage); }
.ws-desk[data-ground="stage"] .hub-shell *:not(.cli-prompt-glyph):not(.cli-cursor):not(.ws-ph):not(.pr) { color: var(--paper); } /* canon-lint:allow: E13 — paper type on the ink-filled stage, the rule's own exception */
.ws-desk[data-ground="stage"] .hub-rail { border-right-color: var(--grey-51); }
.ws-desk[data-ground="stage"] .hub-rail-foot { border-top-color: var(--grey-51); }
.ws-desk[data-ground="stage"] .hub-cmd-btn { border-color: var(--paper-62); }
.ws-desk[data-ground="stage"] .hub-view.active { border-left-color: var(--paper); }
.ws-desk[data-ground="stage"] .hub-topbar { background: var(--glass-stage); border-bottom-color: var(--grey-51); }
.ws-desk[data-ground="stage"] .hub-activity { border-bottom-color: var(--grey-51); }
.ws-desk[data-ground="stage"] .hub-note { border-left-color: var(--paper); }
.ws-desk[data-ground="stage"] .station { border-color: var(--grey-51); }
.ws-desk[data-ground="stage"] .term { --t-bg: var(--glass-stage); --t-bar: var(--graphite); --t-ink: var(--paper); --t-ink70: var(--paper-62); --t-ink40: var(--grey-51); --t-line: var(--grey-51); }
"""

LAW = [
    ("A terminal reads on paper too — the register is about being a terminal, not the stage under it.",
     "epoq · 005_cli · the session", "light is the paper terminal (.term), dark is the stage REPL (.cli-stage--repl)"),
    ("--signal-live · special occasions only, where function is needed; reads on --glass-stage, never on paper.",
     "system.css", "green exists in the dark only; the build refuses it on paper"),
    ("All text is --ink; colour is border/background instrument. Paper type only on an ink-filled surface.",
     "canon-lint E13", "LITERAL: colour only for the door, the mark and the flag; a program's colour becomes full ink"),
    ("Bold is the explainer voice; emphasis is the tism.", "canon-lint E1 · E12",
     "SGR bold sets in Red Hat Mono Italic (font-style-bold = Italic)"),
    ("del struck · ins hairline underline · all ink.", ".hub-diff", "diffs carry no colour on either ground"),
    ("The CLI register is scoped; main views ride the workhorses; glass on agency surfaces only — lens, gates, the door.",
     "USAGE.md · main-view law, 2026-07-17", "Ghostty and the TUI wear the CLI register; Desktop wears the HUB shell"),
    ("--fz-mono-cli 14 · --lh-mono-cli 1.5", "system.css", "Ghostty font-size 14 · adjust-cell-height 13% on Red Hat Mono"),
    ("The mark: --hum ground, --ink type.", ".cli-receipt-mark", "selection, on both grounds, the same object"),
]

RULINGS = [
    ("Terminal reading", "E13: text is ink; colour is instrument", "LITERAL — door · mark · flag; SIGNAL stays a switch away"),
    ("The field", ".term-out at --ink-60, .term-cmd at --ink", "machine at the field, you at full ink"),
    ("The ghost on the stage", "E13: only paper tints on an ink-filled surface",
     "--grey-51, the perceptual mirror of --ink-40 (2.6); E13-strict would fold it into --paper-62"),
    ("The bar", "--graphite carries paper type (.ctl-pill.ghost)",
     "the bar is its own surface: --signal-go on graphite is 2.6:1, so the bar's flag steps up to full paper (paper: --signal-attn); the ghost folds into the field (1.9 / 2.3 otherwise)"),
    ("Hermes' own floors", "Hermes audits built-ins: strong ≥ 3.9, hairline ≥ 2.8 against #101014",
     "canon holds in your skin (--signal-go 3.3 · --grey-51 2.4); upstream, glass-stage rides the PR as its demo, not as a built-in"),
    ("Stress", "E1 · E12", "bold sets as the tism, Red Hat Mono Italic"),
    ("Tracking", ".term-body at --track-code 0.3em", "untracked for the daily terminal; tracked is +50% cell width"),
    ("The banner art", "one ink must hold on both grounds",
     "the gynoid: an abstract piece made for this skin from Jacob's references; nothing from v1, nothing stock. Pending the references"),
    ("Glass on the Ghostty window", "glass on agency surfaces only", "opaque: the window is the ground"),
    ("Desktop register", "main-view law", "HUB shell + serif voice; CLI only at the door; glass on gates + door"),
    ("The door's glass", "colour arrives only where something has to happen",
     "the gate emits, the door refracts: on the stage the composer keeps no fringe and no bleed, rim 0.4, frost 10"),
    ("Desktop on the stage", "workhorse rows are paper-native", "PROPOSAL: E13's exception — paper on ink. Needs an epoq3 ruling"),
    ("Name on the Nous submission", "—", "JACOB / OPERATOR stays local; the submitted skin carries THE GLASS STAGE"),
]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def swatch(hx: str) -> str:
    return (f'<svg class="ws-sw" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
            f'<rect width="12" height="12" fill="{hx}"/><rect x="0.25" y="0.25" width="11.5" height="11.5" '
            f'fill="none" stroke="#515151" stroke-width="0.5"/></svg>')


def kv_receipt(t: dict) -> str:
    """What ships for this theme — the theme file's own values, as canon key/value rows."""
    tok, hx = t["tokens"], t["hex"]
    rows = [("ground", [t["background"]], f"--{tok['ground']}"),
            ("field", [t["foreground"]], f"--{tok[t['fg_role']]}"),
            ("door", [hx["door"]], f"--{tok['door']} · the prompt"),
            ("cursor", [t["cursor"]], f"--{tok['cursor']}"),
            ("mark", [t["selection_bg"], t["selection_fg"]], f"--{tok['mark']} / --{tok['mark_ink']}"),
            ("flag", [hx["flag"]], f"--{tok['flag']}")]
    if t["bold"]:
        rows.append(("stress", [t["bold"]], f"--{tok[VARIANTS[t['variant']]['bold']]} · italic"))
    return "".join(f'<div class="hub-kv"><span class="hub-kv-key">{esc(k)}</span><span class="hub-kv-val">'
                   f'{"".join(swatch(h) for h in hs)} <span class="mono m6">{esc(" / ".join(hs))} · {esc(tk)}</span></span></div>'
                   for k, hs, tk in rows)


def grounds_table(canon: Canon) -> str:
    rows = []
    for role, note in ROLE_NOTE:
        cells = []
        for gname in ("stage", "paper"):
            g = GROUNDS[gname]
            tok = g[role]
            hx = canon.on(tok, g["ground"])
            against = {"mark": "mark_ink", "bar_flag": "bar"}.get(role, "ground")
            on = canon.on(g[against], g["ground"])
            ratio = "" if role == "ground" else f" · {contrast(hx, on):.1f}"
            cells.append(f"<td>{swatch(hx)} <span class=\"mono m6\">--{esc(tok)} · {hx}{ratio}</span></td>")
        rows.append(f"<tr><td class=\"mono m6\">{esc(role)}</td><td>{esc(note)}</td>{''.join(cells)}</tr>")
    return ("<table><thead><tr><th>role</th><th>what it is</th><th>the stage</th><th>the paper terminal</th></tr>"
            "</thead><tbody>" + "".join(rows) + "</tbody></table>")


def simple_table(head, rows) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


# The glass, per ground. EPOQ prints square (--radius-print 0): the pane matches the gate's own
# hairline box. The fill is --ink-60 — black glass (glassci law 3): the record bends behind it,
# the type on it holds. The stage glass EMITS: --hum bleeds, the fringe disperses. Paper glass
# OCCLUDES (S2·B): the record behind inverts, and the bleed turns contact shadow by changing the
# ink, not the rule — no fringe, more frost.
GLASS_PANE = {
    "stage": {"radius": 0, "depth": 12, "strength": 16, "dispersion": 3, "blur": 6,
              "bleed": 18, "rim": 0.85, "fill": "var(--ink-60)"},
    "paper": {"radius": 0, "depth": 12, "strength": 16, "dispersion": 0, "blur": 10,
              "bleed": 10, "emission": "var(--ink)", "invert": 1, "rim": 0.85, "fill": "var(--ink-60)"},
}


def desk(ground: str, rows: list) -> str:
    tag = "the stage" if ground == "stage" else "the paper"
    # One attribute set per ground: an attribute repeated on a tag keeps its FIRST value, so the
    # paper override once appended after the shared set never applied (it bled --hum at 18px).
    def glass_attrs(**over) -> str:
        opts = {**GLASS_PANE[ground], **over}
        return "data-glassci " + " ".join(f'data-glassci-{k}="{v}"' for k, v in opts.items())

    glass = glass_attrs()
    # The door rests on the receipt. The rim is an SVG stroke centred on the pane's edge, so half
    # of it lands on the record above; at the gate's 0.85 it read as a smear over the last line.
    # The gate emits; the door only refracts: on the stage its fringe split the record into a
    # violet smear and its --hum bleed hazed the line above, so the door keeps neither — and frosts
    # harder, so the record behind it never doubles the placeholder.
    door = glass_attrs(rim=0.4, bleed=0, dispersion=0, blur=10) if ground == "stage" else glass_attrs(rim=0.4)
    acts = [("19:41", "read_file", "design/epoq3/USAGE.md · 265–354 · the main-view law"),
            ("19:42", "terminal", "ghostty +show-config --default --docs · 1.3.1")]
    after = [("19:43", "terminal", "git clone lepetittruffier/glass-stage · approved once"),
             ("19:44", "write_file", "v2/build.py · one spine, two grounds")]
    row = lambda a, b, c: (f'<div class="hub-activity is-agent"><span class="act-ts">{a}</span>'  # noqa: E731
                           f'<span class="act-who">{esc(b)}</span><span class="act-ev">{esc(c)}</span></div>')
    before_rows = "".join(row(*a) for a in acts)
    after_rows = "".join(row(*a) for a in after)
    changes = [(text[1:], "del" if kind == "del" else "ins") for text, kind in rows if kind in ("del", "ins")][:8]
    receipt = ('<div class="station"><div class="term" aria-label="a receipt — the canon paper terminal">'
               '<div class="term-body mono"><div class="term-stream">'
               '<span class="term-row term-cmd"><span class="pr">op@hub</span>:~/glass-stage-v2$ '
               'python3 v2/build.py --diff-stock</span>'
               + "".join(f'<span class="term-row term-out"><{tag}>{esc(text)}</{tag}></span>' for text, tag in changes)
               + '</div></div></div></div>')
    return f"""
<div class="ws-desk" data-ground="{ground}">
 <div class="hub-shell hub-shell-specimen">
  <aside class="hub-rail">
   <div class="hub-rail-brand"><span class="hub-brand-name mono m6">Hermes</span><span class="hub-brand-tag mono m6">{tag}</span></div>
   <span class="hub-cmd-btn mono m6">⌘K · new</span>
   <div class="hub-nav-group"><span class="hub-nav-group-label mono m6">sessions</span>
    <div class="hub-views">
     <span class="hub-view active">glass stage v2 <span class="hub-view-ct">now</span></span>
     <span class="hub-view">login to cortex <span class="hub-view-ct">18:02</span></span>
     <span class="hub-view">afterhours <span class="hub-view-ct">sun</span></span>
    </div>
   </div>
   <div class="hub-nav-group"><span class="hub-nav-group-label mono m6">driving</span>
    <div class="hub-views"><span class="hub-view">Calleoke</span><span class="hub-view">Nous</span></div>
   </div>
   <div class="hub-rail-spacer"></div>
   <div class="hub-rail-foot"><span class="hub-foot-who mono m6">jacob · opus-5-5</span></div>
  </aside>
  <div class="hub-main">
   <div class="hub-topbar">
    <div><div class="hub-topbar-title">Glass Stage v2</div><div class="hub-topbar-ctx">visit 6bfe6caf · open · local draft</div></div>
    <div class="hub-topbar-right"><span class="pres-chip is-live"><span class="pix-dot live"></span> live</span></div>
   </div>
   <div class="hub-body">
    <p class="hub-note serif-body-1">lets workshop the designs, totally epoq as canon</p>
    <p class="serif-body-1">The canon already drew both modes. Light is the paper terminal; dark is the stage. Colour arrives only where something has to happen.</p>
    {before_rows}
    <div class="hub-approval ws-glass" {glass}>
     <span class="mono m6">gate · terminal</span>
     <p class="serif-body-1">git clone lepetittruffier/glass-stage into ~/Hermes-Worktrees</p>
     <div class="ws-switch"><span class="ctl-pill ghost accent mono m6">allow once</span><span class="ctl-pill ghost mono m6">deny</span></div>
    </div>
    {after_rows}
    {receipt}
    <div class="ws-glass ws-door" {door}>
     <span class="cli-prompt-glyph">▮</span><span class="ws-ph">message the operator</span><span class="cli-cursor">▌</span><span class="ws-ph ws-send mono m6">⏎ send</span>
    </div>
   </div>
  </div>
 </div>
</div>"""


def page(canon, lock, m, themes, report_rows, status_lines, diff_rows, skins, facts) -> str:
    sv = lock["styles.css"]["sha256"][:8]
    hum = canon.on("hum", "paper")
    logo = hero = ""  # banner art: the gynoid, pending. Nothing from v1, nothing stock.

    def terms(gname):
        out = []
        for vname in ("literal", "signal"):
            t = themes[(gname, vname)]
            rows = ghostty_rows(t, status_lines, diff_rows, report_rows)
            svg = svg_term(rows, t["background"], cols=88, m=m, frame=t["hex"]["rule"],
                           label=f"Ghostty, {t['name']} — a session rendered on the cell grid")
            out.append(f'<div class="ws-v-{vname}">{svg}</div>')
        return "".join(out)

    def slots(gname):
        return "".join(f'<div class="ws-v-{v}">{svg_slots(themes[(gname, v)])}</div>' for v in ("literal", "signal"))

    def notes(gname):
        return "".join(f'<div class="ws-v-{v} ws-stack">{kv_receipt(themes[(gname, v)])}{svg_slots(themes[(gname, v)])}</div>'
                       for v in ("literal", "signal"))

    pl = themes[("paper", "literal")]
    tracked = svg_term([
        ([("op@epoq3", term_style("door", pl)), (":~$ why-a-register", term_style("cmd", pl))], None),
        ([("A system that isn't", term_style("out", pl))], None),
        ([("machine-readable can't be", term_style("out", pl))], None),
        ([("operated, only ", term_style("out", pl)), ("described.", term_style("em", pl))], None),
    ], pl["background"], cols=26, m=m, tracked=True, frame=pl["hex"]["rule"],
        label="the canon's own paper terminal, tracked at --track-code")

    def tui(gname):
        out = []
        for vname in ("literal", "signal"):
            skin = skins[(gname, vname)]
            svg = svg_term(tui_rows(skin, hum, logo, hero, facts), skin["background"], cols=140, m=m,
                           frame=skin["banner_border"],
                           label=f"Hermes TUI on the {gname}, {VARIANTS[vname]['label']} — mock layout, exact inks")
            out.append(f'<div class="ws-v-{vname}">{svg}</div>')
        return "".join(out)

    switch = ('<div class="ws-switch"><span class="mono m6">reading</span>'
              '<button type="button" class="ctl-pill on mono m6" data-set-variant="literal" aria-pressed="true">literal</button>'
              '<button type="button" class="ctl-pill mono m6" data-set-variant="signal" aria-pressed="false">signal</button>'
              '<span class="mono m6">literal · colour only for the door, the mark, the flag — signal · colour as information, every ink a token</span></div>')

    def git_rows(vname):
        cur, rows = "", []
        for line in GIT[vname].splitlines():
            sec = re.match(r'\[color "(\w+)"\]', line)
            if sec:
                cur = sec[1]
            kv_ = re.match(r"\t(\w+) = (.+)", line)
            if kv_ and f"{cur}.{kv_[1]}" in ("diff.old", "diff.new", "diff.frag", "status.untracked", "status.branch"):
                rows.append(f'<div class="hub-kv"><span class="hub-kv-key">{cur}.{kv_[1]}</span>'
                            f'<span class="hub-kv-val mono m6">{esc(kv_[2])}</span></div>')
        return "".join(rows)

    git_notes = ('<span class="mono m6 ann">git · the slots it prints through — one config, both grounds</span>'
                 + "".join(f'<div class="ws-v-{v} ws-stack">{git_rows(v)}</div>' for v in ("literal", "signal")))

    readout = [f"sha256 {lock['system.css']['sha256'][:12]}", f"fetched {lock['fetched']}", f"{len(INKS)} inks",
               "4 / 4 themes on canon", "live on paper refused", "local draft · not live"]
    readout_spans = "".join(f"<span>{esc(r)}</span>" for r in readout)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glass Stage v2 — the workshop</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Red+Hat+Mono:ital,wght@0,400;0,700;1,400&family=Scheherazade+New:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{WEB}styles.css?v={sv}">
<link rel="stylesheet" href="{WEB}glassci.css?v={sv}">
<style>{CSS}</style>
</head>
<body data-variant="literal">
<a class="skip-link mono m6" href="#main">skip to content</a>
<div class="stage">
<div class="canvas" id="canvas">
<div class="frame epoq-container">

<header class="epoq-header">
 <div class="masthead"><span class="mono m6 brand"><span class="cursor">_</span> Glass Stage · v2 · the workshop</span></div>
 <div class="nav-block">
  <nav class="index index-main mono m6" aria-label="workshop">
   <a href="#law">000_law</a><a href="#grounds">001_grounds</a><a href="#ghostty">002_ghostty</a>
   <a href="#tui">003_tui</a><a href="#desktop">004_desktop</a><a href="#rulings">005_rulings</a>
  </nav>
 </div>
</header>

<main id="main">

<section id="law" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">000_law</h2>
  <p class="sec-tagline serif-8-caps">One object, two grounds. The skin invents nothing — every surface wears a register the canon already drew.</p>
 </div>
 <div class="gridrow">
  <div class="container-tile u-full"><div class="m-stage">
   {simple_table(("the law", "where it is written", "what it does to the skin"), LAW)}
  </div></div>
 </div>
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">receipt</span>{readout_spans}</div></div></div>
</section>

<section id="grounds" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">001_grounds</h2>
  <p class="sec-tagline serif-8-caps">Fourteen roles, two grounds. The violet ramp inverts: the light violets carry the dark, the dark violets carry the paper.</p>
 </div>
 <div class="gridrow"><div class="container-tile u-full"><div class="m-stage">{grounds_table(canon)}</div></div></div>
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">the grounds</span><span>every hex a canon ink, alphas flattened onto the ground they sit on · contrast against the ground (the mark: ink on hum · the bar's flag: on the bar)</span></div></div></div>
</section>

<section id="ghostty" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">002_ghostty</h2>
  <p class="sec-tagline serif-8-caps">The same session, the same object — the stage in the dark, the paper terminal in the light. Ghostty follows the macOS appearance.</p>
  {switch}
 </div>
 <div class="gridrow">
  <div class="container-tile u-major"><div class="m-stage"><span class="mono m6 ann">Ghostty · glass-stage · Red Hat Mono 14 / 1.5</span>{terms("stage")}</div></div>
  <div class="container-tile u-minor"><div class="m-stage"><div class="med-text ws-stack">
   <span class="mono m6 ann">the stage</span>
   <h3 class="ms-name serif-heading-3">The stage REPL</h3>
   <p class="ms-text serif-body-1">--glass-stage black, paper type. The machine answers at --paper-62; what you type and what it stresses stand at full paper. The cursor is the one live thing — --signal-live, half a cell wide, as the canon draws its cursor. Diffs carry no colour: git strikes and underlines them.</p>
   {notes("stage")}
   {git_notes}
  </div></div></div>
 </div>
 <div class="gridrow">
  <div class="container-tile u-minor"><div class="m-stage"><div class="med-text ws-stack">
   <span class="mono m6 ann">the paper terminal</span>
   <h3 class="ms-name serif-heading-3">The session, on paper</h3>
   <p class="ms-text serif-body-1">The canon's .term, as written: ink on paper, the answer at --ink-60, the prompt and the cursor in --signal-go. No green can reach this ground — the build refuses it.</p>
   {notes("paper")}
   <span class="mono m6 ann">the canon's own .term-body tracks at --track-code · Ghostty adjust-cell-width +50%</span>
   {tracked}
  </div></div></div>
  <div class="container-tile u-major"><div class="m-stage"><span class="mono m6 ann">Ghostty · glass-paper · Red Hat Mono 14 / 1.5</span>{terms("paper")}</div></div>
 </div>
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">ghostty</span><span>v2/out/ghostty · config + glass-stage + glass-paper (+ -signal) · prompt.zsh · git-literal / git-signal</span><span class="open-ruling">reading · tracking · glass</span></div></div></div>
</section>

<section id="tui" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">003_tui</h2>
  <p class="sec-tagline serif-8-caps">Hermes in the terminal. The stage inks in colors, the grounds in the paired blocks — the Ink TUI turns with Ghostty today; the classic CLI turns with the Nous patch.</p>
 </div>
 <div class="gridrow"><div class="container-tile u-full"><div class="m-stage"><span class="mono m6 ann">Hermes TUI · the stage · colors</span>{tui("stage")}</div></div></div>
 <div class="gridrow"><div class="container-tile u-full"><div class="m-stage"><span class="mono m6 ann">Hermes TUI · the paper · light_colors</span>{tui("paper")}</div></div></div>
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">hermes tui</span><span>mock after hermes_cli/banner.py · inks from v2/out/hermes/glass-stage.yaml</span><span>classic CLI on paper · the Nous patch</span><span class="open-ruling">banner art · the gynoid, pending</span></div></div></div>
</section>

<section id="desktop" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">004_desktop</h2>
  <p class="sec-tagline serif-8-caps">Desktop is a main view, so it wears the HUB shell — the record in the workhorse rows, the serif carrying the prose, glass only on the gate and the door.</p>
 </div>
 <div class="gridrow"><div class="container-tile u-full">{desk("paper", diff_rows)}</div></div>
 <div class="gridrow"><div class="container-tile u-full">{desk("stage", diff_rows)}</div></div>
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">hermes desktop</span><span>mock — canon .hub-shell parts from the live styles.css · glass is the live glassci · the stage polarity is a proposal</span><span class="open-ruling">stage polarity · needs the bridge patch</span></div></div></div>
</section>

<section id="rulings" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">005_rulings</h2>
  <p class="sec-tagline serif-8-caps">What the canon leaves open. Each line is yours to rule.</p>
 </div>
 <div class="gridrow"><div class="container-tile u-full"><div class="m-stage">{simple_table(("decision", "the canon says", "proposed"), RULINGS)}</div></div></div>
</section>

</main>

<footer class="canon-footer">
 <div class="f-crumbs mono m6"><span>Glass Stage &gt; v2 &gt; the workshop · a local draft, not live</span><span class="f-index">5 0 &gt;</span></div>
 <div class="f-bar">
  <svg preserveAspectRatio="none" width="100%" height="75" viewBox="0 0 1200 75" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M0 37.5H1200" stroke="#000" stroke-width="75" stroke-dasharray="2 3 1 4 3 2 1 3"/></svg>
  <span class="f-rail mono m6"><a href="#law">000_law</a><a href="#ghostty">002_ghostty</a><a href="#desktop">004_desktop</a><a href="#rulings">005_rulings</a></span>
 </div>
 <a class="f-group mono m6" href="https://github.com/lepetittruffier/glass-stage">lepetittruffier/glass-stage</a>
</footer>

</div>
</div>
</div>
<script src="{WEB}glassci.js?v={sv}" defer></script>
<script>
document.querySelectorAll('[data-set-variant]').forEach(function (b) {{
  b.addEventListener('click', function () {{
    document.body.dataset.variant = b.dataset.setVariant;
    document.querySelectorAll('[data-set-variant]').forEach(function (x) {{
      x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
    }});
  }});
}});
</script>
</body>
</html>
"""


def classes_in(markup: str) -> set:
    used = set()
    for attr in re.findall(r'class="([^"]+)"', markup):
        used.update(attr.split())
    return used


def class_census(doc: str, styles: str, extra: str, reference: str) -> list:
    """Every class the page wears must be canon: a rule in the live CSS, or markup the
    live reference page itself carries (hooks like .f-index have no rule of their own)."""
    known, ref = styles + extra, classes_in(reference)
    return sorted(c for c in classes_in(doc) if not c.startswith("ws-") and c not in ref
                  and not re.search(r"\." + re.escape(c) + r"(?![a-zA-Z0-9_-])", known))


def facts() -> dict:
    f = {"version": "Hermes Agent", "model": "claude-opus-5-5", "cwd": "~/hhg_cortex_v1", "session": "20261012"}
    try:
        out = subprocess.run(["hermes", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        if out:
            f["version"] = out.splitlines()[0].strip()
    except Exception:  # noqa: BLE001 — the specimen keeps its default label
        pass
    # the model is this session's (claude-opus-5-5); config.yaml's default names another seat
    f["skills"] = sum(1 for _ in (HOME / ".hermes" / "skills").rglob("SKILL.md"))
    return f


def main() -> int:
    args = set(sys.argv[1:])
    spine, styles, glassci = fetch(WEB + "system.css"), fetch(WEB + "styles.css"), fetch(WEB + "glassci.css")
    lock = {"weblink": WEB, "fetched": dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
            "system.css": {"sha256": sha(spine), "bytes": len(spine)},
            "styles.css": {"sha256": sha(styles), "bytes": len(styles)},
            "glassci.css": {"sha256": sha(glassci), "bytes": len(glassci)}}
    canon = Canon(spine)
    lock["inks"] = {n: canon.raw[n] for n in INKS}
    report_rows, failed = run_checks(canon, lock)
    if "--check" in args:
        print("\n".join(r for r, _ in report_rows))
        return 1 if failed else 0

    m = font_metrics()
    cfg = ghostty_config(m, lock)
    diff_rows = diff_stock(cfg)
    if "--diff-stock" in args:
        print("\n".join(r for r, _ in diff_rows))
        return 0

    themes = {(g, v): theme(canon, g, v) for g in GROUNDS for v in VARIANTS}
    for d in ("ghostty/themes", "git", "shell", "hermes", "workshop"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    (OUT / "tokens.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    (OUT / "ghostty" / "config").write_text(cfg)
    for key, t in themes.items():
        (OUT / "ghostty" / "themes" / t["name"]).write_text(ghostty_theme(t, lock))
    for vname, text in GIT.items():
        (OUT / "git" / f"glass-stage-{vname}.gitconfig").write_text(text)
    (OUT / "shell" / "prompt.zsh").write_text(shell_prompt(canon))
    for vname in VARIANTS:
        name = "glass-stage" if vname == "literal" else "glass-stage-signal"
        (OUT / "hermes" / f"{name}.yaml").write_text(hermes_skin(canon, vname, lock))

    status = subprocess.run(["git", "-C", str(REPO), "status", "-sb"], capture_output=True, text=True).stdout
    status_lines = [line for line in status.splitlines() if line.strip()][:4]
    skins = {(g, v): skin_colors(canon, g, v) for g in GROUNDS for v in VARIANTS}
    doc = page(canon, lock, m, themes, report_rows, status_lines, diff_rows, skins, facts())
    # a token never breaks across a line: --paper-62 stays one word in the prose
    doc = re.sub(r'(<p class="ms-text serif-body-1">)(.*?)(</p>)',
                 lambda x: x[1] + re.sub(r"(--[a-z0-9-]+)", r'<span class="ws-tok">\1</span>', x[2]) + x[3], doc)
    (OUT / "workshop" / "index.html").write_text(doc)

    unknown = class_census(doc, styles, glassci, fetch(WEB))
    print("\n".join(r for r, _ in report_rows))
    print(f"  metrics  adv {m['adv']:.3f}em · natural lh {m['asc'] + m['desc'] + m['gap']:.3f} · "
          f"ul {m['ul_pos']:.3f}/{m['ul_th']:.3f} · strike {m['st_pos']:.3f}/{m['st_th']:.3f}")
    print(f"  census   {'every class is canon' if not unknown else 'NOT IN CANON: ' + ', '.join(unknown)}")
    print(f"  wrote    {OUT.relative_to(REPO)}/ · workshop {len(doc) // 1024} KB")
    return 1 if failed or unknown else 0


if __name__ == "__main__":
    sys.exit(main())
