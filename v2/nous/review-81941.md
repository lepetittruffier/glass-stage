<!-- DRAFT — not posted. Target: https://github.com/NousResearch/hermes-agent/pull/81941 (comment, as lepetittruffier)
     Post with: gh pr comment 81941 --repo NousResearch/hermes-agent --body-file <this file, minus this header> -->

Ran this against a dual-ground skin I'm building (glass-stage): its base `colors` carry the inks but no `background`, and each ground lives in its own paired block. Two findings, both measured against current `main` (`c3a4bba74d`).

**1. The branch no longer builds on `main`.** `ensureContrast` and `mix` moved to `@hermes/shared/color`, and `readableOn` became `readableInk`, in 35022e02ed (Sep 13), after this branch's last push. As committed, `tsc` fails on the `./color` import, and every test in `skin.test.ts` fails with `mix is not a function`. Moving the import and renaming the call is the whole rebase. With that done, `tsc` and ESLint are clean and your 13 tests pass.

**2. The overlay for the base's own polarity is dropped.** With a dark base, the dark slot is `colors` as-is, so `dark_colors` never applies. With a light base, the same happens to `light_colors`. The TUI applies `dark_colors` on a dark terminal, so Desktop and the TUI disagree. Minimal repro:

```yaml
colors:       { status_bar_bg: "#272727", banner_text: "#ffffff" }
light_colors: { background: "#ffffff", banner_text: "#000000" }
dark_colors:  { background: "#000000" }
```

| skin | this branch (light / dark) | with the fix below |
|---|---|---|
| the repro | `#ffffff` / `#272727`: the dark slot falls back to `status_bar_bg` | `#ffffff` / `#000000` |
| `default` (stock) | `#f5f5f5` / `#1a1a2e` | unchanged |
| `teal-ocean` (your docs example) | `#f2faf8` / `#02181a` | unchanged |

**Suggested fix:** give each slot the base plus its own overlay. This also makes the polarity seed unnecessary, and with it the chrome-only fallback from the triage note:

```diff
-  // Dual-mode: the base palette's authored background decides polarity (mirror
-  // of the TUI's `skinIsLight`). The opposite mode is the base merged with the
-  // matching hand-tuned overlay; the authored mode is the base itself.
-  //
-  // A chrome-only base (no `background`/`status_bar_bg`) must fall back to the
-  // SAME foreground-luminance bucket `buildPalette` uses, or the polarity seed
-  // disagrees with the palette it derives: light text ⇒ dark canvas ⇒ the
-  // light_colors overlay belongs in the light slot.
-  const seededBg = pick(colors, ['background', 'status_bar_bg'], '#000000')
-  const foregroundSeed = pick(colors, ['ui_text', 'banner_text', 'status_bar_text'], seededBg ?? '#000000')
-  const baseDark = seededBg
-    ? luminance(seededBg) < 0.4
-    : (foregroundSeed ? luminance(foregroundSeed) > 0.5 : false)
-
-  const lightSource = baseDark ? { ...colors, ...(skin.light_colors ?? {}) } : colors
-  const darkSource = baseDark ? colors : { ...colors, ...(skin.dark_colors ?? {}) }
+  // Each slot is the base plus its own overlay — the TUI's rule, per polarity.
+  const lightSource = { ...colors, ...(skin.light_colors ?? {}) }
+  const darkSource = { ...colors, ...(skin.dark_colors ?? {}) }
```

These two tests pin the fix. The first fails on the branch and passes with the fix. With them, your 13 pass too (15/15):

```ts
it('applies the overlay for the base polarity too', () => {
  const theme = skinToDesktopTheme({
    name: 'grounds',
    colors: { status_bar_bg: '#272727', banner_text: '#ffffff' },
    light_colors: { background: '#ffffff', banner_text: '#000000' },
    dark_colors: { background: '#000000' }
  })!

  expect(theme.colors.background).toBe(normalizeHex('#ffffff'))
  expect(theme.darkColors!.background).toBe(normalizeHex('#000000'))
})

it('still toggles a skin that authors its background (the docs example)', () => {
  const theme = skinToDesktopTheme({
    name: 'teal-ocean',
    colors: { background: '#02181A', ui_accent: '#F6A278', banner_text: '#C8F5F2' },
    light_colors: { background: '#F2FAF8', ui_accent: '#B22E12', banner_text: '#051C1C' }
  })!

  expect(theme.colors.background).toBe(normalizeHex('#F2FAF8'))
  expect(theme.darkColors!.background).toBe(normalizeHex('#02181A'))
})
```

One question for maintainers: with an authored `background` in `colors`, the TUI keeps that polarity (#69671), while this toggles it on Desktop (`teal-ocean`). That seems right for a surface with an explicit Light/Dark switch, but it may be worth a line in the docs.

Happy to push a rebased branch with both changes if that's easier.
