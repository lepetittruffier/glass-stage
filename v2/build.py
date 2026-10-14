#!/usr/bin/env python3
"""GLASS STAGE v2 — one token source, two grounds, every surface.

    python3 v2/build.py             pull the live EPOQ III spine, write every surface, run the check
    python3 v2/build.py --check     the check only (exit 1 on any off-canon colour)
    python3 v2/build.py --diff-v1   the v1 Ghostty keys this build moves

The source of truth is the live weblink, never a copy:
    https://www.intelligencematters.se/epoq/system.css
Every colour written here is a canon ink, or a canon alpha flattened onto the ground it
sits on. The check refuses anything else, and it refuses --signal-live on paper, in the
canon's own words: "reads on --glass-stage, never on paper".
"""
from __future__ import annotations

import datetime as dt
import functools
import hashlib
import html
import json
import os
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
V1_SKIN = HOME / ".hermes" / "skins" / "glass-stage.yaml"
V1_GHOSTTY = REPO / "ghostty" / "config"

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
# SIGNAL  — the v1 reading (shipped 2026-07-11), every slot now a canon ink.
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
    for vname in VARIANTS:
        css = desk_css(canon, vname, lock)
        bad, size = desk_check(canon, css), len(css.encode())
        ok = not bad and size <= 32768
        failed |= not ok
        rows.append((f"  {'✓' if ok else '✗'} desktop·{vname:<12} 2 grounds · {len(DESK_KEYS)} tokens · "
                     + (f"every hex a canon ink · {size / 1024:.1f} of 32 KiB" if ok
                        else (bad[0] if bad else f"{size} B over the 32 KiB cap")), "ok" if ok else "err"))
    head, sep, tail = desk_css(canon, "literal", lock).partition(":root:not(.dark) {")
    tampered = head + sep + tail.replace(canon.on("signal-go", "paper"), canon.on("signal-live", "paper"), 1)
    refused = any("never on paper" in b for b in desk_check(canon, tampered))
    failed |= not refused
    rows.append(("  ✗ refused  desktop · --signal-live on paper" if refused
                 else "  ! self-test failed: desktop live on paper was NOT refused", "err"))
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


def diff_v1(v2_config: str) -> list:
    if not V1_GHOSTTY.exists():
        return []
    a, b = kv(V1_GHOSTTY.read_text()), kv(v2_config)
    rows = [("--- ghostty/config  (v1 · shipped 2026-07-11)", "meta"), ("+++ v2/out/ghostty/config", "meta")]
    for k in ("theme", "window-theme", "font-size", "adjust-cell-height", "font-style-bold",
              "cursor-style", "background-opacity", "background-blur"):
        if a.get(k) == b.get(k):
            continue
        if k in a:
            rows.append((f"-{k} = {a[k]}", "del"))
        if k in b:
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
    "signal": ("# GLASS STAGE v2 · git · SIGNAL — the v1 reading, every slot a canon ink\n"
               "[color \"diff\"]\n\tmeta = 8\n\tfrag = 12\n\tfunc = 5\n\tcommit = 12\n"
               "\told = 9\n\tnew = 10\n\twhitespace = reverse 9\n"
               "[color \"status\"]\n\theader = 8\n\tbranch = 13\n\tadded = 10\n"
               "\tchanged = 12\n\tuntracked = 8\n\tdeleted = 9\n"
               "[color \"decorate\"]\n\tbranch = 13\n\tremoteBranch = 12\n\tHEAD = 9\n\ttag = 5\n"),
}


# ── the Hermes skin ──────────────────────────────────────────────────────────
def v1_block(key: str) -> str:
    if not V1_SKIN.exists():
        return ""
    m = re.search(rf"^{key}: \|-?\n((?:  .*\n?)+)", V1_SKIN.read_text(), re.M)
    return "\n".join(line[2:] for line in m.group(1).rstrip("\n").split("\n")) if m else ""


def one_ink(art: str, hum: str) -> str:
    """The mark is printed in one ink that holds on both grounds — --hum, the hero."""
    return re.sub(r"#[0-9A-Fa-f]{6}", hum, art.replace("[bold ", "["))


def skin_colors(canon: Canon, gname: str, vname: str) -> dict:
    g, i = GROUNDS[gname], (0 if vname == "literal" else 1)
    return {k: canon.on(g[roles[i]], g["ground"]) for k, roles in SKIN_KEYS.items()}



