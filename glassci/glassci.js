/*! glassci — glass with nothing to refract but characters.
 *  Zero dependencies. MIT. Part of THE GLASS STAGE (HHG).
 *
 *  The four laws:
 *    1. The substrate is a monospace field, not a photograph. A photo hides
 *       distortion; a grid measures it. The bend is legible because the thing
 *       behind is a ruler.
 *    2. Lit from inside. The characters are the phosphor — emission, not reflection.
 *    3. Black glass. The lens is dark; the specular rim is the only white on it.
 *    4. The prism obeys the palette. Dispersion is legislated onto named inks —
 *       there is no red in the fringe unless you put one there.
 *
 *  Mechanism credit — read, not imported:
 *    displacement-map encoding .... nikdelvin/liquid-glass
 *    specular composite ........... archisvaze/liquid-glass
 *    bevel/SDF refraction model ... ybouane/liquidglass, rdev/liquid-glass-react
 *  No WebGL ships. No canvas ships. Everything below is SVG the browser already has.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.glassci = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var uid = 0;

  /* ── defaults ──────────────────────────────────────────────────────────────
     Every length is CSS px at the element's own scale. The names are the
     physical thing, not the CSS trick that fakes it. */
  var DEFAULTS = {
    radius:     0.28,                    // corner size — <1 = fraction of min(w,h), >=1 = px
    n:          4,                       // superellipse exponent · 2 = circle, 4 = squircle, 8 = near-square
    /* depth and strength are a pair, and the ratio is the whole tuning problem.
       Displacement peaks at strength/2 px right at the rim. Push that past the
       band width and the edge samples from outside the band entirely — the
       image stops bending and starts smearing, and the three rays separate far
       enough to read as three copies of the text instead of one fringe.
       Keep strength ≲ 1.5 × depth, and dispersion ≈ a tenth of strength.
       A hard ramp (low `softness`) concentrates the same displacement into a
       narrower band, so it tears sooner — drop strength further as softness
       falls, or the edge stops bending the grid and starts shredding it. */
    depth:      18,                      // px — thickness of the refracting edge band
    strength:   24,                      // px — how hard that band bends what is behind it
    dispersion: 3,                       // px — ray divergence between inks · 0 = achromatic
    blur:       6,                       // px — frost behind the lens
    bias:       0.5,                     // 0..1 — which axis the lens leans on.
                                         // 0 = bend in X only, 0.5 = equal, 1 = Y only.
                                         // A text grid is not isotropic: Y moves whole
                                         // lines and reads as a bend, X shifts characters
                                         // inside a line and shreds words.
    invert:     0,                       // 0..1 — develop the backdrop through the pane.
                                         // On a white ground this is what lets the glass be
                                         // genuinely black AND still show the bend: a dark
                                         // FILL buries the refraction under it, an inversion
                                         // turns the ground itself dark and the ink light,
                                         // so the displaced characters stay legible.
    softness:   0.55,                    // 0..1 — how gradually the edge band ramps.
                                         // 1 = a slow swell, 0 = a hard optical edge.
                                         // Frost (blur) softens the IMAGE; this softens
                                         // the BEND. Drop both for a crisp lens.
    saturate:   1.06,
    fringe:     ['#8E00FF', '#2CFF05'],  // the legislated prism — [outer ray, inner ray]
    emission:   '#6F75D7',               // the ink the tile emits
    bleed:      44,                      // px — how far that emission escapes the tile
    rim:        0.72,                    // specular edge strength 0..1
    fill:       '',                      // pane tint · '' lets the tier decide · any CSS colour overrides
    rimAngle:   38                       // deg the light comes FROM · 0 = left, 90 = top (SVG y is down)
  };

  /* ── tier detection ────────────────────────────────────────────────────────
     Three honest tiers. We feature-test rather than sniff, stamp the result on
     <html>, and let the CSS branch on it. The specimen prints its own tier —
     an instrument that lies about its conditions is not an instrument. */
  var TIERS = { lens: 1, frost: 1, plate: 1 };
  var _detected = null;

  function detectTier() {
    if (_detected) return _detected;
    var s = (typeof CSS !== 'undefined' && CSS.supports) ? CSS.supports.bind(CSS) : function () { return false; };
    var hasBackdrop = s('backdrop-filter', 'blur(1px)') || s('-webkit-backdrop-filter', 'blur(1px)');
    // The lens needs an SVG filter reference inside backdrop-filter. Chromium takes it;
    // WebKit and Gecko accept the property but not the url() reference.
    var hasFilterRef = s('backdrop-filter', 'url(#x)');
    _detected = !hasBackdrop ? 'plate' : (hasFilterRef ? 'lens' : 'frost');
    return _detected;
  }

  /* An author-set data-glassci-tier on <html> WINS over detection, and it has to
     win here rather than only in the CSS — otherwise pinning a tier reskins the
     fill but leaves the JS still writing an SVG filter reference no engine at
     that tier can resolve, and the pane silently loses its material. One source
     of truth for the tier, read by both halves. */
  function tier() {
    var declared = (typeof document !== 'undefined')
      && document.documentElement.getAttribute('data-glassci-tier');
    return (declared && TIERS[declared]) ? declared : detectTier();
  }

  function stampTier() {
    var el = document.documentElement;
    if (!el.hasAttribute('data-glassci-tier')) el.setAttribute('data-glassci-tier', detectTier());
    if (!el.hasAttribute('data-glassci-squircle')) {
      var native = (typeof CSS !== 'undefined' && CSS.supports && CSS.supports('corner-shape', 'squircle'));
      el.setAttribute('data-glassci-squircle', native ? 'native' : 'path');
    }
  }

  /* ── colour ────────────────────────────────────────────────────────────────
     Resolve whatever the caller gave us (hex, rgb(), or a var() reference that
     the document has already computed) down to 0..1 components. */
  function rgb(input, host) {
    var v = String(input || '').trim();
    if (v.indexOf('var(') === 0 && host) {
      var name = v.slice(4, v.lastIndexOf(')')).split(',')[0].trim();
      v = getComputedStyle(host).getPropertyValue(name).trim() || '#FFFFFF';
    }
    if (v.charAt(0) === '#') {
      if (v.length === 4) v = '#' + v[1] + v[1] + v[2] + v[2] + v[3] + v[3];
      return [parseInt(v.substr(1, 2), 16) / 255,
              parseInt(v.substr(3, 2), 16) / 255,
              parseInt(v.substr(5, 2), 16) / 255];
    }
    var m = v.match(/-?[\d.]+/g);
    return m ? [(+m[0]) / 255, (+m[1]) / 255, (+m[2]) / 255] : [1, 1, 1];
  }

  /* Luminance → ink. Collapses whatever arrives to its brightness, then paints
     that brightness in one named colour. This is how law 4 is enforced: the
     fringe cannot be a hue we did not legislate. */
  function lumToInk(c, gain) {
    var L = [0.2126, 0.7152, 0.0722], out = [];
    for (var i = 0; i < 3; i++)
      out.push((c[i] * gain * L[0]).toFixed(4), (c[i] * gain * L[1]).toFixed(4), (c[i] * gain * L[2]).toFixed(4), '0', '0');
    return out.join(' ') + ' 0 0 0 1 0';
  }

  /* ── the shape ─────────────────────────────────────────────────────────────
     A rounded rectangle whose corners are superellipse quarters rather than
     circular arcs: straight sides, continuous-curvature corners. n is the one
     knob — 2 gives you the ordinary rounded rect, 4 the squircle. */
  function squirclePath(w, h, r, n) {
    r = Math.min(r, Math.min(w, h) / 2);
    if (r <= 0) return 'M0 0H' + w + 'V' + h + 'H0Z';
    var STEPS = 24, p = [], i, t, u, cx, cy;
    /* One superellipse quarter around a corner centre. `back` sweeps the angle in
       reverse, which is what makes consecutive corners meet: each arc has to
       start exactly where the previous one finished, or the path closes itself
       with a chord straight across the shape. */
    function arc(ox, oy, sx, sy, back) {
      for (i = 0; i <= STEPS; i++) {
        u = back ? 1 - i / STEPS : i / STEPS;
        t = (Math.PI / 2) * u;
        cx = ox + sx * r * Math.pow(Math.cos(t), 2 / n);
        cy = oy + sy * r * Math.pow(Math.sin(t), 2 / n);
        p.push((p.length ? 'L' : 'M') + cx.toFixed(2) + ' ' + cy.toFixed(2));
      }
    }
    arc(w - r, h - r,  1,  1, false);  // right edge  → bottom edge
    arc(r,     h - r, -1,  1, true);   // bottom edge → left edge
    arc(r,     r,     -1, -1, false);  // left edge   → top edge
    arc(w - r, r,      1, -1, true);   // top edge    → right edge
    return p.join('') + 'Z';
  }

  function resolveRadius(o, w, h) {
    return o.radius < 1 ? o.radius * Math.min(w, h) : o.radius;
  }

  /* ── the displacement map ──────────────────────────────────────────────────
     #808080 encodes "no displacement". The R channel ramps left→right, G ramps
     top→bottom; an inner copy of the shape, blurred, returns the middle to
     neutral. Result: flat in the centre, ramping hard at the rim — which is
     what a lens does. The inner shape is the real squircle, not a rounded rect,
     so the refracting band follows the silhouette exactly. */
  function displacementMap(w, h, r, n, depth, softness, bias) {
    /* The band cannot be wider than half the element, or the inner neutral shape
       comes out with negative dimensions, draws off-canvas, and the map loses its
       flat centre entirely — at which point the whole pane displaces uniformly
       instead of only at the rim. Anything thin (a one-character cursor, a chip,
       a scan bar) hits this immediately. */
    depth = Math.min(depth, Math.max(Math.min(w, h) / 2 - 1, 0));

    var inner = squirclePath(w - 2 * depth, h - 2 * depth, Math.max(r - depth, 0), n);
    var soft = Math.max(depth * softness, 0.01);        // the ramp
    var grain = Math.max(1.5 * softness, 0.01);         // the gradient's own smoothing

    /* Amplitude per axis. A monospace grid is not isotropic: displacing in Y
       moves whole lines and reads as a bend, displacing in X shifts characters
       inside a line and shreds words. `bias` lets a lens lean on the axis that
       reads. Amplitude 0 leaves that channel flat at 128 — no displacement. */
    var ax = Math.min(1, 2 * (1 - bias)), ay = Math.min(1, 2 * bias);
    function ramp(a) { return [Math.round(128 + 127 * a), Math.round(128 - 127 * a)]; }
    var rx = ramp(ax), ry = ramp(ay);

    var svg =
      '<svg xmlns="' + NS + '" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
      '<defs>' +
        '<linearGradient id="x" x1="0" y1="0" x2="1" y2="0">' +
          '<stop offset="0" stop-color="rgb(' + rx[0] + ',0,0)"/>' +
          '<stop offset="1" stop-color="rgb(' + rx[1] + ',0,0)"/></linearGradient>' +
        '<linearGradient id="y" x1="0" y1="0" x2="0" y2="1">' +
          '<stop offset="0" stop-color="rgb(0,' + ry[0] + ',0)"/>' +
          '<stop offset="1" stop-color="rgb(0,' + ry[1] + ',0)"/></linearGradient>' +
      '</defs>' +
      '<rect width="' + w + '" height="' + h + '" fill="#808080"/>' +
      '<g filter="blur(' + grain.toFixed(2) + ')">' +
        // #000080 seeds the B channel at neutral; R and G arrive by screen below.
        '<rect width="' + w + '" height="' + h + '" fill="#000080"/>' +
        '<rect width="' + w + '" height="' + h + '" fill="url(#y)" style="mix-blend-mode:screen"/>' +
        '<rect width="' + w + '" height="' + h + '" fill="url(#x)" style="mix-blend-mode:screen"/>' +
        '<path transform="translate(' + depth + ',' + depth + ')" d="' + inner + '" fill="#808080" ' +
              'filter="blur(' + soft.toFixed(2) + ')"/>' +
      '</g></svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  /* ── the filter ────────────────────────────────────────────────────────────
     Three rays through the same map at three scales. The neutral ray carries the
     image; the divergence between rays IS the dispersion, and that divergence —
     only that — gets painted in a legislated ink and screened back on. Where the
     rays agree (the flat centre) the difference is black and screen is a no-op,
     so the middle of the pane stays honest. */
  function buildFilter(id, w, h, o, host) {
    var f = document.createElementNS(NS, 'filter');
    f.setAttribute('id', id);
    /* The region must be stated in the same units as the feImage inside it, in
       real pixels. Mixing userSpaceOnUse with percentage extents resolves the
       percentages against the viewport instead of the element, which slides the
       map off-centre — the tell is a lens that bends gently on one edge and
       smears on the opposite one. */
    f.setAttribute('filterUnits', 'userSpaceOnUse');
    f.setAttribute('x', '0'); f.setAttribute('y', '0');
    f.setAttribute('width', w); f.setAttribute('height', h);
    f.setAttribute('color-interpolation-filters', 'sRGB');

    var d = Math.max(o.dispersion, 0);
    var pieces = [
      ['feImage', { href: displacementMap(w, h, resolveRadius(o, w, h), o.n, o.depth, o.softness, o.bias),
                    x: 0, y: 0, width: w, height: h, preserveAspectRatio: 'none', result: 'MAP' }],
      ray('RAY_LO', o.strength - d), ray('RAY_MID', o.strength), ray('RAY_HI', o.strength + d)
    ];

    if (o.invert > 0) {
      var k = Math.min(o.invert, 1);
      pieces.splice(1, 0, ['feColorMatrix', { in: 'SourceGraphic', type: 'matrix', result: 'SRC',
        values: [(1 - 2 * k), 0, 0, 0, k,
                 0, (1 - 2 * k), 0, 0, k,
                 0, 0, (1 - 2 * k), 0, k,
                 0, 0, 0, 1, 0].join(' ') }]);
      pieces.forEach(function (pc) { if (pc[0] === 'feDisplacementMap') pc[1]['in'] = 'SRC'; });
    }

    if (d > 0) {
      pieces.push(
        ['feBlend', { in: 'RAY_HI', in2: 'RAY_MID', mode: 'difference', result: 'DIV_HI' }],
        ['feBlend', { in: 'RAY_LO', in2: 'RAY_MID', mode: 'difference', result: 'DIV_LO' }],
        ['feColorMatrix', { in: 'DIV_HI', type: 'matrix', result: 'INK_HI',
                            values: lumToInk(rgb(o.fringe[0], host), 2.2) }],
        ['feColorMatrix', { in: 'DIV_LO', type: 'matrix', result: 'INK_LO',
                            values: lumToInk(rgb(o.fringe[1], host), 2.2) }],
        ['feBlend', { in: 'INK_HI', in2: 'RAY_MID', mode: 'screen', result: 'LIT' }],
        ['feBlend', { in: 'INK_LO', in2: 'LIT', mode: 'screen', result: 'DISPERSED' }]
      );
    }

    var last = d > 0 ? 'DISPERSED' : 'RAY_MID';
    if (o.blur > 0) { pieces.push(['feGaussianBlur', { in: last, stdDeviation: o.blur / 2, result: 'FROST' }]); last = 'FROST'; }
    if (o.saturate !== 1) pieces.push(['feColorMatrix', { in: last, type: 'saturate', values: o.saturate }]);

    pieces.forEach(function (p) {
      var node = document.createElementNS(NS, p[0]);
      for (var key in p[1]) node.setAttribute(key, p[1][key]);
      f.appendChild(node);
    });
    return f;

    function ray(result, scale) {
      return ['feDisplacementMap', { in: 'SourceGraphic', in2: 'MAP', scale: Math.max(scale, 0),
                                     xChannelSelector: 'R', yChannelSelector: 'G', result: result }];
    }
  }

  /* ── the rim ───────────────────────────────────────────────────────────────
     Not a uniform hairline — a directional specular. Bright where the light
     lands, gone where it does not, with a second wide soft pass underneath so
     the edge reads as a thickness rather than a stroke. Drawn on the real
     squircle path, so it tracks the silhouette exactly. */
  function buildRim(svg, id, w, h, o) {
    var path = squirclePath(w, h, resolveRadius(o, w, h), o.n);
    var g = document.createElementNS(NS, 'linearGradient');
    var a = (o.rimAngle * Math.PI) / 180;
    g.setAttribute('id', id + '-rim');
    g.setAttribute('x1', (0.5 - Math.cos(a) * 0.5).toFixed(3));
    g.setAttribute('y1', (0.5 - Math.sin(a) * 0.5).toFixed(3));
    g.setAttribute('x2', (0.5 + Math.cos(a) * 0.5).toFixed(3));
    g.setAttribute('y2', (0.5 + Math.sin(a) * 0.5).toFixed(3));
    [[0, o.rim], [0.32, o.rim * 0.30], [0.62, o.rim * 0.06], [0.85, o.rim * 0.42], [1, o.rim * 0.14]]
      .forEach(function (s) {
        var stop = document.createElementNS(NS, 'stop');
        stop.setAttribute('offset', s[0]);
        stop.setAttribute('stop-color', '#FFFFFF');
        stop.setAttribute('stop-opacity', s[1].toFixed(3));
        g.appendChild(stop);
      });
    svg.appendChild(g);

    // wide soft pass first, then the hairline on top. A crisp lens should not
    // wear a soft halo on its edge, so the wide pass follows `softness` too.
    var halo = Math.max(2.5 * o.softness, 0.01);
    [[3, 0.30 * Math.max(o.softness, 0.25), 'blur(' + halo.toFixed(2) + ')'], [1, 1, null]].forEach(function (s) {
      var p = document.createElementNS(NS, 'path');
      p.setAttribute('d', path);
      p.setAttribute('fill', 'none');
      p.setAttribute('stroke', 'url(#' + id + '-rim)');
      p.setAttribute('stroke-width', s[0]);
      p.setAttribute('opacity', s[1]);
      if (s[2]) p.setAttribute('filter', s[2]);
      svg.appendChild(p);
    });
  }

  /* ── instance ──────────────────────────────────────────────────────────── */
  function apply(el, opts) {
    if (!el) return null;
    if (el.__glassci) el.__glassci.destroy();

    var o = {}, k;
    for (k in DEFAULTS) o[k] = DEFAULTS[k];
    for (k in (opts || {})) if (opts[k] !== undefined && opts[k] !== null) o[k] = opts[k];
    for (k in DEFAULTS) {                       // data-* wins over the argument
      var attr = el.getAttribute('data-glassci-' + k.toLowerCase());
      if (attr !== null) o[k] = (k === 'fringe') ? attr.split(/\s*,\s*/) : (isNaN(+attr) ? attr : +attr);
    }

    stampTier();
    el.classList.add('glassci');

    var id = 'glassci-' + (++uid);
    var defs = document.createElementNS(NS, 'svg');
    defs.setAttribute('class', 'glassci__defs');
    defs.setAttribute('aria-hidden', 'true');
    defs.setAttribute('width', '0'); defs.setAttribute('height', '0');
    el.appendChild(defs);

    var rimSvg = document.createElementNS(NS, 'svg');
    rimSvg.setAttribute('class', 'glassci__rim');
    rimSvg.setAttribute('aria-hidden', 'true');
    el.appendChild(rimSvg);

    var ro = null, w = 0, h = 0, queued = 0, drawing = false;

    /* Redraws are coalesced into one frame. Without this, drawing mutates the
       element (custom properties, SVG children), the observer sees a mutation,
       and the loop trips the browser's "undelivered notifications" guard —
       which on some engines quietly stops delivering to that observer for good. */
    function schedule() {
      if (queued || drawing) return;
      queued = (typeof requestAnimationFrame !== 'undefined')
        ? requestAnimationFrame(function () { queued = 0; draw(); })
        : setTimeout(function () { queued = 0; draw(); }, 16);
    }

    function draw() {
      var r = el.getBoundingClientRect();
      var nw = Math.round(r.width), nh = Math.round(r.height);
      if (nw < 1 || nh < 1) return;          // display:none / not laid out yet — don't cache it
      if (nw === w && nh === h) return;
      drawing = true;
      w = nw; h = nh;

      var rad = resolveRadius(o, w, h);
      var path = squirclePath(w, h, rad, o.n);

      // Everything the CSS needs to know, handed over as custom properties.
      el.style.setProperty('--glassci-shape', 'path("' + path + '")');
      el.style.setProperty('--glassci-radius', rad.toFixed(2) + 'px');
      el.style.setProperty('--glassci-blur', o.blur + 'px');
      el.style.setProperty('--glassci-saturate', o.saturate);
      el.style.setProperty('--glassci-bleed', o.bleed + 'px');
      el.style.setProperty('--glassci-emission', o.emission);
      el.style.setProperty('--glassci-rim', o.rim);
      if (o.fill) el.style.setProperty('--glassci-fill', o.fill);
      else el.style.removeProperty('--glassci-fill');

      /* The native corner keywords only cover two of the shapes `n` can express.
         Hand the pane to CSS ONLY when a keyword actually matches the exponent —
         otherwise the generated path stays in charge. Getting this wrong is
         invisible until you ask for a circle and the rim draws one while the
         pane clips a squircle: one element, two silhouettes. */
      el.setAttribute('data-glassci-native',
        o.n <= 2.2 ? 'round' : (o.n >= 3.4 && o.n <= 4.6 ? 'squircle' : 'off'));

      while (defs.firstChild) defs.removeChild(defs.firstChild);
      while (rimSvg.firstChild) rimSvg.removeChild(rimSvg.firstChild);

      if (tier() === 'lens') {
        defs.appendChild(buildFilter(id, w, h, o, el));
        el.style.setProperty('--glassci-lens', 'url(#' + id + ')');
      } else {
        el.style.setProperty('--glassci-lens',
          (o.invert > 0 ? 'invert(' + o.invert + ') ' : '') +
          'blur(' + o.blur + 'px) saturate(' + o.saturate + ')');
      }

      rimSvg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      rimSvg.setAttribute('width', w); rimSvg.setAttribute('height', h);
      buildRim(rimSvg, id, w, h, o);
      drawing = false;
    }

    draw();

    /* Three ways to hear about a size change, because no single one is reliable
       everywhere: the observer is the good one, the window event is the backstop
       when observer delivery is throttled or absent, and the font/load hooks
       catch the reflow after the monospace face arrives — the tile is measured
       in characters, so its size moves when the metrics do. */
    if (typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(schedule); ro.observe(el); }
    window.addEventListener('resize', schedule);
    window.addEventListener('load', schedule);
    if (document.fonts && document.fonts.ready && document.fonts.ready.then)
      document.fonts.ready.then(schedule);

    var api = {
      el: el, options: o, tier: tier(),
      set: function (patch) { for (var q in patch) o[q] = patch[q]; w = h = 0; draw(); return api; },
      redraw: function () { w = h = 0; draw(); return api; },
      destroy: function () {
        if (ro) ro.disconnect();
        window.removeEventListener('resize', schedule);
        window.removeEventListener('load', schedule);
        if (queued) { cancelAnimationFrame(queued); queued = 0; }
        if (defs.parentNode) defs.parentNode.removeChild(defs);
        if (rimSvg.parentNode) rimSvg.parentNode.removeChild(rimSvg);
        el.classList.remove('glassci');
        ['shape', 'radius', 'blur', 'saturate', 'bleed', 'emission', 'rim', 'lens', 'fill']
          .forEach(function (p) { el.style.removeProperty('--glassci-' + p); });
        el.removeAttribute('data-glassci-native');
        delete el.__glassci;
      }
    };
    el.__glassci = api;
    return api;
  }

  /* ── entry ─────────────────────────────────────────────────────────────────
     glassci(el|selector|NodeList, options) — or drop [data-glassci] into the
     markup and let it wire itself. */
  function glassci(target, opts) {
    if (typeof target === 'string') target = document.querySelectorAll(target);
    if (target && target.length !== undefined && !target.nodeType)
      return Array.prototype.map.call(target, function (n) { return apply(n, opts); });
    return apply(target, opts);
  }

  glassci.tier = tier;
  glassci.defaults = DEFAULTS;
  glassci.squirclePath = squirclePath;
  glassci.auto = function (scope) {
    stampTier();
    return glassci((scope || document).querySelectorAll('[data-glassci]'));
  };

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading')
      document.addEventListener('DOMContentLoaded', function () { glassci.auto(); });
    else glassci.auto();
  }

  return glassci;
}));
