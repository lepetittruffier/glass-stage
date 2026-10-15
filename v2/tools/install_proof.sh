#!/bin/bash
# The v2 installer, exercised for real in sandboxed HOMEs: never the real one.
#
#   bash v2/tools/install_proof.sh
#
# A stub `hermes` records skin switches, so no Hermes config is ever touched.
# Ghostty is the real binary when it is installed (it validates the candidate
# configs); without it, the Ghostty checks report what the installer does then.
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
T="$(mktemp -d "${TMPDIR:-/tmp}/glass-stage-install-proof.XXXXXX")"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin"
PASS=0; FAIL=0
chk() { if eval "$2"; then PASS=$((PASS+1)); printf '    ✓ %s\n' "$1"; else FAIL=$((FAIL+1)); printf '    ✗ %s\n' "$1"; fi; }

cat > "$T/bin/hermes" <<'STUB'
#!/bin/sh
cur="$(cat "$HOME/.stub-skin" 2>/dev/null || echo default)"
case "${1:-} ${2:-}" in
  "skin list")
    for s in default $(ls "${HERMES_HOME:-$HOME/.hermes}/skins" 2>/dev/null | sed -n 's/\.yaml$//p'); do
      if [ "$s" = "$cur" ]; then echo "* $s"; else echo "  $s"; fi
    done ;;
  "skin use") echo "$3" > "$HOME/.stub-skin"; echo "use $3" >> "$HOME/.stub-log" ;;
  *) exit 2 ;;
esac
STUB
chmod 755 "$T/bin/hermes"

run() {  # <home> <shell> <with-hermes yes|no> <args...>: the repo installer
  h="$1"; s="$2"; hm="$3"; shift 3
  p=/usr/bin:/bin:/usr/sbin:/sbin; [ "$hm" = yes ] && p="$T/bin:$p"
  env -i HOME="$h" PATH="$p" SHELL="$s" LANG=en_US.UTF-8 TERM=xterm-256color sh "$REPO/v2/install.sh" "$@" > "$h.out" 2>&1
}
sw() {  # <home> <shell> <with-hermes> <args...>: the installed switch
  h="$1"; s="$2"; hm="$3"; shift 3
  p=/usr/bin:/bin:/usr/sbin:/sbin; [ "$hm" = yes ] && p="$T/bin:$p"
  env -i HOME="$h" PATH="$p" SHELL="$s" LANG=en_US.UTF-8 TERM=xterm-256color sh "$h/.config/glass-stage/switch.sh" "$@" > "$h.out" 2>&1
}
V2THEME='^theme = light:glass-paper,dark:glass-stage$'
SIGTHEME='^theme = light:glass-paper-signal,dark:glass-stage-signal$'

echo "A · fresh Mac, zsh, no Ghostty config, no ~/.local/bin, Hermes present"
A="$T/a"; mkdir -p "$A"
run "$A" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "v1 noted as no config" "[ -e '$A/.config/glass-stage/v1/ghostty.absent' ]"
chk "v2 written to ~/.config/ghostty/config" "grep -q '$V2THEME' '$A/.config/ghostty/config'"
chk "four themes installed" "[ \$(ls '$A/.config/ghostty/themes' | wc -l) -eq 4 ]"
chk "switch linked into a created ~/.local/bin" "[ \"\$(readlink '$A/.local/bin/glass-stage')\" = '$A/.config/glass-stage/switch.sh' ]"
chk "PATH note printed" "grep -q 'not on your PATH' '$A.out'"
chk "rollback path printed" "grep -q 'switch.sh v1' '$A.out'"
chk "~/.zshrc wired once" "[ \$(grep -c 'glass-stage v2 >>>' '$A/.zshrc') = 1 ]"
chk "~/.gitconfig wired once" "[ \$(grep -c 'glass-stage v2 >>>' '$A/.gitconfig') = 1 ]"
chk "skin carries THE GLASS STAGE" "grep -q 'agent_name: \"THE GLASS STAGE\"' '$A/.hermes/skins/glass-stage-v2.yaml'"
chk "Hermes asked to wear glass-stage-v2" "grep -qx 'use glass-stage-v2' '$A/.stub-log'"
sw "$A" /bin/zsh yes signal; rc=$?
chk "signal exits 0" "[ $rc = 0 ]"
chk "Ghostty on the signal pair" "grep -q '$SIGTHEME' '$A/.config/ghostty/config'"
chk "git on the signal colours" "cmp -s '$A/.config/glass-stage/git.gitconfig' '$A/.config/glass-stage/v2/git-signal.gitconfig'"
chk "Hermes asked to wear glass-stage-v2-signal" "tail -1 '$A/.stub-log' | grep -qx 'use glass-stage-v2-signal'"
sw "$A" /bin/zsh yes status; rc=$?
chk "status runs" "[ $rc = 0 ] && grep -q '^worn *signal' '$A.out'"
sw "$A" /bin/zsh yes v1; rc=$?
chk "v1 exits 0" "[ $rc = 0 ]"
chk "v1 removes the config v2 wrote" "[ ! -e '$A/.config/ghostty/config' ]"
chk "v1 removes git colours and prompt" "[ ! -e '$A/.config/glass-stage/git.gitconfig' ] && [ ! -e '$A/.config/glass-stage/prompt.zsh' ]"
chk "Hermes back on default" "tail -1 '$A/.stub-log' | grep -qx 'use default'"
chk "dated Ghostty backups kept" "[ \$(ls '$A/.config/glass-stage/backups' | wc -l) -ge 1 ]"
run "$A" /bin/zsh yes; rc=$?
chk "second install exits 0 (idempotent)" "[ $rc = 0 ]"
chk "~/.zshrc and ~/.gitconfig still wired once" "[ \$(grep -c 'glass-stage v2 >>>' '$A/.zshrc') = 1 ] && [ \$(grep -c 'glass-stage v2 >>>' '$A/.gitconfig') = 1 ]"

