#!/bin/bash
# The v2 installer, exercised for real in sandboxed homes: never the real one.
#
#   bash v2/tools/install_proof.sh
#
# Every run gets its own HOME and CFFIXED_USER_HOME, so Ghostty's Application
# Support folder is the sandbox's too. A stub `hermes` records skin switches, so
# no Hermes config is ever touched. Ghostty is the real binary when it is
# installed: it validates the candidate configs and, through +show-config, says
# what a sandbox finally wears. Without Ghostty those checks are skipped.
set -u
REPO="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
T="$(mktemp -d "${TMPDIR:-/tmp}/glass-stage-install-proof.XXXXXX")"
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT
mkdir -p "$T/bin"
PASS=0; FAIL=0; SKIP=0
AS='Library/Application Support/com.mitchellh.ghostty'
CR="$(printf '\r')"
GBIN=""
for g in /Applications/Ghostty.app/Contents/MacOS/ghostty "$HOME/Applications/Ghostty.app/Contents/MacOS/ghostty"; do
  if [ -x "$g" ]; then GBIN="$g"; break; fi
done
[ -n "$GBIN" ] || GBIN="$(command -v ghostty 2>/dev/null || true)"

chk()  { if eval "$2"; then PASS=$((PASS+1)); printf '    ✓ %s\n' "$1"; else FAIL=$((FAIL+1)); printf '    ✗ %s\n' "$1"; fi; }
gchk() { if [ -n "$GBIN" ]; then chk "$@"; else SKIP=$((SKIP+1)); printf '    – %s (no Ghostty here)\n' "$1"; fi; }

cat > "$T/bin/hermes" <<'STUB'
#!/bin/sh
hh="${HERMES_HOME:-$HOME/.hermes}"
if [ -s "$HOME/.stub-profile" ]; then hh="$HOME/.hermes/profiles/$(cat "$HOME/.stub-profile")"; fi
cur="$(cat "$HOME/.stub-skin" 2>/dev/null || echo default)"
case "${1:-} ${2:-}" in
  "skin list")
    for s in default mono $(ls "$hh/skins" 2>/dev/null | sed -n 's/\.yaml$//p'); do
      if [ "$s" = "$cur" ]; then echo "* $s"; else echo "  $s"; fi
    done ;;
  "skin use")
    case "$3" in default|mono) ;; *) [ -f "$hh/skins/$3.yaml" ] || { echo "no skin '$3'" >&2; exit 1; } ;; esac
    echo "$3" > "$HOME/.stub-skin"; echo "use $3" >> "$HOME/.stub-log" ;;
  "config path") echo "$hh/config.yaml" ;;
  *) exit 2 ;;
esac
STUB
chmod 755 "$T/bin/hermes"

go() {  # <home> <shell> <with-hermes yes|no> <script> <args...>: one sandboxed run, output in <home>.out
  local h="$1" s="$2" hm="$3" sc="$4" p=/usr/bin:/bin:/usr/sbin:/sbin
  shift 4
  [ "$hm" = yes ] && p="$T/bin:$p"
  # shellcheck disable=SC2086  # EXTRA is a list of NAME=value words
  env -i HOME="$h" CFFIXED_USER_HOME="$h" PATH="$p" SHELL="$s" TMPDIR="${TMPDIR:-/tmp}" \
    LANG=en_US.UTF-8 TERM=xterm-256color ${EXTRA:-} sh "$sc" "$@" > "$h.out" 2>&1
}
run() { local h="$1" s="$2" hm="$3"; shift 3; go "$h" "$s" "$hm" "$REPO/v2/install.sh" "$@"; }
sw()  { local h="$1" s="$2" hm="$3"; shift 3; go "$h" "$s" "$hm" "$h/.config/glass-stage/switch.sh" "$@"; }
gsc() { env -i HOME="$1" CFFIXED_USER_HOME="$1" PATH=/usr/bin:/bin "$GBIN" +show-config 2>/dev/null; }
hexbg() { sed -n 's/^background = #\{0,1\}//p' | tr 'A-F' 'a-f'; }
on_v2_ground() { local b; b="$(gsc "$1" | hexbg)"; [ -n "$b" ] && { [ "$b" = "$BG_STAGE" ] || [ "$b" = "$BG_PAPER" ]; }; }
V2THEME='^theme = light:glass-paper,dark:glass-stage$'
SIGTHEME='^theme = light:glass-paper-signal,dark:glass-stage-signal$'
BG_STAGE="$(hexbg < "$REPO/v2/out/ghostty/themes/glass-stage")"
BG_PAPER="$(hexbg < "$REPO/v2/out/ghostty/themes/glass-paper")"

