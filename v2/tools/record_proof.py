#!/usr/bin/env python3
"""Prove the record layer — code, diffs, counts, meta — in Hermes Desktop's own compiled stylesheet.

Real inputs only: the installed app's compiled renderer CSS (apps/desktop/dist/assets/index-*.css),
real Shiki output from the app's own node_modules in the app's own options (chat fences and diffs in
github-dark-dimmed / github-light-default with defaultColor light-dark(); Streamdown fences in
github-dark / github-light as React custom properties; diff tokens as React inline rgb()), and markup
carrying the component class strings from the app's source. Every token the layer restates is first
painted magenta inline, the way applyTheme paints, so each match below is the layer's doing.

Also re-derives the colour table: every token colour the five GitHub themes paint must sit in
build.SHIKI_GROUPS, or the proof fails (a theme update would otherwise leak a hue through).

    /Library/Developer/CommandLineTools/usr/bin/python3 v2/tools/record_proof.py [--shots DIR]
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

V2 = pathlib.Path(__file__).resolve().parents[1]
DESKTOP = pathlib.Path.home() / ".hermes/hermes-agent/apps/desktop"
spec = importlib.util.spec_from_file_location("build", V2 / "build.py")
assert spec and spec.loader
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

CODE = '''import re  # blank strings and comments
from pathlib import Path

def strip(text: str, n: int = 3) -> str | None:
    """Keep the shape, drop the content."""
    return re.sub(r"[^\\n]", " ", text) if n > 2 else None
'''
DIFF = [("context", "def strip(text: str) -> str:"), ("remove", '    return text.replace("#", "")'),
        ("add", '    return re.sub(r"#.*", "", text)  # comments go'), ("context", "")]

NODE = r"""
import { codeToHtml, codeToTokens } from 'shiki'
const code = process.env.CODE, diff = JSON.parse(process.env.DIFF)
const fence = await codeToHtml(code, { lang: 'python', themes: { dark: 'github-dark-dimmed', light: 'github-light-default' }, defaultColor: 'light-dark()' })
const sd = await codeToTokens(code, { lang: 'python', themes: { light: 'github-light', dark: 'github-dark' }, defaultColor: false })
const stream = sd.tokens.map(line => line.map(t => ({ content: t.content, light: t.htmlStyle?.['--shiki-light'], dark: t.htmlStyle?.['--shiki-dark'] })))
const diffs = {}
for (const theme of ['github-dark-dimmed', 'github-light-default']) {
  const r = await codeToTokens(diff.map(d => d[1]).join('\n'), { lang: 'python', theme })
  diffs[theme] = r.tokens.map(line => line.map(t => ({ content: t.content, color: t.color })))
}
const themes = {}
for (const name of ['github-dark-dimmed', 'github-dark-default', 'github-dark', 'github-light-default', 'github-light']) {
  const t = (await import(`@shikijs/themes/${name}`)).default
  themes[name] = [...new Set([t.fg, ...(t.tokenColors || []).map(c => c.settings?.foreground)].filter(Boolean).map(c => c.toUpperCase()))]
}
console.log(JSON.stringify({ fence, stream, diffs, themes }))
"""

DIFF_BOX = ("-mx-1.5 -mb-1.5 max-h-[12rem] max-w-none min-w-0 overflow-auto overscroll-x-contain "
            "overscroll-y-auto font-mono text-[0.7rem] leading-relaxed text-(--ui-text-secondary)")
LINE = "block min-w-max whitespace-pre border-l-2 px-2.5 py-px"
TINT = {"add": "border-(--ui-diff-add-border) bg-(--ui-diff-add-background)", "context": "border-transparent",
        "remove": "border-(--ui-diff-remove-border) bg-(--ui-diff-remove-background)"}
SEG = ("flex min-w-0 items-center justify-center gap-1 rounded-[3px] px-2.5 py-0.5 text-[0.6875rem] "
       "font-medium whitespace-nowrap transition-colors")

PAGE = """<!doctype html><html class="dark"><head><meta charset="utf-8">
<style id="app-css">{css}</style><style>body{{padding:20px;width:640px}} .card{{border:1px solid var(--dt-border);
border-radius:5px;padding:6px;margin:0 0 14px}} .row{{display:flex;gap:8px;align-items:center;margin:0 0 6px}}</style>
<style id="hermes-desktop-custom-css">{layer}</style></head>
<body class="bg-background text-foreground font-sans text-[13px]">
<div class="row"><span class="tool-memory-legendary-glyph">✦</span>
  <span class="tool-memory-legendary-title shrink-0 text-transparent" id="legend">Self-improvement review</span>
  <span class="tool-memory-legendary-meta" id="legend-meta">Skill 'hermes-agent' patched</span></div>
