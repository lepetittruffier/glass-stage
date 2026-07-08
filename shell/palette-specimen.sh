#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  THE GLASS STAGE — epoq palette specimen
#  Shows off the theme inks in truecolor on the stage (#0E0E12).
#  Run it any time:  sh ~/.config/ghostty/palette-specimen.sh
# ─────────────────────────────────────────────────────────────
esc() { printf '\033[%sm' "$1"; }
fg()  { printf '\033[38;2;%sm' "$1"; }   # $1 = "R;G;B"
bg()  { printf '\033[48;2;%sm' "$1"; }
R="$(printf '\033[0m')"

# —— the inks ——
LIVE="44;255;5"      ; FLAG="216;5;255"   ; MAGC="182;87;201"
HUM="111;117;215"    ; DUSK="95;82;149"   ; GREY="81;81;81"
GRAPH="39;39;39"     ; PAPER="232;232;237"
DIMTX="$(fg "$GREY")"; FGTX="$(fg "$PAPER")"

printf '\n'
printf '  %sTHE GLASS STAGE%s  %s· epoq palette · truecolor specimen%s\n\n' "$(fg "$LIVE")" "$R" "$DIMTX" "$R"

# —— spectrum bar: every ink, edge to edge ——
printf '  '
for c in "$LIVE" "$HUM" "$DUSK" "$MAGC" "$FLAG" "$GREY" "$GRAPH"; do
  printf '%s      %s' "$(bg "$c")" "$R"
done
printf '\n\n'

# —— labeled swatches: block · token · hex · role ——
row() { # $1=rgb  $2=token  $3=hex  $4=role
  printf '  %s  ██████  %s%s%-14s%s %s%-9s%s %s%s%s\n' \
    "$(fg "$1")" "$R" "$(fg "$1")" "$2" "$R" "$FGTX" "$3" "$R" "$DIMTX" "$4" "$R"
}
row "$LIVE" "signal-live" "#2CFF05" "the live readout · cursor · additions"
row "$FLAG" "signal-flag" "#D805FF" "the flag · error · removed (word)"
row "$MAGC" "flag-calm"   "#B657C9" "deletions · the calm magenta"
row "$HUM"  "hum"         "#6F75D7" "the locator · hunk headers"
row "$DUSK" "dusk"        "#5F5295" "seen / faded · prompt border"
row "$GREY" "grey-51"     "#515151" "dim · meta · comments"
printf '\n'

# —— motion ramp: graphite → hum, the mo-L levels ——
printf '  %sMOTION%s  ' "$DIMTX" "$R"
for c in "$GRAPH" "$GREY" "81;81;81" "$DUSK" "$HUM" "175;182;238"; do
  printf '%s  %s' "$(bg "$c")" "$R"
done
printf '  %sL0 → L5%s\n\n' "$DIMTX" "$R"

# —— diff, on-system · NO RED ——
printf '  %sDIFF%s  %sno red%s\n' "$DIMTX" "$R" "$(fg "$MAGC")" "$R"
printf '    %s%s@@ -1,4 +1,4 @@%s\n' "$(esc 1)" "$(fg "$HUM")" "$R"
printf '    %s+ taste over volume%s\n'      "$(fg "$LIVE")" "$R"
printf '    %s- generated at scale%s\n'     "$(fg "$MAGC")" "$R"
printf '    %s+ authored, on the system%s\n' "$(fg "$LIVE")" "$R"
printf '\n'

# —— the prompt, closed with a live block cursor ——
printf '  %sop@hub%s %s›%s ready %s█%s\n\n' "$(fg "$LIVE")" "$R" "$DIMTX" "$R" "$(fg "$LIVE")" "$R"