# ── the Desktop layer: customCSS over the palette the app paints inline ─────
# Hermes Desktop writes its palette inline on <html> (apps/desktop/src/themes/context.tsx applyTheme)
# and sets .dark from the painted ground's luminance. A stylesheet outranks an inline declaration only
# with !important, so the skin's customCSS restates every token the app paints, from the terminals'
# roles: :root.dark carries the stage, :root:not(.dark) the paper. Today's Desktop derives one palette
# for both switch positions (from `colors`, the stage), so it wears the stage either way; with paired
# palettes (NousResearch/hermes-agent#81941) the same rules give it both grounds.
DESK_KEYS = {  # token → (LITERAL role, SIGNAL role); "on:<role>" = the canon ink that reads on that fill
    "--theme-background-seed": ("ground", "ground"), "--theme-sidebar-seed": ("ground", "ground"),
    "--theme-card-seed": ("ground", "ground"), "--theme-bubble-seed": ("ground", "ground"),
    "--theme-elevated-seed": ("bar", "bar"),
    "--dt-popover": ("bar", "bar"),  # opaque: the app frosts menus at 96 %; glass belongs to gates and the door
    "--theme-foreground": ("ink", "ink"), "--theme-secondary": ("field", "field"),
    "--theme-primary": ("door", "door"), "--theme-warm": ("door", "door"),
    "--theme-midground": ("ink", "locator"), "--theme-accent-soft": ("mark", "mark"),
    "--ui-text-primary": ("ink", "ink"), "--ui-text-secondary": ("field", "field"),
    # the app's tertiary is 54 % of its ink (muted-foreground, labels, tool summaries): it reads at the field;
    # its quaternary (36 %) stays the ghost
    "--ui-text-tertiary": ("field", "field"), "--ui-text-quaternary": ("ghost", "ghost"),
    "--dt-border": ("rule", "rule"), "--dt-input": ("rule", "rule"),
    "--dt-sidebar-border": ("rule", "rule"), "--dt-user-bubble-border": ("rule", "rule"),
    "--dt-ring": ("door", "door"), "--dt-composer-ring": ("door", "door"), "--dt-muted": ("bar", "bar"),
    "--dt-primary-solid": ("door", "door"), "--dt-primary-foreground": ("on:door", "on:door"),
    "--dt-primary-solid-foreground": ("on:door", "on:door"),
    "--dt-secondary-foreground": ("ink", "ink"), "--dt-accent-foreground": ("mark_ink", "mark_ink"),
    "--dt-midground-foreground": ("on:ink", "on:locator"),
    "--dt-destructive": ("flag", "flag"), "--dt-destructive-foreground": ("on:flag", "on:flag"),
    "--ui-success": ("ink", "enters"),
    # the app's named hues (styles.css --ui-<hue>), read by meaning like the Ghostty slots: red is the flag;
    # LITERAL promotes every other hue to full ink, SIGNAL keeps the v1 slots
    "--ui-danger": ("flag", "flag"),  # read with a coral fallback (#f87171) where the app leaves it unset
    "--ui-red": ("flag", "flag"), "--ui-orange": ("ink", "locator"), "--ui-yellow": ("ink", "locator"),
    "--ui-green": ("ink", "enters"), "--ui-cyan": ("ink", "field"), "--ui-blue": ("ink", "locator"),
    "--ui-purple": ("ink", "seen"),
    # .hub-diff: diffs carry no colour on either ground (LITERAL); SIGNAL keeps enters / flag
    # (LITERAL's lines carry no gutter; the border token still paints the overview strip, at the field)
    "--ui-diff-add-border": ("field", "enters"), "--ui-diff-remove-border": ("field", "flag"),
    "--ui-diff-add-foreground": ("ink", "enters"), "--ui-diff-remove-foreground": ("ink", "flag"),
    # the self-improvement review: one ink, no gold-to-purple gradient, no glow
    "--tool-memory-legendary-from": ("ink", "locator"), "--tool-memory-legendary-mid": ("ink", "locator"),
    "--tool-memory-legendary-to": ("ink", "locator"), "--tool-memory-legendary-icon": ("field", "locator"),
    "--tool-memory-legendary-meta": ("field", "field"),
}
# flat: no neutral chrome mixed into the ground, no grain; the canon draws depth with hairlines
DESK_FLAT = {"--theme-mix-chrome": "100%", "--theme-mix-sidebar": "100%", "--theme-mix-card": "100%",
             "--theme-mix-elevated": "100%", "--theme-mix-bubble": "100%", "--noise-opacity-mul": "0",
             "--ui-diff-add-background": "transparent", "--ui-diff-remove-background": "transparent",
             "--tool-memory-legendary-glow": "transparent"}
DESK_GROUNDS = (("stage", ":root.dark"), ("paper", ":root:not(.dark)"))
DESK_PROBES = {"background": "ground", "foreground": "ink", "card": "ground", "sidebar": "ground",
               "popover": "bar", "border": "rule", "primary": "door", "primary_fg": "on:door",
               "muted": "bar", "accent": "mark", "accent_fg": "mark_ink", "ring": "door",
               "composer_ring": "door", "destructive": "flag", "text_secondary": "field",
               "muted_fg": "field", "caret": "cursor", "selection": "mark", "timeline_popover": "bar"}


def desk_value(canon: Canon, gname: str, role: str) -> str:
    g = GROUNDS[gname]
    if role.startswith("on:"):
        fill = canon.on(g[role[3:]], g["ground"])
        return max((canon.on("ink", g["ground"]), canon.on("paper", g["ground"])),
                   key=lambda c: contrast(c, fill))
    return canon.on(g[role], g["ground"])