<p class="text-(--ui-text-tertiary) text-[0.75rem]" id="meta">Ran 4 commands · 242 stdout_bytes</p>
<div class="card"><div class="row"><span class="text-(--ui-text-primary)">install.sh</span>
  <span class="flex shrink-0 items-center gap-1 font-mono text-[0.625rem] tabular-nums">
   <span class="text-emerald-600 dark:text-emerald-400" id="hdr-add">+78</span>
   <span class="text-rose-600 dark:text-rose-400" id="hdr-rem">−3</span></span></div>
  <pre class="{box}" data-slot="diff-lines" id="diff"></pre>
  <div class="mb-1 text-[0.65rem] font-medium uppercase tracking-[0.08em] text-(--ui-text-tertiary)" id="label">› Tool payload</div></div>
<div class="card aui-shiki" id="fence">{fence}</div>
<div class="card"><pre class="font-mono text-[0.7rem]" id="stream"></pre></div>
<div class="card" data-slot="aui_changed-files"><div class="row"><span class="min-w-0 flex-1 text-(--ui-text-primary)">4 files changed</span>
  <span class="text-(--ui-text-tertiary)">Review</span></div>
  <div class="row"><span class="min-w-0 flex-1 truncate text-(--ui-text-secondary)">test_delta.py</span>
   <span class="flex shrink-0 items-center gap-1 tabular-nums"><span class="text-(--ui-green)" id="dc-add">+1</span>
   <span class="text-(--ui-red)" id="dc-rem">−1</span></span></div></div>
<div class="inline-grid w-fit auto-cols-fr grid-flow-col gap-0.5 rounded-[5px] bg-(--ui-bg-tertiary) p-0.5">
  <button class="{seg} bg-background text-foreground shadow-sm" id="seg-on">Uncommitted</button>
  <button class="{seg} text-muted-foreground hover:text-foreground" id="seg-off">Last turn</button></div>
