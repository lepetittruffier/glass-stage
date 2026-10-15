#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  GLASS STAGE v2 — install beside v1, and switch in one step
#
#    sh v2/install.sh [literal|signal]   install v2 next to v1, then wear it
#    glass-stage v2                      wear v2 · the literal reading
#    glass-stage signal                  wear v2 · the signal reading
#    glass-stage v1                      back to how it was before v2
#    glass-stage status                  what each surface wears right now
#
#  `glass-stage` is ~/.config/glass-stage/switch.sh, linked into ~/.local/bin;
#  `sh ~/.config/glass-stage/switch.sh v1` always works, on PATH or not.
#
#  Surfaces, each only where it exists: Ghostty (the config file Ghostty gives
#  the last word, plus four theme files), git colours, the zsh prompt on
#  Ghostty shells, and the Hermes skin (classic CLI, TUI and the Desktop's
#  customCSS layer; needs `hermes skin`). Nothing asks; everything is kept.
#
#  v1 is whatever you wore before: the Ghostty config is kept byte for byte in
#  ~/.config/glass-stage/v1/ (or noted as absent) with your Hermes skin's name;
#  ~/.gitconfig and ~/.zshrc are each touched once, backed up first, with a
#  guarded include that reads a file which only exists while v2 is worn. Every
#  switch keeps a dated copy of the Ghostty config it replaces in backups/.
#  One line in ~/.config/glass-stage/agent-name names the agent in your skins.
# ─────────────────────────────────────────────────────────────
set -eu

GS="$HOME/.config/glass-stage"
GHX="${XDG_CONFIG_HOME:-$HOME/.config}/ghostty"
GHA="$HOME/Library/Application Support/com.mitchellh.ghostty"
HH="${HERMES_HOME:-$HOME/.hermes}"
DATE="$(date +%Y%m%d%H%M%S)"
HERE="$(cd "$(dirname "$0")" && pwd)"
MARK='>>> glass-stage v2 >>>'
GHOSTTY=""
GCONF=""
HERMES_OK=""

say() { printf '%s\n' "$*"; }
die() { printf 'glass-stage: %s\n' "$*" >&2; exit 1; }

# ── what is here ────────────────────────────────────────────
find_ghostty() {
  for g in /Applications/Ghostty.app/Contents/MacOS/ghostty "$HOME/Applications/Ghostty.app/Contents/MacOS/ghostty"; do
    if [ -x "$g" ]; then GHOSTTY="$g"; return 0; fi
  done
  GHOSTTY="$(command -v ghostty 2>/dev/null || true)"
}

ghostty_conf() {  # the file Ghostty gives the last word: Application Support over XDG, config.ghostty over config
  for f in "$GHA/config.ghostty" "$GHA/config" "$GHX/config.ghostty" "$GHX/config"; do
    if [ -f "$f" ]; then printf '%s\n' "$f"; return 0; fi
  done
  printf '%s\n' "$GHX/config"
}

load_gconf() {  # the Ghostty config this install manages; '' when Ghostty is not managed
  GCONF=""
  if [ -s "$GS/ghostty.path" ]; then
    GCONF="$(cat "$GS/ghostty.path")"
  elif [ -e "$GS/v1/ghostty.config" ]; then
    GCONF="$GHX/config"                       # installed before the managed path was recorded
  elif [ -n "$GHOSTTY" ]; then
    GCONF="$(ghostty_conf)"
  fi
}

ghostty_managed() {  # a Ghostty config to manage, and its v1 kept
  [ -n "$GCONF" ] || return 1
  [ -e "$GS/v1/ghostty.config" ] || [ -e "$GS/v1/ghostty.absent" ]
}

ghostty_valid() {  # <file> — Ghostty accepts it (or this Ghostty cannot check a named file)
  [ -n "$GHOSTTY" ] || return 0
  "$GHOSTTY" +validate-config --help 2>&1 | grep -q -- '--config-file' || return 0
  "$GHOSTTY" +validate-config --config-file="$1" >/dev/null 2>&1
}

hermes_ok() {  # a Hermes with skins on PATH, checked once
  if [ -z "$HERMES_OK" ]; then
    if command -v hermes >/dev/null 2>&1 && hermes skin list >/dev/null 2>&1; then HERMES_OK=yes; else HERMES_OK=no; fi
  fi
  [ "$HERMES_OK" = yes ]
}