# ── the record layer: code, diffs and counts ─────────────────────────────────
# Shiki paints every token inline: chat fences and inline diffs in github-dark-dimmed /
# github-light-default (shiki-config.ts), the file preview in github-*-default (preview-file.tsx),
# Streamdown fences in github-dark / github-light (@streamdown/code's default). The five GitHub
# palettes share one structure, so each token is read by the theme colour it carries and restated
# from the terminal roles — the Desktop's own slot map. Re-derive with v2/tools/record_proof.py.
SHIKI_GROUPS = {  # category → (stage colours: dimmed, dark-default, dark · paper colours: light-default, light)
    "default": (("#ADBAC7", "#E6EDF3", "#E1E4E8"), ("#1F2328", "#24292E")),
    "comment": (("#768390", "#8B949E", "#6A737D"), ("#6E7781", "#57606A", "#6A737D")),  # #57606A: the app's light comment
    "keyword": (("#F47067", "#FF7B72", "#F97583"), ("#CF222E", "#D73A49")),
    "constant": (("#6CB6FF", "#79C0FF", "#79B8FF"), ("#0550AE", "#005CC5")),
    "name": (("#F69D50", "#FFA657", "#FFAB70"), ("#953800", "#E36209")),
    "function": (("#DCBDFB", "#D2A8FF", "#B392F0"), ("#8250DF", "#6F42C1")),
    "tag": (("#8DDB8C", "#7EE787", "#85E89D"), ("#116329", "#22863A")),
    "string": (("#96D0FF", "#A5D6FF", "#9ECBFF", "#DBEDFF"), ("#0A3069", "#032F62")),
    "invalid": (("#FF938A", "#FFA198", "#FDAEB7"), ("#82071E", "#B31D28")),
    "quiet": (("#CDD9E5", "#2D333B", "#F0F6FC", "#161B22", "#24292E", "#2F363D", "#D1D5DA"),
              ("#F6F8FA", "#EAEEF2", "#FAFBFC", "#586069")),
}
SYNTAX = {  # category → (LITERAL role, SIGNAL role): SKIN_KEYS syntax_* where the skin names one, else the slot map
    "default": ("field", "ink"), "comment": ("ghost", "ghost"), "keyword": ("ink", "locator"),
    "constant": ("ink", "seen"), "name": ("ink", "ink"), "function": ("ink", "ink"), "tag": ("ink", "enters"),
    "string": ("field", "enters"), "invalid": ("flag", "flag"), "quiet": ("ghost", "ghost"),
}
DIFF_ADD, DIFF_REMOVE = '[class~="border-(--ui-diff-add-border)"]', '[class~="border-(--ui-diff-remove-border)"]'
COUNTS = {  # the +N / −N beside a file (DiffCount) and in a tool header (Tailwind emerald / rose)
    "--ui-diff-add-foreground": ('[class~="text-(--ui-green)"]', '[class~="dark:text-emerald-400"]',
                                 '[class~="text-emerald-600"]'),
    "--ui-diff-remove-foreground": ('[class~="text-(--ui-red)"]', '[class~="dark:text-rose-400"]',
                                    '[class~="text-rose-600"]'),
}


def rgb_of(hx: str) -> str:
    return "rgb(%d, %d, %d)" % (int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16))


def token_selectors(gname: str, hexes) -> str:
    # each render path writes the theme colour its own way: Shiki's HTML (--shiki-dark:#F47067),
    # Streamdown's React props (--shiki-dark: #F47067; --sdm-c on paper), the diff renderer (color: rgb(…))
    keys = ("--shiki-dark:", "--shiki-dark: ") if gname == "stage" else ("--shiki-light:", "--sdm-c: ")
    return ", ".join([f'[style*="{k}{hx}" i]' for hx in hexes for k in keys]
                     + [f'[style*="color: {rgb_of(hx)}"]' for hx in hexes])


def desk_record(canon: Canon, gname: str, sel: str, i: int) -> list:
    hair = canon.raw.get("hairline", "0.5px").strip()
    out = []
    for cat, (stage_hexes, paper_hexes) in SHIKI_GROUPS.items():
        sels = token_selectors(gname, stage_hexes if gname == "stage" else paper_hexes)
        out.append(f"{sel} :is({sels}) {{ color: {desk_value(canon, gname, SYNTAX[cat][i])} !important; }}")
    grounds = '[style*="--shiki-dark-bg"]' if gname == "stage" else '[style*="--shiki-light-bg"], [style*="--sdm-bg"]'
    out.append(f"{sel} :is({grounds}) {{ background-color: transparent !important; }}")  # code sits on the ground
    if i == 0:  # LITERAL · .hub-diff: del struck · ins hairline underline · all ink · nothing else
        ink = desk_value(canon, gname, "ink")
        # ins is a border-bottom in the canon: it sits under the descenders, so the line goes `under`
        out.append(f"{sel} {DIFF_ADD} {{ text-decoration: underline solid {ink} {hair}; "
                   "text-underline-position: under; text-underline-offset: 0.08em; text-decoration-skip-ink: none; }")
        out.append(f"{sel} {DIFF_REMOVE} {{ text-decoration: line-through solid {ink} {hair}; }}")
        # no gutter: the canon diff has none, and against the card's own border it doubles the line;
        # the 2px border stays, transparent, so changed lines keep the context lines' column
        out.append(f'{sel} [class~="border-l-2"]:is({DIFF_ADD}, {DIFF_REMOVE}) {{ border-left-color: transparent !important; }}')
    for token, sels in COUNTS.items():
        out.append(f"{sel} .tabular-nums > :is({', '.join(sels)}) "
                   f"{{ color: {desk_value(canon, gname, DESK_KEYS[token][i])} !important; }}")
    return out



