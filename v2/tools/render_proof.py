"""Render proof for the GLASS STAGE v2 workshop — measurement, not approval."""
import json
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

PAGE = pathlib.Path(__file__).resolve().parents[1] / "out" / "workshop" / "index.html"
SHOTS = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "glass-stage-v2-shots"
SHOTS.mkdir(parents=True, exist_ok=True)

PROBE = """() => {
  const q = s => document.querySelector(s);
  const vis = sel => [...document.querySelectorAll(sel)].filter(e => e.offsetParent !== null).length;
  return {
    fonts: { mono: document.fonts.check('14px "Red Hat Mono"'), monoItalic: document.fonts.check('italic 14px "Red Hat Mono"'),
             serif: document.fonts.check('14px "Scheherazade New"') },
    overflowX: document.documentElement.scrollWidth - window.innerWidth,
    height: document.documentElement.scrollHeight,
    glassTier: document.documentElement.getAttribute('data-glassci-tier'),
    glassPanes: document.querySelectorAll('.glassci').length,
    styles: [...document.styleSheets].filter(s => (s.href || '').includes('intelligencematters')).map(s => { try { return s.cssRules.length } catch (e) { return 'cors' } }),
    visibleLiteral: vis('.ws-v-literal'), visibleSignal: vis('.ws-v-signal'),
    bodyFont: getComputedStyle(q('.hub-body .serif-body-1')).fontFamily,
    doorFont: getComputedStyle(q('.ws-door')).fontFamily + ' ' + getComputedStyle(q('.ws-door')).fontSize,
    stageText: getComputedStyle(q('.ws-desk[data-ground="stage"] .hub-brand-name')).color,
    paperText: getComputedStyle(q('.ws-desk[data-ground="paper"] .hub-brand-name')).color,
    tileWidths: [...document.querySelectorAll('#ghostty .container-tile')].map(e => Math.round(e.getBoundingClientRect().width)),
    overflowing: [...document.querySelectorAll('.container-tile')].flatMap(t => { const r = t.getBoundingClientRect();
      return [...t.querySelectorAll('*')].filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && (b.right > r.right + 1 || b.left < r.left - 1); })
        .filter(e => !e.closest('.glassci__rim, .glassci__defs'))
        // inside a scroll/clip container (the canon .spec-rail is overflow-x:auto) is not an escape
        .filter(e => { for (let a = e.parentElement; a && a !== t; a = a.parentElement) { if (getComputedStyle(a).overflowX !== 'visible') return false; } return true; })
        .slice(0, 2)
        .map(e => ((e.closest('section') || {}).id || '?') + ':' + (typeof e.className === 'string' && e.className ? e.className : e.tagName) + ' +' + Math.round(e.getBoundingClientRect().right - r.right) + ' «' + (e.textContent || '').trim().slice(0, 32) + '»'); }).slice(0, 12),
    railsScrolling: [...document.querySelectorAll('.spec-rail')].filter(e => e.scrollWidth > e.clientWidth + 1).length,
    doorRects: (() => { const s = q('#desktop').getBoundingClientRect(); return [...document.querySelectorAll('.ws-door')].map(d => { const r = d.getBoundingClientRect(); return [Math.round(r.left - s.left), Math.round(r.top - s.top), Math.round(r.width), Math.round(r.height)]; }); })(),
    doorOverGate: (() => { const g = q('.ws-desk[data-ground="paper"] .hub-approval').getBoundingClientRect(), d = q('.ws-desk[data-ground="paper"] .ws-door').getBoundingClientRect(); return Math.round(d.top - g.bottom); })(),
    doorOverReceipt: (() => { const t = q('.ws-desk[data-ground="paper"] .term').getBoundingClientRect(), d = q('.ws-desk[data-ground="paper"] .ws-door').getBoundingClientRect(); return Math.round(t.bottom - d.top); })(),
  };
}"""

out = {}
with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome", headless=True)
    except Exception:  # noqa: BLE001
        browser = p.chromium.launch(headless=True)
    errors = []
    for width in (1440, 400):
        page = browser.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2 if width > 400 else 1)
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(PAGE.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(1200)
        out[str(width)] = page.evaluate(PROBE)
        if width == 1440:
            # capture-only: the sticky masthead rides along into element shots; pin it for the camera
            page.add_style_tag(content=".epoq-header{position:static!important}")
            for sid in ("law", "grounds", "ghostty", "tui", "desktop", "rulings"):
                page.locator(f"#{sid}").screenshot(path=str(SHOTS / f"{sid}.png"))
            page.click('[data-set-variant="signal"]')
            page.wait_for_timeout(200)
            out["afterSwitch"] = page.evaluate("() => ({literal: [...document.querySelectorAll('.ws-v-literal')].filter(e => e.offsetParent).length, signal: [...document.querySelectorAll('.ws-v-signal')].filter(e => e.offsetParent).length, variant: document.body.dataset.variant})")
            page.locator("#ghostty").screenshot(path=str(SHOTS / "ghostty-signal.png"))
            page.locator("#tui").screenshot(path=str(SHOTS / "tui-signal.png"))
        else:
            page.screenshot(path=str(SHOTS / "narrow-full.png"), full_page=True)
        page.close()
    browser.close()
out["errors"] = errors[:12]
out["shots"] = str(SHOTS)
print(json.dumps(out, indent=1))
sys.exit(0)