hermes_skin_now() {  # the skin marked * in `hermes skin list`; 'default' when none is marked
  s="$(hermes skin list 2>/dev/null | sed -n 's/^\* *\([^ ]*\).*/\1/p' | head -1)"
  printf '%s\n' "${s:-default}"
}

# ── install (repo only) ──────────────────────────────────────
snapshot_v1() {  # once: the first snapshot is the original
  if [ -e "$GS/v1/.taken" ] || [ -e "$GS/v1/ghostty.config" ]; then return 0; fi
  mkdir -p "$GS/v1"
  if [ -n "$GCONF" ] && [ -f "$GCONF" ]; then
    if grep -q '^theme = light:glass-paper' "$GCONF"; then die "$GCONF already wears v2; refusing to keep it as v1"; fi
    cp -p "$GCONF" "$GS/v1/ghostty.config"
    kept="Ghostty config byte for byte"
  elif [ -n "$GCONF" ]; then
    : > "$GS/v1/ghostty.absent"
    kept="no Ghostty config, so v1 removes the one v2 writes"
  else
    kept="Ghostty not found, left alone"
  fi
  if hermes_ok; then
    skin="$(hermes_skin_now)"
    case "$skin" in glass-stage-v2*) die "active Hermes skin is '$skin'; refusing to keep it as v1" ;; esac
    printf '%s\n' "$skin" > "$GS/v1/hermes-skin"
    kept="$kept · Hermes skin '$skin'"
  fi
  : > "$GS/v1/.taken"
  say "  kept v1        $GS/v1/  ($kept)"
}

