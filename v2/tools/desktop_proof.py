#!/usr/bin/env python3
"""Prove the Desktop layer inside Hermes Desktop's own token chain, without launching the app.

Takes the installed app's token blocks from apps/desktop/src/styles.css (@theme inline, :root,
:root.dark), paints a hostile palette inline on <html> the way applyTheme does (every token the
layer restates set to magenta, every mix 0 %), injects the skin's customCSS, and reads back what
the app would paint on both grounds. A control run without the layer proves the hostile palette
is live, so every match is the layer's doing. Run from the glass-stage repo root:

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/desktop_proof.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

V2 = pathlib.Path(__file__).resolve().parents[1]
STYLES = pathlib.Path.home() / ".hermes/hermes-agent/apps/desktop/src/styles.css"
PROBES = {  # what the app paints with → the expression a probe reads
    "background": "var(--dt-background)",
    "foreground": "var(--dt-foreground)",
    "card": "var(--dt-card)",
    "sidebar": "var(--sidebar)",
    "popover": "var(--popover, var(--dt-popover))",
    "border": "var(--dt-border)",
    "primary": "var(--dt-primary)",
    "primary_fg": "var(--dt-primary-foreground)",
    "muted": "var(--dt-muted)",
    "accent": "var(--dt-accent)",
    "accent_fg": "var(--dt-accent-foreground)",
    "ring": "var(--dt-ring)",
    "composer_ring": "var(--dt-composer-ring)",
    "destructive": "var(--dt-destructive)",
    "text_secondary": "var(--ui-text-secondary)",
    "muted_fg": "var(--dt-muted-foreground)",
}
SLOTS = {"timeline_popover": "thread-timeline-popover"}  # component rules the app writes itself
READ = """(tokens) => {
  const root = document.documentElement;
  for (const k of tokens) {
    root.style.setProperty(k, k.includes('mix') ? '0%' : k === '--noise-opacity-mul' ? '1'
                              : k.includes('font') ? 'serif' : '#ff00ff');
  }
  const out = {};
  for (const mode of ['dark', 'light']) {
    root.classList.toggle('dark', mode === 'dark');
    const row = {};
    for (const el of document.querySelectorAll('[data-probe]')) {
      row[el.dataset.probe] = getComputedStyle(el).backgroundColor;
    }
    row.caret = getComputedStyle(document.getElementById('caret')).caretColor;
    row.selection = getComputedStyle(document.getElementById('sel'), '::selection').backgroundColor;
    out[mode] = row;
  }
  return out;
}"""


def blocks(css: str, opener: str) -> list[str]:
    out = []
    for m in re.finditer(opener, css):
        i = j = m.end()
        depth = 1
        while depth and j < len(css):
            depth += (css[j] == "{") - (css[j] == "}")
            j += 1
        out.append(css[i:j - 1])
    return out


def decls(body: str) -> list[str]:
    """custom-property declarations at the top of a block; nested rules are skipped"""
    res, buf, paren, brace = [], "", 0, 0
    for c in body:
        if c == "{":
            brace += 1
            continue
        if c == "}":
            brace -= 1
            buf = ""
            continue
        if brace:
            continue
        paren += (c == "(") - (c == ")")
        if c == ";" and paren == 0:
            if buf.strip().startswith("--"):
                res.append(buf.strip())
            buf = ""
        else:
            buf += c
    return res


def to_hex(v: str) -> str:
    v = v.strip()
    m = re.fullmatch(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)", v)
    if m:
        rgb, a = [round(float(x)) for x in m.group(1, 2, 3)], float(m[4] or 1)
    else:
        m = re.fullmatch(r"color\(srgb ([-\d.e]+) ([-\d.e]+) ([-\d.e]+)(?: / ([\d.]+))?\)", v)
        if not m:
            return v or "unresolved"
        rgb, a = [round(float(x) * 255) for x in m.group(1, 2, 3)], float(m[4] or 1)
    return "#%02X%02X%02X" % tuple(rgb) + ("" if a >= 0.999 else f" @{a:.2f}")


def main() -> int:
    css = re.sub(r"/\*.*?\*/", "", STYLES.read_text(), flags=re.S)
    root = [d for b in blocks(css, r"@theme\s+inline\s*\{") + blocks(css, r"(?<![\w.-]):root\s*\{") for d in decls(b)]
    dark = [d for b in blocks(css, r":root\.dark\s*\{") for d in decls(b)]
    sheet = ":root{" + ";".join(root) + "}\n:root.dark{" + ";".join(dark) + "}"
    for slot in SLOTS.values():  # the app's own rule for each slot, so the probe runs the real cascade
        sel = f"[data-slot='{slot}']"
        sheet += "\n" + "".join(f"{sel}{{{b}}}" for b in blocks(css, re.escape(sel) + r"\s*\{"))
    expect = json.loads((V2 / "out/desktop/expect.json").read_text())
    probes = "".join(f'<div data-probe="{k}" style="background-color:{v};width:4px;height:4px"></div>'
                     for k, v in PROBES.items())
    probes += "".join(f'<div data-probe="{k}" data-slot="{v}" style="width:4px;height:4px"></div>'
                       for k, v in SLOTS.items())
    report: dict = {"app_tokens": {"root": len(root), "dark": len(dark)}}
    misses = 0
    with sync_playwright() as p:
        try:  # the installed Chrome first: Playwright's own headless shell may not be downloaded
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:  # noqa: BLE001
            browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for vname, stem in (("literal", "glass-stage"), ("signal", "glass-stage-signal")):
            layer = (V2 / "out/desktop" / f"{stem}.css").read_text()
            tokens = sorted(set(re.findall(r"(--[\w-]+)\s*:", layer)))
            runs = {}
            for label, skin in (("control", ""), ("layer", layer)):
                page.set_content(f"<!doctype html><html><head><style>{sheet}</style><style>{skin}</style></head>"
                                 f"<body>{probes}<textarea id='caret'></textarea><p id='sel'>x</p></body></html>")
                runs[label] = page.evaluate(READ, tokens)
            rows = {}
            for mode, ground in (("dark", "stage"), ("light", "paper")):
                for probe, want in expect[vname][ground].items():
                    got = to_hex(runs["layer"][mode].get(probe, ""))
                    ok = got == want
                    misses += not ok
                    rows.setdefault(probe, {})[ground] = {"got": got, "want": want, "ok": ok,
                                                          "control": to_hex(runs["control"][mode].get(probe, ""))}
            report[vname] = {"tokens_restated": len(tokens), "probes": rows}
            print(f"\n{vname.upper()} · {len(tokens)} tokens restated · the app's own chain: "
                  f"{len(root)} :root + {len(dark)} :root.dark declarations")
            print(f"  {'probe':<15} {'stage (.dark)':<26} {'paper':<26} control(stage)")
            for probe, r in rows.items():
                cell = lambda g: f"{'✓' if r[g]['ok'] else '✗'} {r[g]['got']:<9}" + ("" if r[g]['ok'] else f" want {r[g]['want']}")  # noqa: E731
                print(f"  {probe:<15} {cell('stage'):<26} {cell('paper'):<26} {r['stage']['control']}")
        browser.close()
    (V2 / "out/desktop/proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"\n{'PASS' if not misses else 'FAIL'} · {misses} probe(s) off")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
