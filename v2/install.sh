#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  GLASS STAGE v2 — install beside v1, and switch in one step
#
#    sh v2/install.sh [literal|signal]   install v2 next to v1, then wear it
#    glass-stage v2                      wear v2 · the literal reading
#    glass-stage signal                  wear v2 · the signal reading
#    glass-stage v1                      back to the July stage, exactly as it was
#    glass-stage status                  what each surface wears right now
#
#  `glass-stage` is ~/.config/glass-stage/switch.sh (linked into ~/.local/bin),
#  copied there on install so the switch outlives this worktree.
#
#  Surfaces: Ghostty (config + four theme files), git colours, the zsh prompt on
#  Ghostty shells, and the Hermes skin: classic CLI, TUI and the Desktop's
#  customCSS layer. The Desktop repaints live through skin.changed; no restart.
#
#  v1 is never edited. Its Ghostty config is kept byte-for-byte in
#  ~/.config/glass-stage/v1/, its skin stays at ~/.hermes/skins/glass-stage.yaml,
#  and ~/.gitconfig + ~/.zshrc are each touched once (backed up first) with a
#  guarded include that reads a file which only exists while v2 is worn.
#  Installed skins are renamed glass-stage-v2[-signal]; nothing else is rewritten.
# ─────────────────────────────────────────────────────────────
set -eu

GS="$HOME/.config/glass-stage"
GH="$HOME/.config/ghostty"
HH="${HERMES_HOME:-$HOME/.hermes}"
GHOSTTY="/Applications/Ghostty.app/Contents/MacOS/ghostty"
DATE="$(date +%Y%m%d%H%M%S)"
HERE="$(cd "$(dirname "$0")" && pwd)"
MARK='>>> glass-stage v2 >>>'

say() { printf '%s\n' "$*"; }
die() { printf 'glass-stage: %s\n' "$*" >&2; exit 1; }

hermes_skin_now() {
  # display.skin exactly as Hermes resolves it (marked * in `hermes skin list`)
  hermes skin list 2>/dev/null | sed -n 's/^\* *\([^ ]*\).*/\1/p' | head -1
}

# ── install (repo only) ──────────────────────────────────────
snapshot_v1() {
  [ -f "$GS/v1/ghostty.config" ] && return 0          # once; the first snapshot is the original
  [ -f "$GH/config" ] || die "no Ghostty config at $GH/config to keep as v1"
  grep -q '^theme = light:glass-paper' "$GH/config" && die "$GH/config already wears v2; refusing to keep it as v1"
  skin="$(hermes_skin_now)"
  case "$skin" in ''|glass-stage-v2*) die "active Hermes skin is '$skin'; refusing to keep it as v1" ;; esac
  mkdir -p "$GS/v1"
  cp -p "$GH/config" "$GS/v1/ghostty.config"
  printf '%s\n' "$skin" > "$GS/v1/hermes-skin"
  say "  kept v1        $GS/v1/  (Ghostty config, byte-for-byte · Hermes skin '$skin')"
}

install_skin() {  # <built yaml> <installed name> <reading>
  [ "$(grep -c '^name: ' "$1")" = 1 ] || die "expected exactly one name: line in $1"
  [ "$(grep -c '^description: "THE GLASS STAGE v2 — ' "$1")" = 1 ] || die "unexpected description in $1"
  dst="$HH/skins/$2.yaml"
  sed -e "s/^name: .*/name: $2/" \
      -e "s/^description: \"THE GLASS STAGE v2 — /description: \"THE GLASS STAGE v2 · $3 — /" \
      "$1" > "$dst.tmp.$$"
  chmod 600 "$dst.tmp.$$"
  mv "$dst.tmp.$$" "$dst"
}

wire_once() {  # <file> <block>  — appended once, after a dated backup
  grep -qF "$MARK" "$1" 2>/dev/null && return 0
  [ -e "$1" ] && cp -p "$1" "$1.bak.$DATE" && say "  backed up      $1.bak.$DATE"
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
  [ -d "$OUT/ghostty/themes" ] && [ -d "$OUT/hermes" ] || die "run install from the glass-stage repo (v2/install.sh); no built outputs next to $0"
  command -v hermes >/dev/null 2>&1 || die "hermes is not on PATH"
  say "GLASS STAGE v2 — installing beside v1"
  snapshot_v1

  mkdir -p "$GS/v2" "$GH/themes" "$HH/skins"
  cp "$OUT/ghostty/config"                   "$GS/v2/ghostty.config"
  cp "$OUT/git/glass-stage-literal.gitconfig" "$GS/v2/git-literal.gitconfig"
  cp "$OUT/git/glass-stage-signal.gitconfig"  "$GS/v2/git-signal.gitconfig"
  cp "$OUT/shell/prompt.zsh"                  "$GS/v2/prompt.zsh"
  for t in glass-stage glass-paper glass-stage-signal glass-paper-signal; do
    cp "$OUT/ghostty/themes/$t" "$GH/themes/$t"
  done
  say "  ghostty        4 themes → $GH/themes/"
  install_skin "$OUT/hermes/glass-stage.yaml"        glass-stage-v2        literal
  install_skin "$OUT/hermes/glass-stage-signal.yaml" glass-stage-v2-signal signal
  fonts
  say "  hermes         glass-stage-v2 · glass-stage-v2-signal → $HH/skins/  (v1 glass-stage untouched)"
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
  wire_once "$HOME/.zshrc" '
# >>> glass-stage v2 >>> the v2 prompt on Ghostty shells, only while v2 is worn
case "$TERM" in
  xterm-ghostty) [ -r "$HOME/.config/glass-stage/prompt.zsh" ] && . "$HOME/.config/glass-stage/prompt.zsh" ;;
esac
# <<< glass-stage v2 <<<
'

  if [ "$HERE/install.sh" != "$GS/switch.sh" ]; then
    cp "$HERE/install.sh" "$GS/switch.sh"; chmod 755 "$GS/switch.sh"
  fi
  if [ -d "$HOME/.local/bin" ]; then
    if [ ! -e "$HOME/.local/bin/glass-stage" ] || [ "$(readlink "$HOME/.local/bin/glass-stage" 2>/dev/null)" = "$GS/switch.sh" ]; then
      ln -sf "$GS/switch.sh" "$HOME/.local/bin/glass-stage"
      say "  switch         glass-stage v1 | v2 | signal | status"
    fi
  fi
}

