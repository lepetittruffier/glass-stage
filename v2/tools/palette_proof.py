#!/usr/bin/env python3
"""Prove the palette and the spot editor in Hermes Desktop's own compiled stylesheet.

The palette: every --color-<hue>-<shade> the app paints with must resolve to its canon role on each
ground, and every plain or dark: utility that reads one (text, bg, border, fill, stroke, outline,
decoration — alpha tints included) must compute to a canon ink, or a tint of one over the ground.
The spot editor: CodeMirror mints its classes at runtime, so its GitHub theme is mimicked the way
it lands (a scoped root colour, token classes, a blue selection, a teal bracket wash) and every
part must read on the canon. The coral --ui-danger fallback must read as the flag.

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/palette_proof.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

V2 = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", V2 / "build.py")
assert spec and spec.loader
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

KINDS = {"text": "color", "bg": "backgroundColor", "border": "borderTopColor", "fill": "fill", "stroke": "stroke",
         "outline": "outlineColor", "decoration": "textDecorationColor"}
CM = """
.ͼ1 { color: #e6edf3; } .ͼ1 .cm-content { caret-color: #e6edf3; } .ͼ1 .cm-cursor { border-left-color: #e6edf3; }
.ͼ1 .cm-selectionBackground { background-color: rgba(56,139,253,0.25); } .ͼ2 .cm-activeLine { background-color: #99eeff33; }
.ͼ2 .cm-matchingBracket { background-color: #328c8252; } .ͼ9 { color: #ff7b72; } .ͼa { color: #a5d6ff; }
.ͼb { color: #8b949e; font-style: italic; }"""
EDITOR = ('<div class="cm-editor ͼ1 ͼ2"><div class="cm-gutters" id="cm-gut">12</div><div class="cm-content" id="cm-content">'
          '<div class="cm-line cm-activeLine" id="cm-active"><span class="ͼ9" id="cm-kw">def</span> x = '
          '<span class="ͼa" id="cm-str">"s"</span> <span class="ͼb" id="cm-com"># c</span> '
          '<span class="cm-matchingBracket" id="cm-br">(</span></div></div>'
          '<div class="cm-selectionBackground" id="cm-sel" style="width:20px;height:9px"></div>'
          '<div class="cm-cursor" id="cm-cur" style="border-left:1px solid;height:9px"></div></div>')

READ = """({samples, vars, kinds}) => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
  const rgba = c => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgba(1, 2, 3, 0.5)'; const was = cx.fillStyle; cx.fillStyle = c;
    if (cx.fillStyle === was && c !== 'rgba(1, 2, 3, 0.5)') return null;      // unparsed: never a silent pass
    cx.fillRect(0, 0, 1, 1); return [...cx.getImageData(0, 0, 1, 1).data]; };
  const host = document.getElementById('host'); host.textContent = '';
  const out = { vars: {}, samples: [] };
  const root = getComputedStyle(document.documentElement);
  for (const v of vars) out.vars[v] = root.getPropertyValue(v).trim();
  for (const cls of samples) {
    const el = document.createElement('span'); el.className = cls; el.textContent = 'x'; host.append(el);
    const kind = cls.split(':').pop().split('-')[0];
    const val = getComputedStyle(el)[kinds[kind]];
    out.samples.push([cls, val, rgba(val)]);
  }
  const q = id => getComputedStyle(document.getElementById(id));
  out.editor = { kw: rgba(q('cm-kw').color), str: rgba(q('cm-str').color), com: rgba(q('cm-com').color), italic: q('cm-com').fontStyle,
    caret: rgba(q('cm-content').caretColor), cur: rgba(q('cm-cur').borderLeftColor), sel: rgba(q('cm-sel').backgroundColor),
    active: q('cm-active').backgroundColor, gut: rgba(q('cm-gut').color), br: rgba(q('cm-br').backgroundColor),
    danger: rgba(getComputedStyle(document.getElementById('danger')).color) };
  return out;
}"""

PAGE = """<!doctype html><html class="{cls}"><head><meta charset="utf-8"><style>{app}</style><style>{cm}</style>
<style id="hermes-desktop-custom-css">{layer}</style></head><body class="bg-background text-foreground">
<div id="host"></div>{editor}<span id="danger" class="text-(--ui-danger,#f87171)">danger</span></body></html>"""


def hexrgb(hx: str) -> tuple:
    return tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))


def lawful(px, ground: tuple, inks: list) -> bool:
    """A canon ink, at any alpha: the canvas returns a tint's own colour and its alpha, and
    un-premultiplying 8 bits is coarse at low alpha, so the tolerance widens as alpha falls."""
    if px is None:
        return False
    a = px[3] / 255
    if a < 0.02:
        return True
    tol = 2.5 + 0.5 / a
    return any(all(abs(x - c) <= tol for x, c in zip(ink, px[:3])) for ink in inks)


def utilities(css: str) -> list:
    out = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if not re.search(r"var\(--color-[a-z]+-\d+", body):
            continue
        for m in re.finditer(r"\.((?:dark\\:)?(?:text|bg|border|fill|stroke|outline|decoration)-[a-z]+-\d+(?:\\/\d+)?)(?=[\s,:{.]|$)", sel):
            out.add(m.group(1).replace("\\", ""))
    return sorted(out)


def main() -> int:
    app = sorted(build.APP_CSS.glob("index-*.css"), key=lambda p: p.stat().st_mtime)[-1].read_text()
    canon = build.Canon(build.fetch(build.WEB + "system.css"))
    pal = [f"--color-{f}-{n}" for f, n in build.tw_vars()]
    used = sorted(set(re.findall(r"--color-(?:" + "|".join(build.TW_ROLES) + r"|slate|gray|zinc|neutral|stone)-\d+(?=\s*:)", app)))
    samples = utilities(app)
    fails = [f"  ✗ the app paints {v}, the layer does not restate it" for v in used if v not in pal]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()
        for i, vname in enumerate(build.VARIANTS):
            layer = (V2 / "out/desktop" / ("glass-stage.css" if vname == "literal" else "glass-stage-signal.css")).read_text()
            for gname, cls in (("stage", "dark"), ("paper", "")):
                page.set_content(PAGE.format(cls=cls, app=app, cm=CM, layer=layer, editor=EDITOR), wait_until="load")
                got = page.evaluate(READ, {"samples": samples, "vars": pal, "kinds": KINDS})
                v = lambda role: build.desk_value(canon, gname, role)  # noqa: E731
                ground = hexrgb(v("ground"))
                inks = [hexrgb(h) for h in canon.allowed(build.GROUNDS[gname]["ground"])] + [ground]
                bad = []
                for name in pal:
                    f, n = name.split("-")[3], int(name.split("-")[4])
                    want = v(build.tw_role(gname, f, n, i))
                    if got["vars"][name].upper() != want.upper():
                        bad.append(f"{name} = {got['vars'][name]} ≠ {want}")
                bad += [f"{c} → {val}" for c, val, px in got["samples"] if not lawful(px, ground, inks)]
                e, rgb = got["editor"], lambda role: list(hexrgb(v(role))) + [255]  # noqa: E731
                for k, role in (("kw", "ink"), ("str", "ink"), ("com", "ink"), ("caret", "cursor"), ("cur", "cursor"),
                                ("sel", "bar"), ("gut", "ghost"), ("br", "bar"), ("danger", "flag")):
                    if e[k] != rgb(role):
                        bad.append(f"editor.{k} = {e[k]} ≠ {role} {v(role)}")
                if e["italic"] != "italic":
                    bad.append("editor comment lost its italic")
                if e["active"] not in ("rgba(0, 0, 0, 0)", "transparent"):
                    bad.append(f"editor active line tinted {e['active']}")
                print(f"  {'✓' if not bad else '✗'} {vname:8} {gname:6} {len(pal)} hues · {len(samples)} utilities · editor + danger")
                fails += [f"    ✗ {vname} {gname} {x}" for x in bad]
        browser.close()
    print("\n".join(fails) if fails else "  no raw hue survives: every utility reads a canon ink or its tint")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
