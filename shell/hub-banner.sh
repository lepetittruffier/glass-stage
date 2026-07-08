#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  HHG · THE GLASS STAGE — the HUB mark, PRINTED.
#  Authored block lettering (hand-drawn), on the epoq3 palette:
#    green = --signal-live #2CFF05   ·   dim = --grey-51 #515151
#  Costs nothing to print. No image, no hallucinated logo — just
#  characters on the stage. Sourced by ~/.zshrc on Ghostty shells.
# ─────────────────────────────────────────────────────────────
G="$(printf '\033[38;2;44;255;5m')"    # --signal-live
D="$(printf '\033[38;2;81;81;81m')"    # --grey-51
R="$(printf '\033[0m')"

printf '\n'
printf '  %s█  █  █  █  ███ %s\n' "$G" "$R"
printf '  %s█  █  █  █  █  █%s\n' "$G" "$R"
printf '  %s████  █  █  ███ %s\n' "$G" "$R"
printf '  %s█  █  █  █  █  █%s\n' "$G" "$R"
printf '  %s█  █  ████  ███ %s\n' "$G" "$R"
printf '  %sop@hub › ready%s\n\n' "$D" "$R"