</body></html>"""

FILL = """({diff, diffs, stream, tokens, lineBase, tint}) => {
  const root = document.documentElement;
  for (const k of tokens) root.style.setProperty(k, k.includes('mix') ? '0%' : k === '--noise-opacity-mul' ? '1'
                                                : k.includes('font') ? 'serif' : '#ff00ff');
  const dark = root.classList.contains('dark');
  const box = document.getElementById('diff'); box.textContent = '';
  const lines = diffs[dark ? 'github-dark-dimmed' : 'github-light-default'];
  diff.forEach(([kind], i) => {
    const line = document.createElement('span');
    line.className = `${lineBase} ${tint[kind]}`; line.dataset.kind = kind;
    for (const t of lines[i] || []) {                      // React writes style.color: rgb(…)
      const s = document.createElement('span'); s.textContent = t.content; s.style.color = t.color; line.append(s);
    }
    if (!line.textContent) line.textContent = ' ';
    box.append(line);
  });
  const sd = document.getElementById('stream'); sd.textContent = '';
  stream.forEach(row => {                                   // Streamdown: --sdm-c + --shiki-dark as React props
    const line = document.createElement('span'); line.className = 'block';
    for (const t of row) {
      const s = document.createElement('span');
      s.className = 'text-[var(--sdm-c,inherit)] dark:text-[var(--shiki-dark,var(--sdm-c,inherit))]';
      if (t.light) s.style.setProperty('--sdm-c', t.light);
      if (t.dark) s.style.setProperty('--shiki-dark', t.dark);
      s.textContent = t.content; line.append(s);
    }
    sd.append(line);
  });
}"""

READ = """() => {
  const cs = (el, p) => getComputedStyle(el)[p];
  const q = s => document.querySelector(s);
  const leaves = root => [...root.querySelectorAll('span')].filter(s => s.children.length === 0);
  const byText = (root, text) => leaves(root).find(s => s.textContent.trim() === text)
                              || leaves(root).find(s => s.textContent.includes(text));
  const fence = q('#fence'), stream = q('#stream'), diff = q('#diff');
  const add = diff.querySelector('[data-kind=add]'), rem = diff.querySelector('[data-kind=remove]');
  return {
    fence_keyword: cs(byText(fence, 'import'), 'color'), fence_comment: cs(byText(fence, 'blank strings'), 'color'),
    fence_string: cs(byText(fence, 'Keep the shape'), 'color'),
    fence_function: cs(byText(fence, 'strip'), 'color'), fence_ground: cs(q('#fence pre'), 'backgroundColor'),
    stream_keyword: cs(byText(stream, 'import'), 'color'), stream_comment: cs(byText(stream, 'blank strings'), 'color'),
    diff_keyword: cs(byText(add, 'return'), 'color'), diff_add_ground: cs(add, 'backgroundColor'),
    diff_add_line: cs(add, 'textDecorationLine'), diff_remove_line: cs(rem, 'textDecorationLine'),
    diff_add_rule: cs(add, 'borderLeftColor'), diff_hair: cs(add, 'backgroundImage'), diff_ul: cs(add, 'textUnderlinePosition'),
    diff_column: cs(add, 'borderLeftWidth') === cs(diff.querySelector('[data-kind=context]'), 'borderLeftWidth'),
    hdr_add: cs(q('#hdr-add'), 'color'), hdr_rem: cs(q('#hdr-rem'), 'color'),
    dc_add: cs(q('#dc-add'), 'color'), dc_rem: cs(q('#dc-rem'), 'color'),
    legend: cs(q('#legend'), 'backgroundImage'), legend_meta: cs(q('#legend-meta'), 'color'),
    meta: cs(q('#meta'), 'color'), label: cs(q('#label'), 'color'), seg_off: cs(q('#seg-off'), 'color'),
  };
}"""


def rgb(hx: str) -> str:
    return "rgb(%d, %d, %d)" % (int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16))


def expected(canon, gname: str, i: int) -> dict:
    v = lambda role: rgb(build.desk_value(canon, gname, role))  # noqa: E731
    syn = lambda cat: v(build.SYNTAX[cat][i])  # noqa: E731
    add, rem = (build.DESK_KEYS[k][i] for k in ("--ui-diff-add-foreground", "--ui-diff-remove-foreground"))
    ex = {"fence_keyword": syn("keyword"), "fence_comment": syn("comment"), "fence_string": syn("string"),
          "fence_function": syn("function"), "fence_ground": "rgba(0, 0, 0, 0)",
          "stream_keyword": syn("keyword"), "stream_comment": syn("comment"),
          "diff_keyword": syn("keyword"), "diff_add_ground": "rgba(0, 0, 0, 0)",
          "diff_add_rule": v(build.DESK_KEYS["--ui-diff-add-border"][i]), "diff_column": True,
          "hdr_add": v(add), "hdr_rem": v(rem), "dc_add": v(add), "dc_rem": v(rem),
          "legend_meta": v("field"), "meta": v("field"), "label": v("field"), "seg_off": v("field")}
    if i == 0:  # LITERAL · .hub-diff
        ink = v("ink")
        ex |= {"diff_add_line": "underline", "diff_remove_line": "line-through", "diff_add_rule": "rgba(0, 0, 0, 0)",
               "diff_hair": "none", "diff_ul": "under"}
    return ex


def main() -> int:
    shots = pathlib.Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
    css = sorted((DESKTOP / "dist/assets").glob("index-*.css"), key=lambda p: p.stat().st_mtime)[-1]
    app_css = css.read_text()  # inlined: Chrome will not load a file:// sheet into an about:blank page
    env = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "HOME": str(pathlib.Path.home()),
           "CODE": CODE, "DIFF": json.dumps(DIFF)}
    run = subprocess.run(["node", "--input-type=module", "-e", NODE], cwd=DESKTOP, env=env,
                         capture_output=True, text=True, check=True)
    fx = json.loads(run.stdout)

    # the colour table must cover every token colour the themes paint
    groups = {g: {h for cat in build.SHIKI_GROUPS.values() for h in cat[0 if g == "stage" else 1]}
              for g in ("stage", "paper")}
    leaks = [f"{t} {c}" for t, cs in fx["themes"].items() for c in cs
             if c not in groups["paper" if "light" in t else "stage"]]
    canon = build.Canon(build.fetch(build.WEB + "system.css"))
    fails = [f"  ✗ table   {leak} paints outside SHIKI_GROUPS" for leak in leaks]
    print(f"  {'✓' if not leaks else '✗'} table   {sum(map(len, fx['themes'].values()))} theme colours · "
          f"{'every one in SHIKI_GROUPS' if not leaks else f'{len(leaks)} outside'}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(device_scale_factor=2, viewport={"width": 680, "height": 900})
        for i, vname in enumerate(build.VARIANTS):
            name = "glass-stage" if vname == "literal" else "glass-stage-signal"
            layer = (V2 / "out/desktop" / f"{name}.css").read_text()
            tokens = sorted(set(build.DESK_KEYS) | set(build.DESK_FLAT))
            for gname, cls in (("stage", "dark"), ("paper", "")):
                html = PAGE.format(css=app_css, layer=layer, box=DIFF_BOX, seg=SEG, fence=fx["fence"])
                page.set_content(html.replace('<html class="dark">', f'<html class="{cls}">'), wait_until="load")
                page.evaluate(FILL, {"diff": DIFF, "diffs": fx["diffs"], "stream": fx["stream"],
                                     "tokens": tokens, "lineBase": LINE, "tint": TINT})
                got, want = page.evaluate(READ), expected(canon, gname, i)
                bad = [f"{k}: {got.get(k)} ≠ {w}" for k, w in want.items() if got.get(k) != w]
                stops = set(re.findall(r"rgba?\([^)]*\)", got["legend"]))
                if stops != {rgb(build.desk_value(canon, gname, build.DESK_KEYS["--tool-memory-legendary-from"][i]))}:
                    bad.append(f"legend stops {sorted(stops)}")
                mark = "✓" if not bad else "✗"
                print(f"  {mark} {vname:8} {gname:6} {len(want) + 1 - len(bad)}/{len(want) + 1} probes")
                fails += [f"  ✗ {vname} {gname} {b}" for b in bad]
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shots / f"record-{vname}-{gname}.png"), full_page=True)
        browser.close()
    print("\n".join(fails) if fails else "  every probe lands in the app's own compiled stylesheet")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
