#!/usr/bin/env python3
"""Prove the frame: an empty chat opens on the canon's masthead cursor and closes on its braille bar.

Read-only. No Hermes instance is launched: the empty state is laid out in Chrome from the class
strings the app's own source gives it (lifted at run time, so a moved component fails loudly), under
the app's compiled stylesheet and the built layer, on both grounds, at 2x. It checks:

  the masthead   05 Code in caps (Red Hat Mono 7 / 2 / +30%), weight 400, ink; the fit-text twin gone
  the axis       the name sits on the column's centre; the cursor hangs before it, in the cursor ink
  the blink      the canon's own animation, seeked: lit in the first half-period, dark in the second;
                 still and lit under prefers-reduced-motion
  the line       03 Body (Scheherazade New 14 / 1.6 / +5%), the field ink, balanced
  the bar        a 0.5px hairline 16px above the composer, ink, whose pixels run the canon's dasharray
                 at one unit = 1px; gone once the record starts and when the composer pops out

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/frame_proof.py [--shots DIR]
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import struct
import sys
import zlib

from playwright.sync_api import sync_playwright

V2 = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path.home() / ".hermes" / "hermes-agent" / "apps" / "desktop" / "src"
spec = importlib.util.spec_from_file_location("build", V2 / "build.py")
assert spec and spec.loader
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
DPR = 2


def lift(path: str, pattern: str) -> str:
    m = re.search(pattern, (SRC / path).read_text(), re.S)
    if not m:
        raise SystemExit(f"✗ the app moved: no match for {pattern!r} in {path}")
    return m.group(1)


def markup() -> str:
    near = lambda slot: r'className="([^"]+)"[^>]*?data-slot="' + slot + '"'  # noqa: E731
    bounds = lift("app/chat/index.tsx", near("composer-bounds"))
    thread = lift("components/assistant-ui/thread/index.tsx", near("thread"))
    empty = lift("components/assistant-ui/thread/index.tsx", r'emptyPlaceholder = emptyBody \? \(\s*<div className="([^"]+)"')
    intro = lift("components/chat/intro.tsx", near("aui_intro"))
    mark = lift("components/chat/wordmark.tsx", r"'(wordmark fit-text[^']*)'") + " " + \
        lift("components/chat/intro.tsx", r'<Wordmark className="([^"]+)"')
    line = lift("components/chat/intro.tsx", r'<p className="([^"]+)">\{body\}</p>')
    dock = lift("app/chat/composer/index.tsx", r"'(group/composer-dock[^']*)'") + " " + \
        lift("app/chat/composer/index.tsx", r"'(absolute bottom-0 left-1/2[^']*)'")
    root = lift("app/chat/composer/index.tsx", r"'(group/composer relative[^']*)'")
    surface = lift("app/chat/composer/index.tsx", r"'(group/composer-surface[^']*)'")
    return f"""
<div id="pane" style="position:relative;width:100vw;height:100vh;display:flex;flex-direction:column">
 <div class="{bounds}" data-slot="composer-bounds">
  <div class="{thread}" data-slot="thread">
   <div data-slot="aui_thread-viewport" style="display:flex;flex-direction:column;height:100%;overflow-y:auto">
    <div class="{empty}" style="flex:1">
     <div class="{intro}" data-slot="aui_intro"><div class="w-full min-w-0">
      <p aria-label="HERMES AGENT" class="{mark}" style="--fit-min: 2.75rem; width: calc(100% - 1rem)">
       <span><span id="name">HERMES AGENT</span></span><span aria-hidden="true">HERMES AGENT</span></p>
      <p class="{line}" id="line">Send a bug, branch, plan, or rough idea. I'll inspect the repo and turn it into the next concrete step.</p>
     </div></div>
    </div>
   </div>
  </div>
 </div>
 <div class="{dock}" data-slot="composer-dock" id="dock">
  <div class="{root}" data-slot="composer-root">
   <div class="{surface}" data-slot="composer-surface" id="surface" style="min-height:88px">
    <div data-slot="composer-rich-input" contenteditable="true" style="padding:14px 16px;outline:none"></div>
   </div>
  </div>
 </div>
