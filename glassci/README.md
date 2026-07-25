```
   ┌──────────────────────────────────────────────┐
   │  g l a s s c i                               │
   │  glass with nothing to refract but characters│
   └──────────────────────────────────────────────┘
```

# glassci

A liquid-glass material for the web that assumes the thing behind it is a
**monospace field**, not a photograph. Two files, no dependencies, no WebGL,
no canvas, no build step. MIT. Take it.

Part of [THE GLASS STAGE](../README.md).

---

## Why it looks different

Every other liquid-glass library is the same object: a milky white lens over a
colourful wallpaper, with a background-picker and a drag-me blob. They are all
recreating the same iOS demo, and most of them ship a megabyte to do it.

glassci starts from a different substrate and ends up somewhere else.

**1 · The lens has nothing to refract but characters.**
A photograph *hides* distortion — you cannot tell a bent JPEG from an unbent
one. A monospace grid **measures** it. Put a lens over box-drawing characters
and the bend becomes legible, because the thing behind it is a ruler. The grid
is not decoration under the glass; it is the instrument that proves the glass
is there.

**2 · Lit from inside.**
Apple's glass is lit by its environment. glassci is lit by its contents — the
characters are the phosphor, and the light *leaves* the tile. Emission, not
reflection.

**3 · Black glass.**
The pane is dark. The specular rim is the only white on it.

**4 · The prism obeys the palette.**
Ordinary chromatic aberration splits into red/green/blue because that is what
light does. glassci splits into inks **you name**, and the default set contains
no red at all. A refractive material that legislates its own dispersion is the
point, not a limitation — this is the one thing here you will not find in any
other implementation, because it requires having a palette worth obeying.

---

## Use it

```html
<link rel="stylesheet" href="glassci/glassci.css">
<script src="glassci/glassci.js"></script>

<div class="glassci" data-glassci>
  <p>anything</p>
</div>
```

`[data-glassci]` elements wire themselves at load. Or drive it yourself:

```js
glassci('.panel', { radius: 20, dispersion: 4 });
const g = glassci(el, { emission: '#6F75D7' });
g.set({ strength: 30 });   // retune live
g.destroy();               // put everything back
```

Every option is also a `data-glassci-*` attribute, which wins over the argument.

### Options

| option | default | what it is |
|---|---|---|
| `radius` | `0.28` | corner size. `<1` = fraction of the short side, `>=1` = px |
| `n` | `4` | superellipse exponent. `2` = circle / rounded rect, `4` = squircle, `8` = nearly square |
| `depth` | `18` | px — thickness of the refracting edge band |
| `strength` | `24` | px — how hard that band bends what is behind it |
| `dispersion` | `3` | px — ray divergence between inks. `0` = achromatic |
| `blur` | `6` | px — frost behind the lens. `0` = crisp |
| `softness` | `0.55` | `0`–`1` — how gradually the edge band ramps. `1` a slow swell, `0` a hard optical edge |
| `bias` | `0.5` | `0`–`1` — which axis the lens leans on. `0` = X only, `1` = Y only |
| `invert` | `0` | `0`–`1` — develop the backdrop through the pane |
| `saturate` | `1.06` | saturation of the refracted image |
| `fringe` | `['#8E00FF','#2CFF05']` | the legislated prism — `[outer ray, inner ray]` |
| `emission` | `'#6F75D7'` | the ink the tile emits |
| `bleed` | `44` | px — how far that emission escapes the tile |
| `fill` | `''` | pane tint. empty = the tier decides; any CSS colour overrides |
| `rim` | `0.72` | specular edge strength, `0`–`1` |
| `rimAngle` | `38` | degrees the light comes **from**. `0` = left, `90` = top |

**Frost and softness are different things.** `blur` softens the *image* behind the
glass; `softness` softens the *bend* itself. A crisp lens drops both.