# ── the type: three voices from the canon's specimen (/epoq · 002_type) ──────
# Jacob's ruling: the Desktop wears 03 · Body, 04 · Pills and 05 · Code — nothing else.
#   Body  · serif-body-1 · 14 · 1.6 · +5%   everything read and written: the record, sessions, nav, composer
#   Pills · serif-8-caps · 9 · 2 · +20%    controls, bold, and the record's headings (as the canon's taglines)
#   Code  · mono m6      · 7 · 2 · +30%    labels, times, the bar, keys, table heads (caps) · code, tools, diffs (case kept)
# Bold is not a voice (E1). GS_TYPE=0 builds the record layer without the type.
TYPE = os.environ.get("GS_TYPE", "1") != "0"
RECORD = '[data-slot="aui_assistant-message-content"]'
NOT_CODE = ':not(:is([data-slot="tool-block"], [data-slot^="code-card"], pre) *)'
CHROME = ':is([data-slot="sidebar"], [data-slot="pane-tab"], [data-slot="statusbar"], [data-slot="tool-block"], [data-slot^="composer"], [data-slot="aui_thread-viewport"])'


def desk_type(canon: Canon) -> list:
    raw = canon.raw
    serif, mono = raw["font-serif"], raw["font-mono"]
    body = (f"font-family: {serif} !important; font-size: {raw['fz-body-1']} !important; "
            f"line-height: {raw['lh-body-1']} !important; letter-spacing: {raw['track-body-1']} !important;")
    pills = (f"font-family: {serif} !important; font-size: {raw['fz-serif-8']} !important; line-height: {raw['lh-serif-8']} !important; "
             f"letter-spacing: {raw['track-caps']} !important; text-transform: uppercase !important;")
    code = (f"font-family: {mono} !important; font-size: {raw['fz-mono-6']} !important; "
            f"line-height: {raw['lh-mono-6']} !important; letter-spacing: {raw['track-code']} !important;")
    caps = "text-transform: uppercase !important;"
    each = lambda *sels: ", ".join(f"{x}, {x} :not(svg, svg *)" for x in sels)  # noqa: E731 — the part and its text, never its icons
    slot = lambda name, rest="": f'[data-slot="{name}"]{rest}'  # noqa: E731 — 3.9: no backslash in an f-string expression
    reading = each(slot("row-button"))
    # (not composer-bounds: it wraps the whole chat column, tool rows included)
    controls = each(slot("pane-tab", " .uppercase"), slot("composer-surface", ' [data-slot="tooltip-trigger"]'))
    apparatus = each(slot("sidebar", " .uppercase"), slot("statusbar"), "kbd", RECORD + " th")
    program = each(slot("tool-block"), '[data-slot^="code-card"]', RECORD + " pre", slot("timeline-timestamp"))
    user, menu, door = slot("aui_directive-text"), slot("sidebar-menu-item", " .truncate"), slot("composer-rich-input")
    side_time = slot("sidebar", " time")
    return [
        "/* the type — three voices from the canon's specimen: 03 Body · 04 Pills · 05 Code */",
        f":root {{ --dt-font-sans: {serif} !important; --dt-font-kbd: {mono} !important; }}",
        "*, *::before, *::after { font-weight: 400 !important; }  /* E1: bold is not a voice */",
        # 03 · Body
        f"{RECORD}, {RECORD} :is(p, li, td, blockquote, dd){NOT_CODE}, {user}, {reading}, {menu}, {door} "
        f"{{ {body} --dt-line-height: {raw['lh-body-1']}; }}",
        f"{RECORD} :is(p, ul, ol, blockquote, table):not(li *){NOT_CODE} {{ margin: 0 0 {raw['s-2']} !important; }}",
        f"{RECORD} :is(h1, h2, h3, h4, h5, h6, p, ul, ol, blockquote, table):first-child {{ margin-top: 0 !important; }}",
        f"{RECORD} :is(p, ul, ol, blockquote, table):last-child {{ margin-bottom: 0 !important; }}",
        f"{RECORD} blockquote{NOT_CODE}, {RECORD} blockquote :is(p, li){NOT_CODE} {{ font-style: normal !important; }}",
        f"{RECORD} ul{NOT_CODE} {{ list-style: none !important; padding-left: {raw['s-3']} !important; }}",
        f"{RECORD} ul{NOT_CODE} > li {{ position: relative; }}",
        f"{RECORD} ul{NOT_CODE} > li::before {{ content: \"\u2014\"; position: absolute; left: calc(-1 * {raw['s-2']}); font-family: {serif}; }}",
        # 04 · Pills — the record's headings set as the canon's taglines, held to what they introduce
        f"{RECORD} :is(h1, h2, h3, h4, h5, h6, strong, b, .font-semibold, .font-bold):not(th){NOT_CODE}, {controls} {{ {pills} }}",
        f"{RECORD} :is(h1, h2, h3, h4, h5, h6){NOT_CODE} {{ margin: {raw['s-3']} 0 {raw['s-1']} !important; }}",
        # 05 · Code — the apparatus in caps, the program in its own case
        f"{apparatus} {{ {code} {caps} }}",
        f"{program}, {side_time}, {RECORD} code {{ {code} }}",
        # 05 · Code — an empty chat is titled the way every canon page opens: the masthead (.mono.m6.brand),
        # not a display face; .fit-text's container-query sizing is let go, its measuring twin removed
        f".wordmark {{ {code} {caps} display: block !important; width: auto !important; container-type: normal !important; "
        f"margin: 0 auto {raw['s-1']} !important; mix-blend-mode: normal !important; }}",
        ".wordmark > [aria-hidden] { display: none !important; }",
        ".wordmark > :not([aria-hidden]), .wordmark > :not([aria-hidden]) > * { display: inline-block !important; "
        "inline-size: auto !important; flex-grow: 0 !important; container-type: normal !important; font-size: inherit !important; }",
        # 03 · Body — the line beneath it, balanced like the specimen's sample
        f'[data-slot="aui_intro"] p:last-child:not(.wordmark) {{ {body} text-wrap: balance; }}',
    ]



