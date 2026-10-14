#!/usr/bin/env python3
"""Census the type Hermes Desktop actually paints, in a running isolated instance (CDP :9333).

Seeds desk_thread's transcript through the app's own toChatMessages, then groups every visible
text-bearing element by its computed face, size, weight, tracking, leading and case.

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/type_census.py [--shot PATH] [--light]
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("desk_thread", HERE / "desk_thread.py")
assert spec and spec.loader
thread = importlib.util.module_from_spec(spec)
spec.loader.exec_module(thread)

SEED = """async ({rows, sessions}) => {
  const cm = await import('/src/lib/chat-messages/index.ts');
  const ss = await import('/src/store/session.ts');
  const msgs = cm.toChatMessages(rows);
  ss.setMessages(msgs);
  ss.$sessions.set(sessions);
  ss.$sessionsLoading.set(false);
  return msgs.map(m => m.role + ':' + m.parts.map(p => p.type).join('+'));
}"""

CENSUS = """() => {
  const groups = new Map();
  const slot = el => { const s = el.closest('[data-slot]'); return s ? s.dataset.slot : (el.closest('aside,nav,header,footer,main,form')?.tagName.toLowerCase() || '-'); };
  for (const el of document.querySelectorAll('body *')) {
    const own = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
    if (!own) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
    const key = [fam, cs.fontSize, cs.fontWeight, cs.letterSpacing, cs.lineHeight, cs.textTransform, cs.fontStyle].join(' | ');
    const g = groups.get(key) || { n: 0, slots: new Set(), samples: [] };
    g.n++; g.slots.add(slot(el));
    if (g.samples.length < 3) g.samples.push(own.slice(0, 38));
    groups.set(key, g);
  }
  return [...groups].sort((a, b) => b[1].n - a[1].n).map(([k, g]) => ({ k, n: g.n, slots: [...g.slots].slice(0, 5), samples: g.samples }));
}"""


def attach(pw, port: int = 9333):
    browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    page = next(p for c in browser.contexts for p in c.pages if ":5174" in p.url)
    return browser, page


def main() -> int:
    shot = pathlib.Path(sys.argv[sys.argv.index("--shot") + 1]) if "--shot" in sys.argv else None
    with sync_playwright() as pw:
        browser, page = attach(pw)
        page.evaluate("light => document.documentElement.classList.toggle('dark', !light)", "--light" in sys.argv)
        print("seeded:", page.evaluate(SEED, {"rows": thread.rows(), "sessions": thread.sessions()}))
        page.wait_for_timeout(1800)
        for g in page.evaluate(CENSUS):
            print(f"{g['n']:>4}  {g['k']:<92} {', '.join(g['slots'])[:70]:<70} {' / '.join(g['samples'])[:90]}")
        if shot:
            page.screenshot(path=str(shot))
            print("shot", shot)
        browser.close()  # detaches only; the instance keeps running
    return 0


if __name__ == "__main__":
    sys.exit(main())