echo "A · fresh Mac, zsh, no Ghostty config, no ~/.local/bin, Hermes present"
A="$T/a"; mkdir -p "$A"
run "$A" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "v1 noted as no config" "[ -e '$A/.config/glass-stage/v1/ghostty.absent' ]"
chk "v2 written to ~/.config/ghostty/config" "grep -q '$V2THEME' '$A/.config/ghostty/config'"
chk "four themes installed" "[ \$(ls '$A/.config/ghostty/themes' | wc -l) -eq 4 ]"
gchk "Ghostty wears v2's ground, Red Hat Mono first" "on_v2_ground '$A' && [ \"\$(gsc '$A' | grep -m1 '^font-family = ')\" = 'font-family = Red Hat Mono' ]"
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
chk "v2 goes to config.ghostty, the file Ghostty reads last" "grep -q '$V2THEME' '$C/.config/ghostty/config.ghostty'"
chk "the earlier config, with no colour lines, is untouched" "cmp -s '$C/.config/ghostty/config' '$T/c.legacy'"
chk "own agent name applied, slash and ampersand intact" "grep -q 'agent_name: \"ANY / NAME & CO\"' '$C/.hermes/skins/glass-stage-v2.yaml'"
chk "the YAML still has one agent_name" "[ \$(grep -c '^  agent_name:' '$C/.hermes/skins/glass-stage-v2.yaml') = 1 ]"
sw "$C" /bin/zsh yes v1
chk "v1 restores config.ghostty byte for byte" "cmp -s '$C/.config/ghostty/config.ghostty' '$T/c.orig'"

echo "D · an install made by the previous installer"
D="$T/d"; mkdir -p "$D/.config/glass-stage/v1" "$D/.config/ghostty"
printf 'font-size = 12\n' > "$D/.config/glass-stage/v1/ghostty.config"
echo glass-stage > "$D/.config/glass-stage/v1/hermes-skin"
cp "$REPO/v2/out/ghostty/config" "$D/.config/ghostty/config"
mkdir -p "$D/.hermes/skins"; : > "$D/.hermes/skins/glass-stage.yaml"
echo glass-stage-v2 > "$D/.stub-skin"
run "$D" /bin/zsh yes; rc=$?
chk "reinstall over the old layout exits 0 (no refusal)" "[ $rc = 0 ]"
chk "managed path recorded as ~/.config/ghostty/config" "[ \"\$(cat '$D/.config/glass-stage/ghostty.path')\" = '$D/.config/ghostty/config' ]"
chk "the v1 it already kept is not re-taken" "[ \"\$(cat '$D/.config/glass-stage/v1/hermes-skin')\" = glass-stage ]"
sw "$D" /bin/zsh yes v1
chk "v1 restores the old snapshot" "cmp -s '$D/.config/ghostty/config' '$D/.config/glass-stage/v1/ghostty.config'"
chk "Hermes back on the old v1 skin" "tail -1 '$D/.stub-log' | grep -qx 'use glass-stage'"

if [ -n "$GBIN" ]; then
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