# ── the palette: Tailwind's raw hues on the canon roles ──────────────────────
# The app's utilities (text-amber-600, bg-emerald-500/10, ring-red-500/30 …) all read a
# --color-<hue>-<shade> variable, so restating those recolours every use, alpha tints included.
# The families read like the app's named hues (DESK_KEYS --ui-*): red and rose are the flag; LITERAL
# promotes every other hue to full ink, SIGNAL keeps the v1 slots. The palest shades on paper and the
# deepest on the stage are the tints a callout lays on its ground, so they fall to the ground itself.
APP_CSS = HOME / ".hermes" / "hermes-agent" / "apps" / "desktop" / "dist" / "assets"
TW_ROLES = {
    "red": ("flag", "flag"), "rose": ("flag", "flag"),
    "orange": ("ink", "locator"), "amber": ("ink", "locator"), "yellow": ("ink", "locator"),
    "lime": ("ink", "enters"), "green": ("ink", "enters"), "emerald": ("ink", "enters"), "teal": ("ink", "enters"),
    "cyan": ("ink", "field"), "sky": ("ink", "locator"), "blue": ("ink", "locator"), "indigo": ("ink", "locator"),
    "violet": ("ink", "seen"), "purple": ("ink", "seen"), "fuchsia": ("ink", "seen"), "pink": ("ink", "seen"),
}
TW_GREYS = {  # the raw greys by lightness onto the canon's own steps
    "paper": {50: "ground", 100: "ground", 200: "ground", 300: "ghost", 400: "ghost", 500: "field", 600: "field",
              700: "ink", 800: "ink", 900: "ink", 950: "ink"},
    "stage": {50: "ink", 100: "ink", 200: "ink", 300: "ink", 400: "field", 500: "field", 600: "ghost", 700: "ghost",
              800: "ground", 900: "ground", 950: "ground"},
}
TW_SEEN = ("red:200,300,400,500,600,700,950 orange:500 amber:50,100,200,300,400,500,600,700,900,950 "
           "emerald:200,300,400,500,600,700 teal:200,600 cyan:300,700 sky:300,500,600,700 blue:300,400,600,700 "
           "violet:400,500,600 fuchsia:300,700 pink:300,500,600,700 rose:300,400,600 "
           "zinc:100,200,300,400,500,600,700")  # the census of 2026-10-14: the floor when no app build is found


def tw_vars() -> list:
    """Every --color-<hue>-<shade> the installed Desktop paints with, plus the census floor."""
    seen = {(f, int(n)) for part in TW_SEEN.split() for f, ns in [part.split(":")] for n in ns.split(",")}
    builds = sorted(APP_CSS.glob("index-*.css"), key=lambda p: p.stat().st_mtime) if APP_CSS.is_dir() else []
    if builds:
        seen |= {(f, int(n)) for f, n in re.findall(r"--color-([a-z]+)-(\d+)\s*:", builds[-1].read_text())}
    return sorted(p for p in seen if p[0] in TW_ROLES or p[0] in ("slate", "gray", "zinc", "neutral", "stone"))


def tw_role(gname: str, family: str, shade: int, i: int) -> str:
    if family not in TW_ROLES:
        return TW_GREYS[gname][shade]
    if (gname == "paper" and shade <= 200) or (gname == "stage" and shade >= 800):
        return "ground"
    return TW_ROLES[family][i]


def desk_palette(canon: Canon, gname: str, sel: str, i: int) -> list:
    decl = " ".join(f"--color-{f}-{n}: {desk_value(canon, gname, tw_role(gname, f, n, i))} !important;" for f, n in tw_vars())
    return [f"{sel} {{ {decl} }}"]


# ── the spot editor: CodeMirror's own chrome on the canon ────────────────────
# Its highlight classes are minted at runtime (ͼ1x), so no selector can tell a keyword from a string:
# every token reads at full ink and a comment keeps the italic its theme gives it. The chrome is
# canon: the cursor is the one live thing, selection and match sit on the bar, no active-line tint.
def desk_editor(canon: Canon, gname: str, sel: str) -> list:
    v = lambda role: desk_value(canon, gname, role)  # noqa: E731
    cm = f"{sel} .cm-editor"
    return [
        f"{cm} {{ color: {v('ink')} !important; }}",
        f'{cm} .cm-content :is([class^="\u037c"], [class*=" \u037c"]) {{ color: inherit !important; }}',
        f"{cm} .cm-content {{ caret-color: {v('cursor')} !important; }}",
        f"{cm} :is(.cm-cursor, .cm-dropCursor) {{ border-left-color: {v('cursor')} !important; }}",
        f"{cm} .cm-selectionBackground, {cm} .cm-content ::selection {{ background-color: {v('bar')} !important; }}",
        f"{cm} :is(.cm-activeLine, .cm-activeLineGutter) {{ background-color: transparent !important; }}",
        f"{cm} .cm-gutters {{ color: {v('ghost')} !important; }}",
        f"{cm} .cm-matchingBracket {{ background-color: {v('bar')} !important; color: {v('ink')} !important; }}",
        f"{cm} .cm-nonmatchingBracket {{ background-color: transparent !important; color: {v('flag')} !important; }}",
        f"{cm} :is(.cm-searchMatch, .cm-searchMatch-selected) {{ background-color: {v('bar')} !important; outline: none !important; }}",
    ]


