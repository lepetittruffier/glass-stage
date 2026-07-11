#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  THE GLASS STAGE — epoq palette specimen
#  Every ink is a live EPOQ III token. Truecolor on the stage (#000000).
#  Run it any time:  sh ~/.config/ghostty/palette-specimen.sh
# ─────────────────────────────────────────────────────────────
fg()  { printf '\033[38;2;%sm' "$1"; }   # $1 = "R;G;B"
bg()  { printf '\033[48;2;%sm' "$1"; }
R="$(printf '\033[0m')"

# —— the inks · epoq3 tokens ——
LIVE="44;255;5"      ; GO="142;0;255"    ; ATTN="54;0;218"
HUM="111;117;215"    ; DUSK="95;82;149"  ; GREY="81;81;81"
GRAPH="39;39;39"     ; PAPER="255;255;255"
DIMTX="$(fg "$GREY")"; FGTX="$(fg "$PAPER")"

printf '\n'
printf '  %sTHE GLASS STAGE%s  %s· epoq palette · truecolor specimen%s\n\n' "$(fg "$LIVE")" "$R" "$DIMTX" "$R"

# —— spectrum bar: every ink, edge to edge ——
printf '  '
for c in "$LIVE" "$GO" "$ATTN" "$HUM" "$DUSK" "$GREY" "$GRAPH"; do
  printf '%s      %s' "$(bg "$c")" "$R"
done
printf '\n\n'

# —— labeled swatches: block · token · hex · role ——
row() { # $1=rgb  $2=token  $3=hex  $4=role
  printf '  %s  ██████  %s%s%-14s%s %s%-9s%s %s%s%s\n' \
    "$(fg "$1")" "$R" "$(fg "$1")" "$2" "$R" "$FGTX" "$3" "$R" "$DIMTX" "$4" "$R"
}
row "$LIVE" "signal-live" "#2CFF05" "the live readout · cursor · additions"
row "$GO"   "signal-go"   "#8E00FF" "the no-red flag · error · deletions"
row "$HUM"  "hum"         "#6F75D7" "the locator · hunk headers"
row "$DUSK" "dusk"        "#5F5295" "seen / faded · prompt border"
row "$GREY" "grey-51"     "#515151" "dim · meta · comments"
printf '\n'

# —— motion ramp: graphite → hum, epoq stops ——
printf '  %sMOTION%s  ' "$DIMTX" "$R"
for c in "$GRAPH" "$GREY" "$DUSK" "$HUM"; do
  printf '%s  %s' "$(bg "$c")" "$R"
done
printf '  %sgraphite → hum%s\n\n' "$DIMTX" "$R"

# —— diff, on-system · NO RED ——
printf '  %sDIFF%s  %sno red%s\n' "$DIMTX" "$R" "$(fg "$GO")" "$R"
printf '    %s@@ -1,4 +1,4 @@%s\n'          "$(fg "$HUM")"  "$R"
printf '    %s+ taste over volume%s\n'      "$(fg "$LIVE")" "$R"
printf '    %s- generated at scale%s\n'     "$(fg "$GO")"   "$R"
printf '    %s+ authored, on the system%s\n' "$(fg "$LIVE")" "$R"
printf '\n'

# —— the prompt, closed with a live block cursor ——
printf '  %sop@hhg%s %s›%s ready %s█%s\n\n' "$(fg "$LIVE")" "$R" "$DIMTX" "$R" "$(fg "$LIVE")" "$R"