echo "F · the common macOS layout: v1 colours inline in ~/.config/ghostty/config, an empty App Support config.ghostty"
F="$T/f"; mkdir -p "$F/.config/ghostty" "$F/$AS"
printf 'font-family = Menlo\nbackground = 123456\nforeground = abcdef\npalette = 1=#654321\ntheme = Dracula\nkeybind = ctrl+a=select_all\n' > "$F/.config/ghostty/config"
: > "$F/$AS/config.ghostty"
cp "$F/.config/ghostty/config" "$T/f.xdg"; cp "$F/$AS/config.ghostty" "$T/f.as"
run "$F" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "v2 goes into the file Ghostty reads last" "grep -q '$V2THEME' '$F/$AS/config.ghostty'"
chk "four colour and theme lines held in ~/.config/ghostty/config" "[ \$(grep -c '^#glass-stage-v2: ' '$F/.config/ghostty/config') = 4 ]"
chk "the rest of that file stays as it was" "grep -q '^keybind = ctrl+a=select_all' '$F/.config/ghostty/config' && grep -q '^font-family = Menlo' '$F/.config/ghostty/config'"
chk "the held file was copied to backups/ first" "ls '$F/.config/glass-stage/backups' | grep -q '^ghostty\.config\.[0-9]'"
gchk "Ghostty wears v2's ground" "on_v2_ground '$F'"
gchk "none of v1's colours survive" "! gsc '$F' | grep -qiE '123456|abcdef|1=#654321'"
gchk "Red Hat Mono leads, Menlo cleared" "[ \"\$(gsc '$F' | grep '^font-family = ')\" = 'font-family = Red Hat Mono' ]"
gchk "nothing else decides, and the installer says nothing of it" "! grep -q 'still decided' '$F.out'"
sw "$F" /bin/zsh yes status
chk "status names the held file" "grep -qF 'holding colour lines in $F/.config/ghostty/config' '$F.out'"
sw "$F" /bin/zsh yes signal; rc=$?
chk "signal holds nothing twice" "[ $rc = 0 ] && [ \$(grep -c '^#glass-stage-v2: ' '$F/.config/ghostty/config') = 4 ] && ! grep -q 'glass-stage-v2: #glass-stage-v2' '$F/.config/ghostty/config'"
sw "$F" /bin/zsh yes v1; rc=$?
chk "v1 exits 0" "[ $rc = 0 ]"
chk "v1 lets the held lines go, byte for byte" "cmp -s '$F/.config/ghostty/config' '$T/f.xdg'"
chk "v1 puts the App Support file back as it was" "cmp -s '$F/$AS/config.ghostty' '$T/f.as'"
gchk "Ghostty back on v1's colours" "gsc '$F' | grep -qi '^background = #123456'"

echo "G · a dotfiles symlink as the config: v2 never writes into the dotfiles, v1 restores the link"
G="$T/g"; mkdir -p "$G/dotfiles" "$G/.config/ghostty"
printf 'font-size = 13\nbackground = 0a0a0a\n' > "$G/dotfiles/ghostty"; cp "$G/dotfiles/ghostty" "$T/g.dot"
ln -s "$G/dotfiles/ghostty" "$G/.config/ghostty/config"
run "$G" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "v1 kept as the link it was" "[ \"\$(cat '$G/.config/glass-stage/v1/ghostty.link')\" = '$G/dotfiles/ghostty' ]"
chk "v2 worn in Ghostty" "grep -q '$V2THEME' '$G/.config/ghostty/config'"
chk "the dotfiles file is untouched" "cmp -s '$G/dotfiles/ghostty' '$T/g.dot'"
sw "$G" /bin/zsh yes v1; rc=$?
chk "v1 restores the same link" "[ $rc = 0 ] && [ -L '$G/.config/ghostty/config' ] && [ \"\$(readlink '$G/.config/ghostty/config')\" = '$G/dotfiles/ghostty' ]"
chk "the dotfiles file is still untouched" "cmp -s '$G/dotfiles/ghostty' '$T/g.dot'"

