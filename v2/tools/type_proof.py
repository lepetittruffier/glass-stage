#!/usr/bin/env python3
"""Prove the Desktop type in the real app: an isolated Hermes Desktop (perf:serve, CDP :9333).

Seeds desk_thread's transcript through the app's own toChatMessages, puts the built layer into the
app's own customCSS slot (#hermes-desktop-custom-css, where the backend's skin lands), then on both
grounds reads each surface's computed face, size, tracking, leading and case against the canon
tokens, and clip-tests every text box: the real baseline (an inline probe) plus the face's ink
(measureText) must sit inside its clipping box — Scheherazade New's metrics are tall.

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/type_proof.py [--shots DIR] [--variant signal]
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

from playwright.sync_api import sync_playwright

V2 = pathlib.Path(__file__).resolve().parents[1]


def load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = load("build", V2 / "build.py")
census = load("type_census", V2 / "tools" / "type_census.py")

READ = """() => {
  const leaf = t => [...document.querySelectorAll('body *')].find(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().startsWith(t)));
  const st = (el, pseudo) => { if (!el) return null; const c = getComputedStyle(el, pseudo || null);
    return { fam: c.fontFamily.split(',')[0].replace(/["']/g, '').trim(), size: parseFloat(c.fontSize), weight: c.fontWeight,
             ls: c.letterSpacing === 'normal' ? 0 : parseFloat(c.letterSpacing), lh: c.lineHeight === 'normal' ? 'normal' : parseFloat(c.lineHeight),
             tt: c.textTransform, style: c.fontStyle, content: c.content, color: c.color, mt: parseFloat(c.marginTop), mb: parseFloat(c.marginBottom) }; };
  const rec = document.querySelector('[data-slot="aui_assistant-message-content"]');
  const scale = parseFloat(getComputedStyle(rec).getPropertyValue('--chat-text-scale')) || 1;
  const li = leaf('Raw Tailwind colours');
  const cv = document.createElement('canvas').getContext('2d');
  const w = f => { cv.font = f; return cv.measureText('Hamburgefonstiv 0123').width; };
  let heavy = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.bottom < 0 || r.top > innerHeight) continue;
    if (getComputedStyle(el).fontWeight !== '400') heavy++;
  }
  return { scale, heavy,
    serif_loaded: w('40px "Scheherazade New", monospace') !== w('40px monospace'),
    mono_loaded: w('40px "Red Hat Mono", serif') !== w('40px serif'),
    layer: (document.getElementById('hermes-desktop-custom-css') || {}).textContent?.includes('the type —') || false,
    p: st(leaf('The record sets in')), h2: st(leaf('The type')), h3: st(leaf('Three voices')),
    strong: st(leaf('How it was checked')), td_bold: st(leaf('Syntax')), th: st(leaf('what you flagged')),
    quote: st(leaf('The canon already drew')), dash: st(li ? li.closest('li') : null, '::before'),
    user: st(leaf('sorry i last')), code: st(leaf('9b7b95a')),
    group: st(leaf('Pinned')), bucket: st(leaf('Yesterday')), tab: st(leaf('Sessions')),
    row: st(leaf('login to cortex')), nav: st(leaf('Capabilities')), time: st(leaf('1d')),
    bar: st(leaf('Backend')), tool: st(leaf('Ran')),
    pill: st([...document.querySelectorAll('[data-slot="composer-surface"] [data-slot="tooltip-trigger"] *')]
             .find(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))),
    door: st(document.querySelector('[data-slot="composer-rich-input"]')),
    kbd: st(document.querySelector('kbd')) };
}"""

CLIP = """() => {
  const out = [], cv = document.createElement('canvas').getContext('2d');
  for (const el of document.querySelectorAll('body *')) {
    const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim());
    if (!own.length) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const lh = cs.lineHeight === 'normal' ? 1.3 * parseFloat(cs.fontSize) : parseFloat(cs.lineHeight);
    let box = null;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const o = getComputedStyle(n);
      if (o.overflowY !== 'visible' || o.overflowX !== 'visible') { box = n; break; }
    }
    if (!box) continue;
    const c = box.getBoundingClientRect();
    if (c.height > 3 * lh || c.height < 4) continue;       // a scroller or a 1px helper, not a line box
    const last = own[own.length - 1];
    const probe = document.createElement('span');
    probe.style.cssText = 'display:inline-block;width:0;height:0;padding:0;margin:0;border:0;vertical-align:baseline';
    last.parentNode.insertBefore(probe, last.nextSibling);
    const base = probe.getBoundingClientRect().top; probe.remove();
    cv.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const raw = last.textContent.trim();                   // measure what is drawn, case included
    const m = cv.measureText(cs.textTransform === 'uppercase' ? raw.toUpperCase() : cs.textTransform === 'lowercase' ? raw.toLowerCase() : raw);
    const top = (base - m.actualBoundingBoxAscent) - c.top, bottom = c.bottom - (base + m.actualBoundingBoxDescent);
    if (top < -0.5 || bottom < -0.5) {
      const s = el.closest('[data-slot]');
      out.push({ text: last.textContent.trim().slice(0, 28), slot: s ? s.dataset.slot : '-', top: +top.toFixed(1), bottom: +bottom.toFixed(1),
                 fam: cs.fontFamily.split(',')[0].replace(/["']/g, ''), size: cs.fontSize, box: Math.round(c.height) });
    }
  }
  return out;
}"""


CONN = """async () => {
  const ss = await import('/src/store/session.ts');
  const c = ss.$connection.get() || {};
  return Object.fromEntries(Object.entries(c).filter(([k]) => !/token|key|secret|auth|pass/i.test(k))
    .map(([k, v]) => [k, typeof v === 'string' ? v.replace(/[?#].*$/, '?…').slice(0, 70) : typeof v]));
}"""


def near(a, b, tol=0.06):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def expect(canon, got: dict, gname: str) -> list:
    raw = canon.raw
    px = lambda n: float(raw[n].removesuffix("px"))  # noqa: E731
    em = lambda n: float(raw[n].removesuffix("em"))  # noqa: E731
    serif = raw["font-serif"].split(",")[0].strip('" ')
    mono = raw["font-mono"].split(",")[0].strip('" ')
    voice = {  # the specimen's three: face, size, leading, tracking
        "body": dict(fam=serif, size=px("fz-body-1"), lh=px("fz-body-1") * float(raw["lh-body-1"]), ls=px("fz-body-1") * em("track-body-1")),
        "pills": dict(fam=serif, size=px("fz-serif-8"), lh=px("fz-serif-8") * float(raw["lh-serif-8"]), ls=px("fz-serif-8") * em("track-caps"), tt="uppercase"),
        "code": dict(fam=mono, size=px("fz-mono-6"), lh=px("fz-mono-6") * float(raw["lh-mono-6"]), ls=px("fz-mono-6") * em("track-code")),
    }
    want = {"p": "body", "user": "body", "row": "body", "nav": "body", "door": "body",
            "h2": "pills", "h3": "pills", "strong": "pills", "td_bold": "pills", "pill": "pills", "tab": "pills",
            "code": "code", "th": "code", "group": "code", "bucket": "code", "time": "code", "bar": "code", "kbd": "code", "tool": "code"}
    caps = {"th", "group", "bucket", "bar"}
    bad = []

    def chk(name, **w):
        g = got.get(name)
        if not g:
            bad.append(f"{name}: not found")
            return
        for k, v in w.items():
            ok = near(g[k], v) if isinstance(v, (int, float)) and not isinstance(v, bool) else g[k] == v
            if not ok:
                bad.append(f"{name}.{k} = {g[k]} ≠ {round(v, 3) if isinstance(v, float) else v}")

    if not got["layer"]:
        bad.append("the type layer is not in the app's customCSS slot")
    if not got["serif_loaded"]:
        bad.append("Scheherazade New is not installed: the record falls to Georgia")
    if not got["mono_loaded"]:
        bad.append("Red Hat Mono is not installed")
    if got["heavy"]:
        bad.append(f"{got['heavy']} visible text boxes above weight 400 (E1)")
    for name, v in want.items():
        w = {k: x for k, x in voice[v].items() if not (name in ("user", "tool", "time", "kbd") and k in ("lh",))}
        chk(name, **w, **({"tt": "uppercase"} if name in caps else {}), weight="400")
    for k in ("code", "tool", "time"):
        chk(k, tt="none")                                  # the program keeps its case
    chk("quote", style="normal")
    chk("dash", content='"\u2014"')
    chk("h2", mt=px("s-3"), mb=px("s-1"))
    chk("p", mt=0, mb=px("s-2"))
    ink = build.rgb_of(build.desk_value(canon, gname, "ink"))
    for k in ("group", "bucket", "time"):
        chk(k, color=ink)
    return bad


def main() -> int:
    shots = pathlib.Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
    vname = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "literal"
    css = (V2 / "out" / "desktop" / ("glass-stage.css" if vname == "literal" else "glass-stage-signal.css")).read_text()
    canon = build.Canon(build.fetch(build.WEB + "system.css"))
    fails = []
    with sync_playwright() as pw:
        browser, page = census.attach(pw)
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 1100, "deviceScaleFactor": 2, "mobile": False})
        print("  probe connection:", page.evaluate(CONN))
        page.evaluate("() => { location.hash = '#/'; }")          # a new chat: no stored session re-hydrates over the seed
        page.wait_for_timeout(1500)
        page.evaluate(census.SEED, {"rows": census.thread.rows(), "sessions": census.thread.sessions()})
        page.wait_for_timeout(1200)
        page.evaluate("() => { const v = document.querySelector('[data-slot=aui_thread-viewport]'); if (v) v.scrollTop = v.scrollHeight; }")
        page.evaluate("""css => { let s = document.getElementById('hermes-desktop-custom-css');
                         if (!s) { s = document.createElement('style'); s.id = 'hermes-desktop-custom-css'; document.head.append(s); }
                         s.textContent = css; }""", css)
        for gname, dark in (("stage", True), ("paper", False)):
            page.evaluate("d => document.documentElement.classList.toggle('dark', d)", dark)
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(900)
            page.evaluate("""css => { document.getElementById('hermes-desktop-custom-css').textContent = css; }""", css)
            page.wait_for_timeout(300)
            got = page.evaluate(READ)
            bad = expect(canon, got, gname)
            clips = page.evaluate(CLIP)
            print(f"  {'✓' if not bad else '✗'} {vname} {gname}: {len(bad)} surface misses · "
                  f"record {got['p']['size'] if got['p'] else '?'}px at scale {got['scale']} · weights>400: {got['heavy']} · clipped boxes: {len(clips)}")
            fails += [f"    ✗ {gname} {b}" for b in bad]
            fails += [f"    ✗ {gname} clip {c}" for c in clips]
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots / f"type-{vname}-{gname}.png"))
                vp = page.evaluate("() => { const r = document.querySelector('[data-slot=\"aui_thread-viewport\"]').getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; }")
                page.screenshot(path=str(shots / f"type-{vname}-{gname}-record.png"), clip=vp)
        page.evaluate("() => document.documentElement.classList.add('dark')")
        cdp.send("Emulation.clearDeviceMetricsOverride")
        browser.close()
    print("\n".join(fails) if fails else "  every surface wears its canon voice, and no box clips its ink")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