**`depth` and `strength` are a pair, and the ratio is the whole tuning problem.**
Displacement peaks at `strength / 2` px right at the rim. Push that past the band
width and the edge samples from outside the band entirely — the image stops
bending and starts smearing, and the three rays separate far enough to read as
three copies of the text instead of one fringe. Keep `strength ≲ 1.5 × depth`,
and `dispersion` around a tenth of `strength`. A hard ramp concentrates the same
displacement into a narrower band, so it tears sooner — drop `strength` further as
`softness` falls.

`depth` is clamped to half the shorter side. Below that the map loses its neutral
centre and the whole pane displaces uniformly instead of only at the rim — which
is what happens to anything thin: a one-character cursor, a chip, a scan bar.

**A text grid is not isotropic.** Displacing in Y moves whole lines and reads as a
bend; displacing in X shifts characters inside a line and shreds words. `bias`
exists so a lens can lean on the axis that reads.

### Black glass on a white ground

A dark `fill` cannot give you a black pane over white paper — the fill paints *on
top* of the refracted backdrop and buries the very bend you wanted to see. Use
`invert` instead. Inverting turns the paper itself dark and the ink light, so the
pane reads genuinely black while the displaced characters stay legible:

```html
<div class="glassci" data-glassci
     data-glassci-invert="1"
     data-glassci-blur="0" data-glassci-softness="0.34"
     data-glassci-fill="rgba(0,0,0,.10)"></div>
```

The emission works the same way on paper — a dark object does not glow, it casts.
Give `emission` a dark ink and the same drop-shadow mechanism becomes a contact
shadow. No new rule, just a different colour.

### Helper classes

- `.glassci-field` — the substrate. A monospace grid for the lens to bend.
- `.glassci-lit` — the phosphor. Characters as the light source.

---

## The ladder

`backdrop-filter: url(#svg-filter)` is a Chromium capability. WebKit and Gecko
take the property but not the reference. glassci feature-tests at boot, stamps
`data-glassci-tier` on `<html>`, and both halves read it:

| tier | what renders | where |
|---|---|---|
| `lens` | full refraction, legislated dispersion, rim, bleed | Chromium |
| `frost` | blur + saturate + rim + bleed (no bend) | Safari, Firefox |
| `plate` | tinted plate + hairline + rim | no `backdrop-filter` at all |

**Nothing reflows between tiers** — same geometry, same box, every time.

Pin a tier by setting the attribute yourself before the script runs; your value
wins over detection:

```html
<html data-glassci-tier="frost">
```

`prefers-reduced-transparency` lifts the frost entirely and the glass reads as a
solid plate, matching EPOQ III's own behaviour. `prefers-reduced-motion` kills
transitions. Print drops the rim and the emission.

---

## On a system

Every ink reads through `var()` with a live EPOQ III token as the fallback:

```css
--glassci-hum:  var(--hum, #6F75D7);
--glassci-go:   var(--signal-go, #8E00FF);
--glassci-live: var(--signal-live, #2CFF05);
```

Drop glassci into a page that already has those tokens and it inherits the
system. Drop it anywhere else and it still works.

---

## Mechanism credit

Read, not imported — no code from these ships here:

- **[nikdelvin/liquid-glass](https://github.com/nikdelvin/liquid-glass)** — the
  displacement-map encoding (grey = no displacement, R/G channels as x/y ramps,
  an inner blurred shape returning the middle to neutral).
- **[archisvaze/liquid-glass](https://github.com/archisvaze/liquid-glass)** — the
  specular composite in the filter chain.
- **[ybouane/liquidglass](https://github.com/ybouane/liquidglass)** and
  **[rdev/liquid-glass-react](https://github.com/rdev/liquid-glass-react)** — the
  rounded-rect SDF and bevel height field, as the physics reference for the ramp.

glassci differs in substrate (characters, not photographs), in light direction
(emitted, not reflected), in dispersion (named inks, not RGB), in geometry (a
real superellipse path, so the refracting band follows the silhouette rather
than approximating it with a border-radius), and in weight (two files, zero
dependencies).

---

MIT © HHG. No red. The palette legislates none.
