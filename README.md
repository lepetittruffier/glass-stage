```
█  █ █  █ ████      █  █ █  █ ███
█  █ █  █ █         █  █ █  █ █  █
████ ████ █ ██      ████ █  █ ███
█  █ █  █ █  █      █  █ █  █ █  █
█  █ █  █ ████      █  █ ████ ███
```

# THE GLASS STAGE

**An epoq terminal theme — one system across Ghostty, git, and Claude Code.**

The window is a glass stage (`#000000` — epoq3's true CLI black). Green is the one
live signal allowed to glow. There is **no red anywhere** — deletions, errors, and
flags read as **epoq purple** (`--signal-go`), so a `git diff` doesn't feel like an
alarm. Every ink is a live EPOQ III token. Free. Take it.

<p>
<img src="screenshots/01-banner.png" width="49%" alt="THE MUSE printed on the stage">
<img src="screenshots/03-diff.png" width="49%" alt="A no-red diff">
</p>

---

## v2: paper and stage

v2 reads every value off the live EPOQ III canon and writes one system to
Ghostty, git, the zsh prompt and the Hermes Agent skin (classic CLI, TUI and the
Desktop). Two grounds, the stage (dark) and paper (light), with Ghostty following
your system appearance; two readings, literal and signal.

```sh
brew install --cask font-scheherazade-new font-red-hat-mono
git clone https://github.com/lepetittruffier/glass-stage && cd glass-stage
sh v2/install.sh            # or: sh v2/install.sh signal
```

It installs beside v1, wears v2 straight away, and does not ask. What it touches:

- **Ghostty**, if installed. Ghostty reads up to four config files, and an explicit
  colour in any of them beats a theme. v2 is written to the one it reads last
  (`~/Library/Application Support/com.mitchellh.ghostty/config[.ghostty]` when one
  exists there, otherwise `~/.config/ghostty/config[.ghostty]`), with four theme
  files in `~/.config/ghostty/themes/`. The file it replaces is kept byte for byte
  as v1 in `~/.config/glass-stage/v1/`, or as the symlink it was. While v2 is worn,
  colour and theme lines in the other config files are held as `#glass-stage-v2: `
  comments, written through any symlink, and `glass-stage v1` lets them go. Every
  Ghostty file it rewrites is copied to `~/.config/glass-stage/backups/` first, and
  `glass-stage status` names anything another config still decides.
- **git**: one guarded include in `~/.gitconfig`, backed up first. The colours live
  in a file that exists only while v2 is worn.
- **zsh**, if it is your shell: one guarded block in `~/.zshrc`, backed up first,
  for the v2 prompt on Ghostty shells.
- **Hermes Agent**, if `hermes skin` is available: two skins, `glass-stage-v2` and
  `glass-stage-v2-signal`, in the active profile's `skins/` folder (`~/.hermes/skins/`
  unless you use profiles). The Desktop repaints within a
  second; quit and reopen it once if the text shows in Georgia. The agent is named
  THE GLASS STAGE; to name it yourself, put one line in
  `~/.config/glass-stage/agent-name` and run the install again.

Switch any time with `glass-stage v2`, `glass-stage signal`, `glass-stage v1` or
`glass-stage status` (linked into `~/.local/bin`). `glass-stage v1` puts every
surface back as it was when it first met v2, and `sh ~/.config/glass-stage/switch.sh v1`
works even when `~/.local/bin` is not on your PATH. Install Ghostty or Hermes later
and run `sh v2/install.sh` again: each joins with its own v1.

Rebuilding `v2/out` (`python3 v2/build.py`) reads the live canon and a few local
inputs, among them the Red Hat Mono font file and a Hermes Desktop build. The
committed outputs install without any of them. `bash v2/tools/install_proof.sh`
runs the installer in sandboxed homes, never your own, against your Ghostty.

---

## The palette

| ink | hex | epoq3 token · role |
|-----|-----|------|
| **signal-live** | `#2CFF05` | `--signal-live` — the live readout · cursor · additions · the pulse |
| **signal-go** | `#8E00FF` | `--signal-go` — the no-red flag · error · deletions · removed-word |
| **hum** | `#6F75D7` | `--hum` — the locator · hunk headers · warning |
| **dusk** | `#5F5295` | `--dusk` — seen / faded · selection · prompt border |
| **grey-51** | `#515151` | `--grey-51` — dim · meta · comments |
| **graphite** | `#272727` | `--graphite` — hairlines · window chrome |
| stage | `#000000` | `--ink` — the glass stage (background) |
| paper | `#FFFFFF` | `--paper` — foreground |

Type is **[Red Hat Mono](https://fonts.google.com/specimen/Red+Hat+Mono)** — the specimen mono.
The mark is **real CLI art** — epoq3 `.tui-art`: Red Hat Mono block caps, printed on the
stage, never an image.

---

## Install v1 (the July stage)

**Everything, guided (macOS):**
```sh
git clone https://github.com/lepetittruffier/glass-stage
cd glass-stage && ./install.sh
```
The installer backs up anything it touches (`*.bak.<date>`), and asks before each step.

**Or take only the parts you want:**

<details><summary><b>Ghostty</b></summary>

Copy [`ghostty/config`](ghostty/config) into `~/.config/ghostty/config`
(or merge the blocks you want). Reload with **⌘⇧,** or open a new window.
Requires Ghostty ≥ 1.2 (for `background-image`; the skin itself works on any version).
</details>

<details><summary><b>git — no-red diffs</b></summary>

```sh
sh git/glass-stage-colors.sh
```
Retunes `diff` / `status` / `log` colors globally: deletions purple, additions
green, hunks hum-blue, meta dim. Reversible — the values live in `~/.gitconfig`.
</details>

<details><summary><b>Claude Code</b></summary>

Set `"theme": "dark-ansi"` in `~/.claude/settings.json` — Claude Code then follows
your terminal's palette (this one) instead of its brand colors. To pin exact epoq
inks (green thinking-pulse, non-red diffs), drop [`claude-code/themes/epoq.json`](claude-code/themes/epoq.json)
into `~/.claude/themes/` and set `"theme": "custom:epoq"`.
</details>

<details><summary><b>THE MUSE banner + palette specimen</b></summary>

`shell/hub-banner.sh` prints THE MUSE — the ruled-G 2ch drawing in the epoq purple, pupils paper-white — on new shells; `shell/palette-specimen.sh`
shows the full palette in truecolor. Wire the banner in `~/.zshrc`:
```sh
case "$TERM" in
  xterm-ghostty) [ -r "$HOME/.config/ghostty/hub-banner.sh" ] \
     && . "$HOME/.config/ghostty/hub-banner.sh" ;;
esac
```
</details>

**The font** (any OS): install *Red Hat Mono* from Google Fonts.
macOS via Homebrew: `brew install --cask font-red-hat-mono`.

---

## Live demo

The [`demo/`](demo/) folder is a self-contained page that renders the theme in the
browser — the terminal, the HHG HUB mark, the palette, the no-red diff, in Red Hat
Mono. Deploy it to GitHub Pages (Settings → Pages → `/demo`) or open `demo/index.html`
directly.

---

## Why no red

Red is the default alarm of the terminal — and it's exhausting. THE GLASS STAGE
routes every "negative" signal (deletions, errors, flags) through **the epoq purple** (`--signal-go`)
instead: still distinct, still legible, never a jolt. One coherent palette, held
across every tool that colors your day.

## Credit & license

Designed on the **epoq** system by [Intelligence Matters](https://intelligencematters.se) / HHG.
MIT — see [LICENSE](LICENSE). Give it away, remix it, ship it.
