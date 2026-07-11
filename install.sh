#!/bin/sh
# ─────────────────────────────────────────────────────────────
#  THE GLASS STAGE — installer
#  Backs up anything it touches (<file>.bak.<date>) and asks
#  before each step. Nothing is overwritten silently.
# ─────────────────────────────────────────────────────────────
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
DATE="$(date +%Y%m%d%H%M%S)"
G="$(printf '\033[38;2;44;255;5m')"; D="$(printf '\033[38;2;129;129;129m')"; R="$(printf '\033[0m')"

say()  { printf '%s%s%s\n' "$G" "$1" "$R"; }
note() { printf '%s%s%s\n' "$D" "$1" "$R"; }
ask()  { printf '%s [y/N] ' "$1"; read -r a; [ "$a" = y ] || [ "$a" = Y ]; }
backup(){ [ -e "$1" ] && cp "$1" "$1.bak.$DATE" && note "  backed up → $1.bak.$DATE" || true; }

printf '\n'; say "THE GLASS STAGE — installer"
note "an epoq terminal theme · no red · Ghostty + git + Claude Code"; printf '\n'

# 1 · font ------------------------------------------------------
if ask "1) Install Red Hat Mono (the theme font)?"; then
  if command -v brew >/dev/null 2>&1; then brew install --cask font-red-hat-mono
  else note "  no Homebrew — install Red Hat Mono from https://fonts.google.com/specimen/Red+Hat+Mono"; fi
fi

# 2 · ghostty ---------------------------------------------------
if ask "2) Install the Ghostty skin (~/.config/ghostty/config)?"; then
  mkdir -p "$HOME/.config/ghostty"
  backup "$HOME/.config/ghostty/config"
  cp "$HERE/ghostty/config"            "$HOME/.config/ghostty/config"
  cp "$HERE/shell/hub-banner.sh"       "$HOME/.config/ghostty/hub-banner.sh"
  cp "$HERE/shell/palette-specimen.sh" "$HOME/.config/ghostty/palette-specimen.sh"
  say "  ✓ skin installed — reload Ghostty with ⌘⇧, or open a new window"
fi

# 3 · git colors ------------------------------------------------
if ask "3) Apply the no-red git colors (global ~/.gitconfig)?"; then
  sh "$HERE/git/glass-stage-colors.sh"
  say "  ✓ git diff / status / log are now on-system (no red)"
fi

# 4 · claude code -----------------------------------------------
if ask "4) Install the Claude Code epoq theme?"; then
  mkdir -p "$HOME/.claude/themes"
  cp "$HERE/claude-code/themes/epoq.json" "$HOME/.claude/themes/epoq.json"
  note "  set  \"theme\": \"dark-ansi\"  (follow the palette) or  \"custom:epoq\"  (pin exact inks)"
  note "  in ~/.claude/settings.json — or run  /theme  inside Claude Code"
  say "  ✓ epoq theme available"
fi

# 5 · shell banner ----------------------------------------------
if ask "5) Print the HHG HUB banner on new Ghostty shells (adds to ~/.zshrc)?"; then
  if ! grep -q 'hub-banner.sh' "$HOME/.zshrc" 2>/dev/null; then
    backup "$HOME/.zshrc"
    {
      printf '\n# THE GLASS STAGE — HHG HUB banner on Ghostty shells\n'
      printf 'case "$TERM" in\n  xterm-ghostty) [ -r "$HOME/.config/ghostty/hub-banner.sh" ] && . "$HOME/.config/ghostty/hub-banner.sh" ;;\nesac\n'
    } >> "$HOME/.zshrc"
    say "  ✓ banner wired — open a new window to see it"
  else note "  already wired"; fi
fi

printf '\n'; say "Done."; note "the stage is set. reload Ghostty (⌘⇧,) and open a fresh window."; printf '\n'
