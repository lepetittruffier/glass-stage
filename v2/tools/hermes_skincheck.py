"""GLASS STAGE v2 — load the emitted Hermes skins through Hermes' own code paths.

Run from the hermes-agent checkout with its venv and an isolated HERMES_HOME:
  HERMES_HOME=<scratch> venv/bin/python <this> <skin.yaml> [<skin.yaml> ...]
Read-only: nothing is installed, the real ~/.hermes is never touched.
"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from hermes_cli import skin_engine as se  # noqa: E402

try:  # the audit module imports pytest only for its parametrize decorators
    import pytest  # noqa: F401
except ImportError:
    stub = types.ModuleType("pytest")
    stub.mark = types.SimpleNamespace(parametrize=lambda *a, **k: (lambda f: f))
    sys.modules["pytest"] = stub
sys.path.insert(0, str(Path.cwd() / "tests" / "hermes_cli"))
import test_skin_palettes as audit  # noqa: E402

from prompt_toolkit.styles import Style  # noqa: E402
from rich.text import Text  # noqa: E402


def audit_base(palette: dict, is_light: bool) -> list:
    pole = audit.LIGHT_POLE if is_light else audit.DARK_POLE
    out = [f"missing {sorted(audit.REQUIRED_KEYS - palette.keys())}"] if audit.REQUIRED_KEYS - palette.keys() else []
    if not is_light:
        out += [f"{k} {palette[k]} {audit.contrast(palette[k], pole):.2f} < {audit.STRONG_MIN} (strong)"
                for k in audit.STRONG_FG if audit.contrast(palette[k], pole) < audit.STRONG_MIN]
        out += [f"{k} {palette[k]} {audit.contrast(palette[k], pole):.2f} < {audit.SOFT_MIN} (soft)"
                for k in audit.SOFT_FG if audit.contrast(palette[k], pole) < audit.SOFT_MIN]
    bar = palette["status_bar_bg"]
    for k in audit.ON_STATUS_BAR:
        floor = audit.STRONG_MIN if k == "status_bar_strong" else audit.SOFT_MIN
        if audit.contrast(palette[k], bar) < floor:
            out.append(f"{k} {palette[k]} on bar {bar} {audit.contrast(palette[k], bar):.2f} < {floor}")
    audit._check_fills(palette, is_light, audit.FILLS, out)
    audit._check_chip(palette, out)
    return out


report = {}
for arg in sys.argv[1:]:
    path = Path(arg)
    data = se._load_skin_from_yaml(path)
    assert data, f"skin_engine refused {path}"
    sk = se._build_skin_config(data)
    raw_colors = data.get("colors", {})
    r = {"name": sk.name, "colors": len(raw_colors), "light_colors": len(sk.light_colors),
         "dark_colors": dict(sk.dark_colors), "background_in_colors": "background" in raw_colors}

    # Rich markup of the banner art must parse (banner.py prints it through Rich)
    for key in ("banner_logo", "banner_hero"):
        art = getattr(sk, key)
        if art:
            Text.from_markup(art)
    r["banner_markup"] = "parses"

    # prompt_toolkit must accept every style the classic CLI derives from this skin
    se.get_active_skin = lambda sk=sk: sk  # scope the override to this skin
    styles = se.get_prompt_toolkit_style_overrides()
    Style.from_dict(styles)
    r["prompt_toolkit_styles"] = f"{len(styles)} parse"
    r["status_bar_bad_style"] = styles["status-bar-bad"]

    # the TUI's own rule (ui-tui theme.ts skinIsLight + createGatewayEventHandler themeForSkin):
    # no authored background in colors -> polarity follows the host; the paired block overlays colors
    for host, block in (("light host", sk.light_colors), ("dark host", sk.dark_colors)):
        merged = {**raw_colors, **block} if block else dict(raw_colors)
        r[f"tui on {host}"] = {k: merged.get(k) for k in ("background", "banner_title", "ui_error", "status_bar_bad")}

    # the repo's own palette audit (built-in floors), read as information for a user skin
    base = {k: v for k, v in raw_colors.items() if k != "background"}
    r["audit base colors (dark, vs #101014)"] = audit_base(base, False) or "pass"
    light_full = {**base, **sk.light_colors}
    r["audit light palette (vs #ffffff)"] = audit_base(light_full, True) or "pass"
    r["overlay keys beyond the audit's required set"] = sorted(sk.light_colors.keys() - audit.REQUIRED_KEYS)
    report[path.name] = r

print(json.dumps(report, indent=1, ensure_ascii=False))