</div>"""


PAGE = """<!doctype html><html class="{cls}"><head><meta charset="utf-8"><style>{app}</style>
<style id="hermes-desktop-custom-css">{layer}</style></head><body class="bg-background text-foreground" style="margin:0">{body}</body></html>"""

READ = """() => {
  const cs = (el, p) => getComputedStyle(el, p || null);
  const mark = document.querySelector('.wordmark'), name = document.getElementById('name'), line = document.getElementById('line');
  const twin = mark.querySelector('[aria-hidden]'), dock = document.getElementById('dock');
  const col = document.querySelector('[data-slot="aui_intro"] > div').getBoundingClientRect();
  const nr = name.getBoundingClientRect(), dr = dock.getBoundingClientRect(), sr = document.getElementById('surface').getBoundingClientRect();
  const m = cs(mark), c = cs(name, '::before'), l = cs(line), b = cs(dock, '::before');
  const cv = document.createElement('canvas').getContext('2d');
  const w = f => { cv.font = f; return cv.measureText('Hamburgefonstiv 0123').width; };
  return {
    fonts: { mono: w('40px "Red Hat Mono", serif') !== w('40px serif'), serif: w('40px "Scheherazade New", monospace') !== w('40px monospace') },
    mark: { fam: m.fontFamily, size: m.fontSize, lh: m.lineHeight, ls: m.letterSpacing, tt: m.textTransform, weight: m.fontWeight,
            color: m.color, blend: m.mixBlendMode, twin: cs(twin).display },
    axis: (nr.left + nr.right - parseFloat(cs(name).letterSpacing)) / 2 - (col.left + col.right) / 2,  // the ink, not the box: the last letter carries its tracking
    name: { left: nr.left, top: nr.top, right: nr.right, bottom: nr.bottom },
    cursor: { content: c.content, color: c.color, anim: c.animationName, dur: c.animationDuration, ease: c.animationTimingFunction,
              count: c.animationIterationCount, weight: c.fontWeight, fam: c.fontFamily },
    line: { fam: l.fontFamily, size: l.fontSize, lh: l.lineHeight, ls: l.letterSpacing, weight: l.fontWeight, color: l.color,
            wrap: l.textWrapStyle || l.textWrap },
    bar: { content: b.content, height: b.height, bg: b.backgroundImage.slice(0, 40), mask: (b.maskImage || b.webkitMaskImage || '').slice(0, 60) },
    dock: { left: dr.left, top: dr.top, right: dr.right, width: dr.width },
    edges: { bar: [dr.left + parseFloat(b.left), dr.right - parseFloat(b.right)], surface: [sr.left, sr.right] },
  };
}"""

SEEK = """t => { for (const a of document.getAnimations()) if (a.animationName === 'gs-cursor-blink') { a.pause(); a.currentTime = t; } }"""


def png(data: bytes):
    """A small PNG reader (8-bit RGB/RGBA, the five filters): rows of bytes, no dependency."""
    pos, idat = 8, b""
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat += chunk
    assert depth == 8 and ctype in (2, 6), (depth, ctype)
    bpp = 4 if ctype == 6 else 3
    raw, stride, rows, prev, i = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp), 0
    for _ in range(h):
        f, ln = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = ln[x - bpp] if x >= bpp else 0
            b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
            if f == 1:
                ln[x] = (ln[x] + a) & 255
            elif f == 2:
                ln[x] = (ln[x] + b) & 255
            elif f == 3:
                ln[x] = (ln[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                ln[x] = (ln[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(ln)
        prev = ln
    return w, h, [[tuple(r[x * bpp:x * bpp + 3]) for x in range(w)] for r in rows]


def hexrgb(hx: str) -> tuple:
    return tuple(int(hx[k:k + 2], 16) for k in (1, 3, 5))


def rgb_css(hx: str) -> str:
    r, g, b = hexrgb(hx)
    return f"rgb({r}, {g}, {b})"


def dist(a, b) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def tinted(p: tuple, ink: tuple, ground: tuple, floor: float = 0.18) -> bool:
    """p is the ink laid over the ground at some coverage: a 7px glyph is nearly all anti-aliased edge."""
    d = [i - g for i, g in zip(ink, ground)]
    k = max(range(3), key=lambda c: abs(d[c]))
    a = (p[k] - ground[k]) / d[k]
    return a >= floor and all(abs(ground[c] + a * d[c] - p[c]) <= 24 for c in range(3))


def lit(page, clip: dict, ink: tuple, ground: tuple) -> list:
    """Device-pixel columns (from the clip's left) holding the cursor's ink."""
    w, h, px = png(page.screenshot(clip=clip))
    return sorted({x for y in range(h) for x in range(w) if tinted(px[y][x], ink, ground)})


def runs(page, clip: dict, ink: tuple, ground: tuple):
    w, h, px = png(page.screenshot(clip=clip))
    score = [sum(dist(p, ink) <= 48 for p in row) for row in px]
    rows = [y for y, s in enumerate(score) if s > w // 5]
    if not rows:
        return [], 0, 0
    row = px[rows[0]]
    kind = ["on" if dist(p, ink) <= 48 else "off" if dist(p, ground) <= 48 else "mid" for p in row]
    out = []
    for k in kind:
        if out and out[-1][0] == k:
            out[-1][1] += 1
        else:
            out.append([k, 1])
    return out, len(rows), kind.count("mid")


def main() -> int:
    shots = pathlib.Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
    app = sorted(build.APP_CSS.glob("index-*.css"), key=lambda p: p.stat().st_mtime)[-1].read_text()
    canon = build.Canon(build.fetch(build.WEB + "system.css"))
    frame, raw = build.canon_frame(), canon.raw
    body = markup()
    period = [int(n * DPR) for n in frame["dash"]]
    half = float(re.match(r"([\d.]+)s", frame["blink"]).group(1)) * 1000 / 2
    fails = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1180, "height": 820}, device_scale_factor=DPR)
        for vname in build.VARIANTS:
            layer = (V2 / "out/desktop" / ("glass-stage.css" if vname == "literal" else "glass-stage-signal.css")).read_text()
            for gname, cls in (("stage", "dark"), ("paper", "")):
                v = lambda role: build.desk_value(canon, gname, role)  # noqa: E731
                page.emulate_media(reduced_motion="no-preference")
                page.set_content(PAGE.format(cls=cls, app=app, layer=layer, body=body), wait_until="load")
                page.evaluate("() => document.fonts.ready")
                page.evaluate("() => document.documentElement.style.setProperty('--composer-measured-height', document.getElementById('dock').offsetHeight + 'px')")
                page.wait_for_timeout(150)
                g = page.evaluate(READ)
                bad = []
                if not (g["fonts"]["mono"] and g["fonts"]["serif"]):
                    bad.append(f"fonts not installed: {g['fonts']}")
                mk, px7 = g["mark"], float(raw["fz-mono-6"].removesuffix("px"))
                want = {"size": f"{px7:g}px", "lh": f"{px7 * float(raw['lh-mono-6']):g}px", "tt": "uppercase", "weight": "400",
                        "color": rgb_css(v("ink")), "blend": "normal", "twin": "none"}
                bad += [f"masthead.{k} = {mk[k]} ≠ {x}" for k, x in want.items() if mk[k] != x]
                if not mk["fam"].startswith('"Red Hat Mono"'):
                    bad.append(f"masthead face = {mk['fam'][:40]}")
                if abs(float(mk["ls"].removesuffix("px")) - px7 * 0.3) > 0.01:
                    bad.append(f"masthead tracking {mk['ls']} ≠ +30%")
                if abs(g["axis"]) > 0.75:
                    bad.append(f"the name is {g['axis']:+.2f}px off the column's axis")
                cu = g["cursor"]
                if cu["content"] != '"_\u00a0"':
                    bad.append(f"cursor content = {cu['content']!r}")
                if cu["color"] != rgb_css(v("cursor")):
                    bad.append(f"cursor ink = {cu['color']} ≠ {v('cursor')}")
                if (cu["anim"], cu["dur"], cu["count"]) != ("gs-cursor-blink", "1.1s", "infinite") or cu["ease"] not in ("steps(2, start)", "steps(2, jump-start)"):
                    bad.append(f"cursor blink = {cu['anim']} {cu['dur']} {cu['ease']} {cu['count']} ≠ canon {frame['blink']}")
                ln, px14 = g["line"], float(raw["fz-body-1"].removesuffix("px"))
                want = {"size": f"{px14:g}px", "lh": f"{px14 * float(raw['lh-body-1']):g}px", "weight": "400",
                        "color": rgb_css(v("field")), "wrap": "balance"}
                bad += [f"line.{k} = {ln[k]} ≠ {x}" for k, x in want.items() if ln[k] != x]
                if not ln["fam"].startswith('"Scheherazade New"') or abs(float(ln["ls"].removesuffix("px")) - px14 * 0.05) > 0.01:
                    bad.append(f"line face/tracking = {ln['fam'][:24]} {ln['ls']}")
                # the blink, seeked: lit in the first half-period, dark in the second; the cursor hangs left of the name
                nm = g["name"]
                clip = {"x": nm["left"] - 40, "y": nm["top"] - 2, "width": nm["right"] - nm["left"] + 80, "height": nm["bottom"] - nm["top"] + 4}
                ink_c, gr = hexrgb(v("cursor")), hexrgb(v("ground"))
                page.evaluate(SEEK, half * 0.4)
                on = lit(page, clip, ink_c, gr)
                page.evaluate(SEEK, half * 1.5)
                off = lit(page, clip, ink_c, gr)
                if not on or off:
                    bad.append(f"blink: {len(on)} lit columns at {half * 0.4:.0f}ms, {len(off)} at {half * 1.5:.0f}ms")
                if on and max(on) >= 40 * DPR:
                    bad.append(f"the cursor does not hang: its ink reaches {max(on) / DPR - 40:+.1f}px into the name")
                if shots:
                    page.evaluate(SEEK, half * 0.4)
                    shots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shots / f"frame-{vname}-{gname}.png"))
                    page.screenshot(path=str(shots / f"frame-{vname}-{gname}-mast.png"),
                                    clip={"x": nm["left"] - 160, "y": nm["top"] - 40, "width": nm["right"] - nm["left"] + 320, "height": 120})
                # the bar: one device row, 16px above the composer, running the canon's dasharray
                dk, bar = g["dock"], g["bar"]
                if bar["content"] != '""' or bar["height"] != "1px" or "linear-gradient" not in bar["bg"] or "linear-gradient" not in bar["mask"]:
                    bad.append(f"bar = {bar}")
                eb, es = g["edges"]["bar"], g["edges"]["surface"]
                if abs(eb[0] - es[0]) > 0.5 or abs(eb[1] - es[1]) > 0.5:
                    bad.append(f"the bar spans {eb[0]:.1f}–{eb[1]:.1f}, the composer {es[0]:.1f}–{es[1]:.1f}")
                top = dk["top"] - float(raw["s-2"].removesuffix("px")) - 0.5
                rl, nrows, mids = runs(page, {"x": eb[0], "y": top - 3, "width": min(eb[1] - eb[0], 380), "height": 6.5},
                                       hexrgb(v("ink")), hexrgb(v("ground")))
                seq = [n for k, n in rl[:-1] if k != "mid"]          # the last run is cut by the clip
                expect = (period * (len(seq) // len(period) + 2))[:len(seq)]
                if nrows != 1 or seq != expect or mids:
                    bad.append(f"bar pixels: {nrows} rows, {mids} blurred, runs {seq[:10]} ≠ {expect[:10]}")
                if shots:
                    page.screenshot(path=str(shots / f"frame-{vname}-{gname}-bar.png"),
                                    clip={"x": dk["left"] - 24, "y": top - 40, "width": 300, "height": 90})
                    page.screenshot(path=str(shots / f"frame-{vname}-{gname}-bar-end.png"),
                                    clip={"x": dk["right"] - 276, "y": top - 40, "width": 300, "height": 90})
                # reduced motion: still, and lit
                page.emulate_media(reduced_motion="reduce")
                page.wait_for_timeout(60)
                rm = page.evaluate("() => getComputedStyle(document.getElementById('name'), '::before').animationName")
                still = lit(page, clip, ink_c, gr)
                if rm != "none" or not still:
                    bad.append(f"reduced motion: animation {rm}, lit {bool(still)}")
                # the frame leaves with the empty stage: popped out, then once the record starts
                page.evaluate("() => document.getElementById('dock').setAttribute('data-popped-out', '')")
                pop = page.evaluate("() => getComputedStyle(document.getElementById('dock'), '::before').content")
                page.evaluate("() => { document.getElementById('dock').removeAttribute('data-popped-out'); document.querySelector('.wordmark').remove(); }")
                gone = page.evaluate("() => getComputedStyle(document.getElementById('dock'), '::before').content")
                if pop != "none" or gone != "none":
                    bad.append(f"the bar outlives the empty stage: popped-out {pop!r}, record started {gone!r}")
                print(f"  {'✓' if not bad else '✗'} {vname:8} {gname:6} masthead m6 · axis {g['axis']:+.2f}px · "
                      f"cursor {v('cursor')} lit {len(on)}/{len(off)} · bar {nrows} row, runs {seq[:8]} · "
                      f"edges {eb[0] - es[0]:+.1f}/{eb[1] - es[1]:+.1f}px")
                fails += [f"    ✗ {vname} {gname} {x}" for x in bad]
        browser.close()
    print("\n".join(fails) if fails else "  the empty stage opens on the canon's cursor and closes on its braille bar")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