# ── wear ─────────────────────────────────────────────────────
wear() {  # v1 | literal | signal
  [ -f "$GS/v1/ghostty.config" ] || die "nothing installed yet; run v2/install.sh from the repo"
  [ -f "$GH/config" ] && cp -p "$GH/config" "$GS/.ghostty.prev"
  case "$1" in
    v1)
      cp "$GS/v1/ghostty.config" "$GH/config"
      rm -f "$GS/git.gitconfig" "$GS/prompt.zsh"
      skin="$(cat "$GS/v1/hermes-skin")" ;;
    literal|signal)
      if [ "$1" = signal ]; then
        sed 's/^theme = light:glass-paper,dark:glass-stage$/theme = light:glass-paper-signal,dark:glass-stage-signal/' \
          "$GS/v2/ghostty.config" > "$GH/config.tmp.$$"
        grep -q '^theme = light:glass-paper-signal,dark:glass-stage-signal$' "$GH/config.tmp.$$" \
          || { rm -f "$GH/config.tmp.$$"; die "could not set the signal theme pair"; }
        skin=glass-stage-v2-signal
      else
        cp "$GS/v2/ghostty.config" "$GH/config.tmp.$$"
        skin=glass-stage-v2
      fi
      mv "$GH/config.tmp.$$" "$GH/config"
      cp "$GS/v2/git-$1.gitconfig" "$GS/git.gitconfig"
      cp "$GS/v2/prompt.zsh" "$GS/prompt.zsh" ;;
    *) die "unknown reading '$1'" ;;
  esac
  if [ -x "$GHOSTTY" ] && ! "$GHOSTTY" +validate-config >/dev/null 2>&1; then
    cp -p "$GS/.ghostty.prev" "$GH/config"
    die "Ghostty refused the new config; the previous one is back in place"
  fi
  hermes skin use "$skin" >/dev/null
  printf '%s\n' "$1" > "$GS/active"
  say "  wearing        $1  (Hermes skin $skin · Desktop repaints within ~1s · Ghostty: ⌘⇧, or a new window)"
}

status() {
  say "worn         $(cat "$GS/active" 2>/dev/null || echo 'v1 (never switched)')"
  say "ghostty      $(grep -m1 '^theme = ' "$GH/config" 2>/dev/null || echo 'inline colours (v1)')"
  say "git          color.diff.old = $(git config --get color.diff.old 2>/dev/null || echo unset)"
  say "zsh prompt   $([ -r "$GS/prompt.zsh" ] && echo 'v2 · op@hub on Ghostty shells' || echo 'stock')"
  say "hermes skin  $(hermes_skin_now)"
}

case "${1:-install}" in
  install)        install_v2; wear "${2:-literal}" ;;
  literal|signal) wear "$1" ;;
  v2)             wear literal ;;
  v1)             wear v1 ;;
  status)         status ;;
  -h|--help|help) sed -n '2,22p' "$0" | sed 's/^#  \{0,1\}//' ;;
  *)              die "usage: glass-stage v1 | v2 | signal | status" ;;
esac