# ── the frame: the empty stage opens and closes the way every canon page does ─
# Every /epoq page opens on the masthead's cursor (.brand .cursor: `_ Intelligence Matters` in mono m6,
# blinking) and closes on the braille bar (.f-bar: one stroke dashed 2 3 1 4 3 2 1 3 across a 1200-unit
# viewBox). An empty chat wears both: the cursor hangs before the name in the live ink, so the name keeps
# the axis; the bar runs a hairline above the composer at the canon's own scale (one unit = 1px, the
# bar's width on the page it was drawn for), and the frame holds until the first message lands. Both
# marks are parsed from the live page at build time. GS_FRAME=0 builds without it.
FRAME = os.environ.get("GS_FRAME", "1") != "0"
NAME = ".wordmark > :not([aria-hidden]) > *"
BAR = 'body:has(.wordmark) [data-slot="composer-dock"]:not([data-popped-out])::before'


@functools.lru_cache(maxsize=1)
def canon_frame() -> dict:
    styles, site = fetch(WEB + "styles.css"), fetch(WEB)
    blink = re.search(r"\.brand\s+\.cursor\s*\{[^}]*?animation:\s*([\w-]+)\s+([^;}]+)", styles)
    keys = blink and re.search(r"@keyframes\s+" + re.escape(blink.group(1)) + r"\s*\{\s*((?:[^{}]*\{[^{}]*\}\s*)+)\}", styles)
    bar = re.search(r'class="f-bar".*?viewBox="0 0 ([\d.]+) [\d.]+".*?stroke-dasharray="([\d.\s]+)"', site, re.S)
    if not (blink and keys and bar):
        raise SystemExit("✗ the canon's masthead cursor or braille bar moved: read /epoq before building the frame")
    dash = [float(x) for x in bar.group(2).split()]
    return {"blink": " ".join(blink.group(2).split()), "keyframes": " ".join(keys.group(1).split()),
            "dash": dash * (2 if len(dash) % 2 else 1), "units": float(bar.group(1))}


def composer_inset() -> str:
    """The composer's inset inside its dock (composer-root padding-inline, beside the dock's 10px grab
    platform), read from the installed build like the palette: the bar spans the composer you see."""
    builds = sorted(APP_CSS.glob("index-*.css"), key=lambda p: p.stat().st_mtime) if APP_CSS.is_dir() else []
    for css in builds[-1:]:
        m = re.search(r"\[data-slot=['\"]?composer-root['\"]?\]\s*\{[^}]*?padding-inline:\s*([\d.]+px)", css.read_text())
        if m:
            return m.group(1)
    return "5px"  # the app's composer-root padding-inline on 2026-10-14: the floor when no build is found


def braille(ink: str, dash: list) -> str:
    """The f-bar's dasharray as one repeating tile: dash, gap, dash, gap … at one unit = 1px."""
    stops, x = [], 0.0
    for k, n in enumerate(dash):
        stops.append(f"{ink if k % 2 == 0 else 'transparent'} {x:g}px {x + n:g}px")
        x += n
    return f"linear-gradient(90deg, {', '.join(stops)}) 0 0 / {x:g}px 100% repeat-x"


def desk_frame(canon: Canon) -> list:
    raw, f = canon.raw, canon_frame()
    return [
        "/* the frame — the empty stage opens on the canon's masthead cursor and closes on its braille bar */",
        f"@keyframes gs-cursor-blink {{ {f['keyframes']} }}",
        f"{NAME} {{ position: relative !important; margin-right: calc(-1 * {raw['track-code']}) !important; }}",
        f'{NAME}::before {{ content: "_\\00a0"; position: absolute; right: 100%; top: 0; white-space: pre; '
        f"animation: gs-cursor-blink {f['blink']}; }}",
        f"@media (prefers-reduced-motion: reduce) {{ {NAME}::before {{ animation: none; }} }}",
        # A bare 0.5px box is fragile in Chrome: painted a loose 1px on its own, nothing at all inside the
        # dock's translate. A 1px box masked down to its last hairline paints one exact device row at 2x.
        f'{BAR} {{ content: ""; position: absolute; left: {composer_inset()}; right: {composer_inset()}; bottom: calc(100% + {raw["s-2"]}); height: 1px; '
        f"-webkit-mask: linear-gradient(transparent calc(100% - {raw['hairline']}), black 0); "
        f"mask: linear-gradient(transparent calc(100% - {raw['hairline']}), black 0); pointer-events: none; }}",
    ]