echo "H · a dotfiles symlink beside an empty App Support config.ghostty: held through the link"
H="$T/h"; mkdir -p "$H/dotfiles" "$H/.config/ghostty" "$H/$AS"
printf 'background = 123456\nfont-size = 12\n' > "$H/dotfiles/ghostty"; cp "$H/dotfiles/ghostty" "$T/h.dot"
ln -s "$H/dotfiles/ghostty" "$H/.config/ghostty/config"; : > "$H/$AS/config.ghostty"
run "$H" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "the link stays a link" "[ -L '$H/.config/ghostty/config' ]"
chk "its colour line held in the dotfiles file" "grep -q '^#glass-stage-v2: background = 123456' '$H/dotfiles/ghostty'"
gchk "Ghostty wears v2's ground" "on_v2_ground '$H'"
sw "$H" /bin/zsh yes v1; rc=$?
chk "v1: still a link, the dotfiles file byte for byte" "[ $rc = 0 ] && [ -L '$H/.config/ghostty/config' ] && cmp -s '$H/dotfiles/ghostty' '$T/h.dot'"

echo "I · a read-only config (a store link, as Nix leaves it): never aborts, says what still decides"
I="$T/i"; mkdir -p "$I/store" "$I/.config/ghostty" "$I/$AS"
printf 'background = 123456\n' > "$I/store/ghostty"; chmod 444 "$I/store/ghostty"; chmod 555 "$I/store"
ln -s "$I/store/ghostty" "$I/.config/ghostty/config"; : > "$I/$AS/config.ghostty"
run "$I" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "says the file is read-only" "grep -q 'is read-only: its 1 colour line(s) still beat' '$I.out'"
gchk "names what still decides" "grep -q 'still decided by another config: .*background' '$I.out'"
sw "$I" /bin/zsh yes status
gchk "status names it too" "grep -q 'still decided by another config: .*background' '$I.out'"
sw "$I" /bin/zsh yes v1; rc=$?
chk "v1 exits 0" "[ $rc = 0 ]"

echo "J · Hermes arrives after the first install: it joins with its own v1"
J="$T/j"; mkdir -p "$J"
run "$J" /bin/zsh no
echo mono > "$J/.stub-skin"
run "$J" /bin/zsh yes; rc=$?
chk "re-install exits 0" "[ $rc = 0 ]"
chk "v1 now keeps Hermes skin 'mono'" "[ \"\$(cat '$J/.config/glass-stage/v1/hermes-skin')\" = mono ]"
chk "Hermes wears v2" "grep -qx 'use glass-stage-v2' '$J/.stub-log'"
sw "$J" /bin/zsh yes v1
chk "v1 puts Hermes back on mono" "tail -1 '$J/.stub-log' | grep -qx 'use mono'"

if [ -n "$GBIN" ]; then
  echo "K · Ghostty arrives after the first install: it joins with its own v1"
  K="$T/k"; RK="$T/repo-k/v2"; mkdir -p "$K" "$RK"
  cp -R "$REPO/v2/out" "$RK/out"
  sed 's|/Applications/Ghostty.app|/nonexistent/Ghostty.app|' "$REPO/v2/install.sh" > "$RK/install.sh"
  go "$K" /bin/zsh yes "$RK/install.sh"; rc=$?
  chk "first install without Ghostty exits 0 and says how it joins" "[ $rc = 0 ] && grep -q 'not found; skipped' '$K.out'"
  mkdir -p "$K/Applications/Ghostty.app/Contents/MacOS"
  printf '#!/bin/sh\nexec "%s" "$@"\n' "$GBIN" > "$K/Applications/Ghostty.app/Contents/MacOS/ghostty"
  chmod 755 "$K/Applications/Ghostty.app/Contents/MacOS/ghostty"
  go "$K" /bin/zsh yes "$RK/install.sh"; rc=$?
  chk "re-install brings Ghostty in" "[ $rc = 0 ] && grep -q '$V2THEME' '$K/.config/ghostty/config'"
  chk "with its v1 kept (no config before)" "[ -e '$K/.config/glass-stage/v1/ghostty.absent' ]"
  sw "$K" /bin/zsh yes v1
  chk "v1 takes that config away again" "[ ! -e '$K/.config/ghostty/config' ]"