echo "B · bash user, no ~/.zshrc, XDG config, no Hermes at all"
B="$T/b"; mkdir -p "$B/.config/ghostty"; printf 'font-size = 13\n' > "$B/.config/ghostty/config"; cp "$B/.config/ghostty/config" "$T/b.orig"
run "$B" /bin/bash no; rc=$?
chk "install exits 0 without Hermes" "[ $rc = 0 ]"
chk "Hermes skipped, said so" "grep -q 'hermes skin. on PATH; skipped' '$B.out'"
chk "no ~/.zshrc created for a bash user" "[ ! -e '$B/.zshrc' ]"
chk "v1 kept byte for byte" "cmp -s '$B/.config/glass-stage/v1/ghostty.config' '$T/b.orig'"
chk "v2 worn in Ghostty" "grep -q '$V2THEME' '$B/.config/ghostty/config'"
sw "$B" /bin/bash no v1; rc=$?
chk "v1 restores the original byte for byte" "[ $rc = 0 ] && cmp -s '$B/.config/ghostty/config' '$T/b.orig'"

echo "C · modern config.ghostty beside a legacy config, own agent name"
C="$T/c"; mkdir -p "$C/.config/ghostty" "$C/.config/glass-stage"
printf 'theme = Dracula\n' > "$C/.config/ghostty/config.ghostty"; printf 'font-size = 15\n' > "$C/.config/ghostty/config"
cp "$C/.config/ghostty/config.ghostty" "$T/c.orig"; cp "$C/.config/ghostty/config" "$T/c.legacy"
printf 'ANY / NAME & CO\n' > "$C/.config/glass-stage/agent-name"
run "$C" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "v2 goes to config.ghostty, the file Ghostty prefers" "grep -q '$V2THEME' '$C/.config/ghostty/config.ghostty'"
chk "the lower-priority config is untouched" "cmp -s '$C/.config/ghostty/config' '$T/c.legacy'"
chk "own agent name applied, slash and ampersand intact" "grep -q 'agent_name: \"ANY / NAME & CO\"' '$C/.hermes/skins/glass-stage-v2.yaml'"
chk "the YAML still has one agent_name" "[ \$(grep -c '^  agent_name:' '$C/.hermes/skins/glass-stage-v2.yaml') = 1 ]"
sw "$C" /bin/zsh yes v1
chk "v1 restores config.ghostty byte for byte" "cmp -s '$C/.config/ghostty/config.ghostty' '$T/c.orig'"

echo "D · an install made by the previous installer"
D="$T/d"; mkdir -p "$D/.config/glass-stage/v1" "$D/.config/ghostty"
printf 'font-size = 12\n' > "$D/.config/glass-stage/v1/ghostty.config"
echo glass-stage > "$D/.config/glass-stage/v1/hermes-skin"
cp "$REPO/v2/out/ghostty/config" "$D/.config/ghostty/config"
echo glass-stage-v2 > "$D/.stub-skin"
run "$D" /bin/zsh yes; rc=$?
chk "reinstall over the old layout exits 0 (no refusal)" "[ $rc = 0 ]"
chk "managed path recorded as ~/.config/ghostty/config" "[ \"\$(cat '$D/.config/glass-stage/ghostty.path')\" = '$D/.config/ghostty/config' ]"
sw "$D" /bin/zsh yes v1
chk "v1 restores the old snapshot" "cmp -s '$D/.config/ghostty/config' '$D/.config/glass-stage/v1/ghostty.config'"
chk "Hermes back on the old v1 skin" "tail -1 '$D/.stub-log' | grep -qx 'use glass-stage'"

if [ -x /Applications/Ghostty.app/Contents/MacOS/ghostty ] || command -v ghostty >/dev/null 2>&1; then
  echo "E · Ghostty refuses a config: nothing moves"
  E="$T/e"; mkdir -p "$E"
  run "$E" /bin/zsh yes
  printf 'this-is-not-a-ghostty-key = 1\n' >> "$E/.config/glass-stage/v2/ghostty.config"
  before="$(shasum "$E/.config/ghostty/config" | cut -c1-40)"; gbefore="$(shasum "$E/.config/glass-stage/git.gitconfig" | cut -c1-40)"; lbefore="$(wc -l < "$E/.stub-log")"
  sw "$E" /bin/zsh yes signal; rc=$?
  chk "switch refuses (non-zero) and says why" "[ $rc != 0 ] && grep -q 'Ghostty refused' '$E.out'"
  chk "Ghostty config unchanged" "[ \"\$(shasum '$E/.config/ghostty/config' | cut -c1-40)\" = '$before' ]"
  chk "git colours unchanged" "[ \"\$(shasum '$E/.config/glass-stage/git.gitconfig' | cut -c1-40)\" = '$gbefore' ]"
  chk "Hermes not asked" "[ \$(wc -l < '$E/.stub-log') = $lbefore ]"
else
  echo "E · skipped: no Ghostty here to refuse a config"
fi

echo "----"
echo "install proof: PASS $PASS · FAIL $FAIL"
[ "$FAIL" = 0 ]