def desk_css(canon: Canon, vname: str, lock: dict) -> str:
    i = 0 if vname == "literal" else 1
    out = [f"/* GLASS STAGE v2 · Hermes Desktop · {VARIANTS[vname]['label']} · generated by v2/build.py",
           f"   from {WEB}system.css · sha256 {lock['system.css']['sha256'][:12]} · do not hand-edit.",
           "   The dark class is the stage, its absence the paper; !important outranks the palette",
           "   the app paints inline on <html>. Every colour is a canon ink on its own ground. */"]
    for gname, sel in DESK_GROUNDS:
        g = GROUNDS[gname]
        cursor = canon.on(g["cursor"], g["ground"])
        out.append(f"{sel} {{")
        out += [f"  {k}: {desk_value(canon, gname, roles[i])} !important;" for k, roles in DESK_KEYS.items()]
        out += [f"  {k}: {v} !important;" for k, v in DESK_FLAT.items()]
        out += ['  --dt-font-mono: "Red Hat Mono", ui-monospace, monospace !important;',
                f"  caret-color: {cursor};", "}"]
        out.append(f"{sel} :is(textarea, input, [contenteditable]) {{ caret-color: {cursor}; }}")
        out.append(f"{sel} [data-slot='thread-timeline-popover'] {{ background: {canon.on(g['bar'], g['ground'])} !important; }}")
        out.append(f"{sel} ::selection {{ background: {canon.on(g['mark'], g['ground'])}; "
                   f"color: {canon.on(g['mark_ink'], g['ground'])}; }}")
        out += desk_record(canon, gname, sel, i)
        out += desk_palette(canon, gname, sel, i)
        out += desk_editor(canon, gname, sel)
    if TYPE:
        for gname, sel in DESK_GROUNDS:  # .hub-label · .hub-nav-group-label · .hub-action-time · .tabs button: color var(--ink)
            ink = desk_value(canon, gname, "ink")
            out.append(f"{sel} :is([data-slot=\"sidebar\"], [data-slot=\"pane-tab\"]) :is(.uppercase, .uppercase *):not(svg, svg *), "
                       f"{sel} [data-slot=\"sidebar\"] time, {sel} [data-slot=\"timeline-timestamp\"] {{ color: {ink} !important; }}")
            out.append(f"{sel} .wordmark {{ color: {ink} !important; }}")  # .m6: color var(--ink)
            if FRAME:  # the cursor is the one live thing; the bar is struck in ink, as the canon strokes it
                out.append(f"{sel} {NAME}::before {{ color: {desk_value(canon, gname, 'cursor')} !important; }}")
                out.append(f"{sel} {BAR} {{ background: {braille(ink, canon_frame()['dash'])}; }}")
        out += desk_type(canon)
        if FRAME:
            out += desk_frame(canon)
    return "\n".join(out) + "\n"


def desk_check(canon: Canon, css: str) -> list:
    bad, bare = [], re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for gname, sel in DESK_GROUNDS:
        ground = GROUNDS[gname]["ground"]
        allowed, live = canon.allowed(ground), canon.on("signal-live", ground)
        body = " ".join(re.findall(re.escape(sel) + r"(?:\s[^{]*)?\{([^}]*)\}", bare))
        for hx in re.findall(r"#[0-9A-Fa-f]{6}\b", body):
            if hx.upper() not in allowed:
                bad.append(f"{hx} is no canon ink on {gname}")
            if gname == "paper" and hx.upper() == live:
                bad.append("--signal-live on paper · reads on --glass-stage, never on paper")
    return bad


def desk_expect(canon: Canon) -> dict:
    return {v: {g: {p: desk_value(canon, g, r) for p, r in DESK_PROBES.items()} for g, _ in DESK_GROUNDS}
            for v in VARIANTS}