install_skin() {  # <built yaml> <installed name> <reading>
  [ "$(grep -c '^name: ' "$1")" = 1 ] || die "expected exactly one name: line in $1"
  [ "$(grep -c '^description: "THE GLASS STAGE v2 — ' "$1")" = 1 ] || die "unexpected description in $1"
  [ "$(grep -c '^  agent_name: ' "$1")" = 1 ] || die "expected exactly one agent_name: line in $1"
  who=""
  if [ -s "$GS/agent-name" ]; then
    who="$(head -n 1 "$GS/agent-name" | tr -d '"\\' | sed -e 's/[|&]/\\&/g')"
  fi
  dst="$HH/skins/$2.yaml"
  if [ -n "$who" ]; then
    sed -e "s/^name: .*/name: $2/" \
        -e "s/^description: \"THE GLASS STAGE v2 — /description: \"THE GLASS STAGE v2 · $3 — /" \
        -e "s|^  agent_name: .*|  agent_name: \"$who\"|" \
        "$1" > "$dst.tmp.$$"
  else
    sed -e "s/^name: .*/name: $2/" \
        -e "s/^description: \"THE GLASS STAGE v2 — /description: \"THE GLASS STAGE v2 · $3 — /" \
        "$1" > "$dst.tmp.$$"
  fi
  chmod 600 "$dst.tmp.$$"
  mv "$dst.tmp.$$" "$dst"
}

wire_once() {  # <file> <block>  — appended once, after a dated backup
  if grep -qF "$MARK" "$1" 2>/dev/null; then return 0; fi
  if [ -e "$1" ]; then cp -p "$1" "$1.bak.$DATE"; say "  backed up      $1.bak.$DATE"; fi
  printf '%s' "$2" >> "$1"
  say "  wired once     $1"
}

fonts() {  # the record wears the canon's two faces; without them Hermes Desktop falls back to Georgia
  missing=""
  for face in ScheherazadeNew:font-scheherazade-new RedHatMono:font-red-hat-mono; do
    ls "$HOME/Library/Fonts" /Library/Fonts 2>/dev/null | grep -qi "${face%%:*}" || missing="$missing ${face#*:}"
  done
  if [ -n "$missing" ]; then
    say "  fonts          missing:$missing  →  brew install --cask$missing  (then quit and reopen Hermes)"
  else
    say "  fonts          Scheherazade New · Red Hat Mono"
  fi
}

install_v2() {
  OUT="$HERE/out"
  { [ -d "$OUT/ghostty/themes" ] && [ -d "$OUT/hermes" ]; } || die "run install from the glass-stage repo (v2/install.sh); no built outputs next to $0"
  say "GLASS STAGE v2 — installing beside v1"
  find_ghostty
  load_gconf
  snapshot_v1

  mkdir -p "$GS/v2" "$GS/backups"
  cp "$OUT/ghostty/config"                   "$GS/v2/ghostty.config"
  cp "$OUT/git/glass-stage-literal.gitconfig" "$GS/v2/git-literal.gitconfig"
  cp "$OUT/git/glass-stage-signal.gitconfig"  "$GS/v2/git-signal.gitconfig"
  cp "$OUT/shell/prompt.zsh"                  "$GS/v2/prompt.zsh"
  if ghostty_managed; then
    printf '%s\n' "$GCONF" > "$GS/ghostty.path"
    mkdir -p "$GHX/themes"
    for t in glass-stage glass-paper glass-stage-signal glass-paper-signal; do
      cp "$OUT/ghostty/themes/$t" "$GHX/themes/$t"
    done
    say "  ghostty        4 themes → $GHX/themes/ · config → $GCONF"
  else
    say "  ghostty        not found; skipped (install Ghostty, then run this again)"
  fi
  if hermes_ok; then
    mkdir -p "$HH/skins"
    install_skin "$OUT/hermes/glass-stage.yaml"        glass-stage-v2        literal
    install_skin "$OUT/hermes/glass-stage-signal.yaml" glass-stage-v2-signal signal
    say "  hermes         glass-stage-v2 · glass-stage-v2-signal → $HH/skins/  (v1 skins untouched)"
  else
    say "  hermes         no \`hermes skin\` on PATH; skipped (update Hermes Agent, then run this again)"
  fi
  fonts
  {
    printf 'repo    %s\n' "$(cd "$HERE/.." && pwd)"
    printf 'branch  %s\n' "$(git -C "$HERE/.." branch --show-current 2>/dev/null || echo '?')"
    printf 'commit  %s\n' "$(git -C "$HERE/.." rev-parse --short HEAD 2>/dev/null || echo '?')"
    printf 'tokens  %s\n' "$(sed -n 's/.*"sha256": *"\([0-9a-f]\{12\}\).*/\1/p' "$OUT/tokens.lock.json" | head -1)"
    printf 'at      %s\n' "$DATE"
  } > "$GS/v2/SOURCE"

  wire_once "$HOME/.gitconfig" "
# $MARK v2 git colours live in this include; the file exists only while v2 is worn
[include]
	path = ~/.config/glass-stage/git.gitconfig
# <<< glass-stage v2 <<<
"
  if [ -e "$HOME/.zshrc" ] || case "${SHELL:-}" in */zsh) true ;; *) false ;; esac; then
    wire_once "$HOME/.zshrc" '
# >>> glass-stage v2 >>> the v2 prompt on Ghostty shells, only while v2 is worn
case "$TERM" in
  xterm-ghostty) [ -r "$HOME/.config/glass-stage/prompt.zsh" ] && . "$HOME/.config/glass-stage/prompt.zsh" ;;
esac
# <<< glass-stage v2 <<<
'
  else
    say "  zsh            not your shell; the prompt is skipped"
  fi

  if [ "$HERE/install.sh" != "$GS/switch.sh" ]; then
    cp "$HERE/install.sh" "$GS/switch.sh"; chmod 755 "$GS/switch.sh"
  fi
  mkdir -p "$HOME/.local/bin"
  if [ ! -e "$HOME/.local/bin/glass-stage" ] || [ "$(readlink "$HOME/.local/bin/glass-stage" 2>/dev/null || true)" = "$GS/switch.sh" ]; then
    ln -sf "$GS/switch.sh" "$HOME/.local/bin/glass-stage"
    say "  switch         glass-stage v1 | v2 | signal | status"
  else
    say "  switch         ~/.local/bin/glass-stage belongs to something else; use the full path below"
  fi
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) say "  note           ~/.local/bin is not on your PATH; add it, or use the full path below" ;;
  esac
  say "  back to v1     glass-stage v1   (always works: sh $GS/switch.sh v1)"
}

