#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  HHG · THE GLASS STAGE — the HHG HUB mark, PRINTED.
#  Real CLI art (epoq3 .tui-art): Red Hat Mono block caps, on the
#  glass stage. Paper-white — epoq3 renders tui-art in paper, never
#  a hue; green stays reserved for the ONE live signal.
#  Costs nothing to print. No image, no hallucinated logo — just
#  characters on the stage. Sourced by ~/.zshrc on Ghostty shells.
# ─────────────────────────────────────────────────────────────
P="$(printf '\033[38;2;255;255;255m')"   # --paper (on-dark)
D="$(printf '\033[38;2;110;110;120m')"   # dim
R="$(printf '\033[0m')"

printf '\n'
printf '  %s█  █ █  █ ████      █  █ █  █ ███ %s\n' "$P" "$R"
printf '  %s█  █ █  █ █         █  █ █  █ █  █%s\n' "$P" "$R"
printf '  %s████ ████ █ ██      ████ █  █ ███ %s\n' "$P" "$R"
printf '  %s█  █ █  █ █  █      █  █ █  █ █  █%s\n' "$P" "$R"
printf '  %s█  █ █  █ ████      █  █ ████ ███ %s\n' "$P" "$R"
printf '  %sop@hhg › ready%s\n\n' "$D" "$R"