def hermes_skin(canon: Canon, vname: str, lock: dict) -> str:
    hum = canon.on("hum", "paper")
    name = "glass-stage" if vname == "literal" else "glass-stage-signal"
    stage = skin_colors(canon, "stage", vname)

    def block(key, s):
        return f"{key}: |-\n" + "\n".join("  " + line for line in s.split("\n")) + "\n"

    L = [f"# {name} — GLASS STAGE v2 · Hermes skin · {VARIANTS[vname]['label']}",
         f"# generated by v2/build.py from {WEB}system.css · sha256 {lock['system.css']['sha256'][:12]}",
         "# colors = the stage inks · dark_colors = the stage ground · light_colors = the paper terminal, inks + ground.",
         "# No background in colors: the Ink TUI reads the terminal's polarity, so it turns when Ghostty turns.",
         "# The classic CLI (display.interface: cli) reads light_colors once the paired-palette patch lands.",
         "# customCSS = the Desktop layer: the same roles, restated over the palette the app paints inline.",
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
          "# the mark, printed in one ink that holds on both grounds: --hum, the hero"]
    text = "\n".join(L) + "\n"
    logo, hero = v1_block("banner_logo"), v1_block("banner_hero")
    if logo:
        text += block("banner_logo", one_ink(logo, hum))
    if hero:
        text += "\n" + block("banner_hero", one_ink(hero, hum))
    text += ("\n# the Desktop layer: Hermes Desktop injects this while the skin is active (GUI only, 32 KiB cap)\n"
             + block("customCSS", desk_css(canon, vname, lock).rstrip("\n")))
    return text


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
    raw += [[], P(bench) + [("python3 v2/build.py --diff-v1", "cmd")]]
    raw += [[(text, kind)] for text, kind in diff_rows]
    raw += [[(" background = ", "out"), ("000000", "mark")], [],
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
    ("The banner", "one ink must hold on both grounds",
     "printed in --hum, like THE MUSE; the braille hero thins on paper (4.0) — a polarity-aware banner rides the Nous patch"),
    ("Glass on the Ghostty window", "glass on agency surfaces only", "opaque; v1 ran 0.94 + blur"),
    ("Desktop register", "main-view law", "HUB shell + serif voice; CLI only at the door; glass on gates + door"),
    ("The door's glass", "colour arrives only where something has to happen",
     "the gate emits, the door refracts: on the stage the composer keeps no fringe and no bleed, rim 0.4, frost 10"),
    ("Desktop on the stage", "workhorse rows are paper-native", "PROPOSAL: E13's exception — paper on ink. Needs an epoq3 ruling"),
    ("The Desktop layer", "the app paints one palette inline; .dark follows the ground's luminance",
     "customCSS restates every token from the terminal roles: flat ground, no grain, colour at the door, the mark and the flag. Today's Desktop wears the stage in both switch positions; the paper arrives with paired palettes (#81941)"),
    ("The record on the Desktop", ".hub-diff · the terminal roles",
     "code: LITERAL promotes a program's colour to full ink, strings in the field, comments in the ghost · diffs carry no colour: del struck, ins hairline-underlined under the descenders, no gutter · counts in ink · the review loses its gradient"),
    ("Type on the Desktop", "/epoq 002_type · 03 Body · 04 Pills · 05 Code",
     "the record in Scheherazade New at the canon body over the app's text scale; apparatus in Red Hat Mono mono-6; "
     "Jacob's three voices from the specimen: Body (serif-body-1) for all reading and writing, Pills (serif-8-caps) for controls, "
     "bold and the record's headings, Code (mono m6) for the apparatus and the program; weight 400 everywhere (E1); 7px apparatus at full ink"),
    ("Raw hues on the Desktop", "the app's named hues · the Ghostty slots",
     "every Tailwind --color-<hue>-<shade> the app paints with: red and rose are the flag, LITERAL promotes the rest to ink "
     "(SIGNAL keeps the v1 slots); the palest shades on paper and the deepest on the stage fall to the ground"),
    ("The spot editor", "colour arrives only where something has to happen",
     "CodeMirror mints its token classes at runtime: every token at full ink, comments keep their italic; "
     "the cursor is the live one, selection on the bar, no active-line tint"),
    ("Meta on the Desktop", "the app's tertiary is 54 % of its ink",
     "it reads at the field (--paper-62); the 36 % quaternary stays the ghost"),
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


def desk(ground: str) -> str:
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
    receipt = ('<div class="station"><div class="term" aria-label="a receipt — the canon paper terminal">'
               '<div class="term-body mono"><div class="term-stream">'
               '<span class="term-row term-cmd"><span class="pr">op@hub</span>:~/glass-stage-v2$ python3 v2/build.py --diff-v1</span>'
               '<span class="term-row term-out"><del>window-theme = dark</del></span>'
               '<span class="term-row term-out"><ins>window-theme = auto</ins></span>'
               '<span class="term-row term-out"><del>background-opacity = 0.94</del></span>'
               '<span class="term-row term-out"><ins>background-opacity = 1</ins></span>'
               '<span class="term-row term-out"><del>cursor-style = block</del></span>'
               '<span class="term-row term-out"><ins>cursor-style = bar</ins></span>'
               '<span class="term-row term-out"><ins>theme = light:glass-paper,dark:glass-stage</ins></span>'
               '</div></div></div></div>')
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
    logo, hero = one_ink(v1_block("banner_logo"), hum), one_ink(v1_block("banner_hero"), hum)

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
              '<span class="mono m6">literal · colour only for the door, the mark, the flag — signal · the v1 reading, every ink a token</span></div>')

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
 <div class="gridrow"><div class="container-tile u-full"><div class="spec-rail mono m6"><span class="family">hermes tui</span><span>mock after hermes_cli/banner.py · inks from v2/out/hermes/glass-stage.yaml</span><span>classic CLI on paper · the Nous patch</span><span class="open-ruling">banner in one ink</span></div></div></div>
</section>

<section id="desktop" class="epoq-section" data-density="tight">
 <div class="section-mark">
  <h2 class="serif-page-title">004_desktop</h2>
  <p class="sec-tagline serif-8-caps">Desktop is a main view, so it wears the HUB shell — the record in the workhorse rows, the serif carrying the prose, glass only on the gate and the door.</p>
 </div>
 <div class="gridrow"><div class="container-tile u-full">{desk("paper")}</div></div>
 <div class="gridrow"><div class="container-tile u-full">{desk("stage")}</div></div>
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
    diff_rows = diff_v1(cfg)
    if "--diff-v1" in args:
        print("\n".join(r for r, _ in diff_rows))
        return 0

    themes = {(g, v): theme(canon, g, v) for g in GROUNDS for v in VARIANTS}
    for d in ("ghostty/themes", "git", "shell", "hermes", "desktop", "workshop"):
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
        (OUT / "desktop" / f"{name}.css").write_text(desk_css(canon, vname, lock))
        (OUT / "desktop" / "expect.json").write_text(json.dumps(desk_expect(canon), indent=2) + "\n")

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