# ── wear ─────────────────────────────────────────────────────
wear() {  # v1 | literal | signal
  case "$1" in v1|literal|signal) ;; *) die "unknown reading '$1'" ;; esac
  { [ -e "$GS/v1/.taken" ] || [ -e "$GS/v1/ghostty.config" ]; } || die "nothing installed yet; run v2/install.sh from the repo"
  find_ghostty
  load_gconf
  mkdir -p "$GS/backups"

  # 1 · Ghostty first, checked before it moves: if Ghostty refuses, nothing is switched
  gnote="Ghostty: not managed"
  if ghostty_managed; then
    if [ "$1" = v1 ]; then
      if [ -f "$GCONF" ]; then cp -p "$GCONF" "$GS/backups/ghostty.$DATE"; fi
      if [ -e "$GS/v1/ghostty.absent" ]; then rm -f "$GCONF"; else cp -p "$GS/v1/ghostty.config" "$GCONF"; fi
    else
      next="$GS/ghostty.next.$$"
      if [ "$1" = signal ]; then
        sed 's/^theme = light:glass-paper,dark:glass-stage$/theme = light:glass-paper-signal,dark:glass-stage-signal/' \
          "$GS/v2/ghostty.config" > "$next"
        grep -q '^theme = light:glass-paper-signal,dark:glass-stage-signal$' "$next" \
          || { rm -f "$next"; die "could not set the signal theme pair"; }
      else
        cp "$GS/v2/ghostty.config" "$next"
      fi
      ghostty_valid "$next" || { rm -f "$next"; die "Ghostty refused the $1 config; nothing was switched"; }
      if [ -f "$GCONF" ]; then cp -p "$GCONF" "$GS/backups/ghostty.$DATE"; fi
      mkdir -p "$(dirname "$GCONF")"
      mv "$next" "$GCONF"
    fi
    gnote="Ghostty: ⌘⇧, or a new window"
  fi

  # 2 · git colours and the prompt
  skin=""
  if [ "$1" = v1 ]; then
    rm -f "$GS/git.gitconfig" "$GS/prompt.zsh"
    if [ -s "$GS/v1/hermes-skin" ]; then skin="$(cat "$GS/v1/hermes-skin")"; fi
  else
    cp "$GS/v2/git-$1.gitconfig" "$GS/git.gitconfig"
    cp "$GS/v2/prompt.zsh" "$GS/prompt.zsh"
    if [ "$1" = signal ]; then skin=glass-stage-v2-signal; else skin=glass-stage-v2; fi
  fi

  # 3 · Hermes last, and never fatal: the other surfaces are already worn
  hnote="Hermes: not managed"
  if [ -n "$skin" ] && hermes_ok; then
    if hermes skin use "$skin" >/dev/null 2>&1; then
      hnote="Hermes skin $skin · the Desktop repaints within ~1s"
    else
      hnote="Hermes would not wear '$skin'; try: hermes skin use $skin"
    fi
  fi
  printf '%s\n' "$1" > "$GS/active"
  say "  wearing        $1  ($hnote · $gnote)"
}

status() {
  find_ghostty
  load_gconf
  say "worn         $(cat "$GS/active" 2>/dev/null || echo 'v1 (never switched)')"
  if ghostty_managed; then
    say "ghostty      $(grep -m1 '^theme = ' "$GCONF" 2>/dev/null || echo 'your own colours (v1)')  · $GCONF"
  else
    say "ghostty      not managed"
  fi
  say "git          color.diff.old = $(git config --get color.diff.old 2>/dev/null || echo unset)"
  if [ -r "$GS/prompt.zsh" ]; then say "zsh prompt   v2 · op@hub on Ghostty shells"; else say "zsh prompt   stock"; fi
  if hermes_ok; then say "hermes skin  $(hermes_skin_now)"; else say "hermes skin  (no \`hermes skin\` on PATH)"; fi
}

from_repo() { [ -d "$HERE/out" ] && [ "$HERE/install.sh" != "$GS/switch.sh" ]; }

case "${1:-install}" in
  install)        install_v2; wear "${2:-literal}" ;;
  literal|signal) if from_repo; then install_v2; fi; wear "$1" ;;
  v2)             if from_repo; then install_v2; fi; wear literal ;;
  v1)             wear v1 ;;
  status)         status ;;
  -h|--help|help) sed -n '3,/^# ─/p' "$0" | sed '$d' | sed 's/^#  \{0,1\}//' ;;
  *)              die "usage: glass-stage v1 | v2 | signal | status" ;;
esac