else
  echo "K · skipped: no Ghostty here"
fi

echo "L · rough edges: an exported CDPATH, 'install v2', a CRLF agent-name, help"
L="$T/l"; mkdir -p "$L/.config/glass-stage"; printf 'WIN NAME\r\n' > "$L/.config/glass-stage/agent-name"
EXTRA="CDPATH=.:$T" run "$L" /bin/zsh yes install v2; rc=$?
chk "an exported CDPATH and 'install v2' both work, wearing literal" "[ $rc = 0 ] && grep -q 'wearing  *literal' '$L.out'"
chk "a CRLF agent-name leaves no CR in the skin" "! LC_ALL=C grep -q \"\$CR\" '$L/.hermes/skins/glass-stage-v2.yaml'"
chk "and the name itself is there" "grep -q 'agent_name: \"WIN NAME\"' '$L/.hermes/skins/glass-stage-v2.yaml'"
sw "$L" /bin/zsh yes help
chk "help prints no bare '#'" "! grep -qx '#' '$L.out' && grep -q 'GLASS STAGE v2' '$L.out'"

echo "M · Hermes on a sticky profile: the skins go where hermes reads them"
M="$T/m"; mkdir -p "$M"; echo work > "$M/.stub-profile"
run "$M" /bin/zsh yes; rc=$?
chk "install exits 0" "[ $rc = 0 ]"
chk "skins land in the active profile's home" "[ -f '$M/.hermes/profiles/work/skins/glass-stage-v2.yaml' ] && [ ! -e '$M/.hermes/skins/glass-stage-v2.yaml' ]"
chk "and Hermes wears them" "grep -qx 'use glass-stage-v2' '$M/.stub-log'"

if [ -n "$GBIN" ]; then
  echo "O · Ghostty's +show-config gives nothing: the installer says it could not check"
  O="$T/o"; RO="$T/repo-o/v2"; mkdir -p "$O/Applications/Ghostty.app/Contents/MacOS" "$RO"
  cp -R "$REPO/v2/out" "$RO/out"
  sed 's|/Applications/Ghostty.app|/nonexistent/Ghostty.app|' "$REPO/v2/install.sh" > "$RO/install.sh"
  printf '#!/bin/sh\ncase "$1" in +show-config) exit 0 ;; esac\nexec "%s" "$@"\n' "$GBIN" > "$O/Applications/Ghostty.app/Contents/MacOS/ghostty"
  chmod 755 "$O/Applications/Ghostty.app/Contents/MacOS/ghostty"
  go "$O" /bin/zsh yes "$RO/install.sh"; rc=$?
  chk "install exits 0 and says it could not check" "[ $rc = 0 ] && grep -q 'could not check what Ghostty finally wears' '$O.out'"
  sw "$O" /bin/zsh yes status
  chk "status says so too" "grep -q 'could not check what Ghostty finally wears' '$O.out'"
else
  echo "O · skipped: no Ghostty here"
fi

echo "N · the held keys cover every key the v2 themes set"
sed -n 's/^\([a-z-]*\) *=.*/\1/p' "$REPO"/v2/out/ghostty/themes/* | sort -u > "$T/theme-keys"
sed -n "s/^HOLDKEYS='\(.*\)'\$/\1/p" "$REPO/v2/install.sh" | tr '|' '\n' | sort -u > "$T/hold-keys"
chk "none missing" "[ -s '$T/hold-keys' ] && [ -z \"\$(comm -23 '$T/theme-keys' '$T/hold-keys')\" ]"

echo "----"
echo "install proof: PASS $PASS · FAIL $FAIL · SKIP $SKIP${GBIN:+ · Ghostty $("$GBIN" +version 2>/dev/null | sed -n 's/^ *- *version: *//p; s/^Ghostty *//p' | head -1)}"
[ "$FAIL" = 0 ]
