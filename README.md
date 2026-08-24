# .dotfiles

Cross-platform configuration managed with [chezmoi](https://www.chezmoi.io/).
Configuration files — https://dotfiles.github.io

## Getting started on a new machine

```shell
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply https://github.com/varun-datt/.dotfiles.git
```

This installs chezmoi, then applies configs, installs packages, and runs setup scripts for the current OS.

## Overview

- **Manager:** [chezmoi](https://www.chezmoi.io/) ([daily ops](https://www.chezmoi.io/user-guide/daily-operations/)).
  Source root is `dotfiles/` (see `.chezmoiroot`).
- **Platforms:** macOS (Homebrew), Arch/Manjaro (pamac), Windows (Chocolatey + PowerShell).
- **Shell:** fish on macOS/Linux, PowerShell on Windows. Prompt is [starship](https://starship.rs/); terminal is [Ghostty](https://ghostty.org/); tmux for multiplexing; nvim (AstroNvim) as editor.
- **Theme:** Catppuccin **Mocha** everywhere. The palette in `dotfiles/.chezmoidata/catppuccin.yaml` is the single source of truth and is templated into tools if built-in theme is not available.

## Layout

| Path | Purpose |
| --- | --- |
| `dotfiles/dot_config/` | XDG configs |
| `dotfiles/.chezmoidata/` | Template data |
| `dotfiles/.chezmoiscripts/` | Setup/bootstrap scripts |
| `dotfiles/packages/` | Per-OS package manifests |
| `dotfiles/dot_local/bin/` | scripts deployed to `~/.local/bin` |

## Packages

Manifests in `dotfiles/packages/` (`Brewfile`, `Archfile`, `ChocoPackages.config`).
The core CLI set is kept in sync across all three on a best-effort basis.

- The Arch box omits kubernetes/cloud CLIs; those are macOS/work only.
- macOS carries redundant tooling to consolidate when convenient: dbeaver-community vs harlequin.

## Work profile

Auto-enabled on macOS (`workEnabled`, set in the chezmoi config template). It provisions a separate work SSH key, a `~/sandbox/work` directory, and a git `includeIf` that loads `~/sandbox/work/.gitconfig` for repos cloned there. On apply you'll see a banner (reprints each apply until done) with SSH public keys until you create that work gitconfig and register them with your git host.

## Agent Skills

Personal, global [Agent Skills](https://agentskills.io/) (portable `SKILL.md` workflows) managed with the [Vercel `skills` CLI](https://github.com/vercel-labs/skills). Skills are installed to the standard `~/.agents/skills/` store and symlinked into whichever agents are detected (GitHub Copilot, Cursor, Claude Code, …).

- **Manifest:** [`dotfiles/.chezmoidata/skills.yaml`](dotfiles/.chezmoidata/skills.yaml) is the single source of truth — a list of `repo` + `skills` sources. Skill folders are **not** vendored into chezmoi; only the manifest is tracked.
- **Apply:** `run_onchange_after_skills.*` renders the manifest (via [`dotfiles/.chezmoitemplates/skills-install.tmpl`](dotfiles/.chezmoitemplates/skills-install.tmpl)) into `npx skills add <repo> -s <skill> -g -y` commands, then runs `npx skills update -g -y` to pull latest. It re-runs whenever the rendered commands change. Node comes from mise.
- **On demand:** `dotfiles-deps` (in `~/.local/bin`) refreshes every dependency the dotfiles installed — system packages (brew/pamac), mise tools, fish (fisher) and tmux (tpm) plugins, the bat theme, yazi packages, and Agent Skills (`npx skills update -g -y`). To add a skill or package permanently, edit the relevant manifest and `chezmoi apply`.
- **Agents:** auto-detected by default. Pin specific agents by uncommenting `skills.agents` in the manifest (adds `-a <agent>` to each install).

## Shells & tools

- **PATH (all shells):** the PATH logic lives in one POSIX snippet, [`dotfiles/dot_config/shell/path.sh`](dotfiles/dot_config/shell/path.sh) (precedence, left wins: mise shims → `~/.local/bin` → Homebrew GNU keg `gnubin` on macOS → Homebrew → inherited). It is sourced by zsh ([`dot_zshenv`](dotfiles/dot_zshenv)), bash login ([`dot_bash_profile`](dotfiles/dot_bash_profile) → [`dot_profile`](dotfiles/dot_profile)) and non-login bash ([`dot_bashrc`](dotfiles/dot_bashrc)), so AI agents and non-interactive scripts resolve mise-managed tools without an interactive `mise activate`. Do not duplicate PATH in the rc files themselves. fish keeps its own PATH in [`config.fish.tmpl`](dotfiles/dot_config/private_fish/config.fish.tmpl) (shims outside its interactive guard) and does **not** prepend GNU `gnubin`. `~/.zshenv`/`~/.profile`/`~/.bashrc` must stay in `$HOME` (no XDG location), so keeping the real logic under `~/.config/shell/` is the XDG-friendly split.
- **GNU userland (macOS):** Homebrew’s `coreutils`, `findutils`, `gnu-sed`, `gawk`, and `grep` install unprefixed names (`date`, `sed`, `find`, `awk`, `grep`, …) under each keg’s `libexec/gnubin`. Those dirs are prepended on Darwin in `path.sh` only (bash/zsh/agents) so they get GNU flags/behavior instead of BSD `/usr/bin`. Interactive fish stays on the stock macOS/Homebrew names. Intel Homebrew (`/usr/local/opt`) is checked as well as Apple Silicon (`/opt/homebrew/opt`). Linux already is GNU; no extra PATH. Optional siblings (`gnu-tar`, `make`) are not installed unless a formula needs them.
- **rg (agents):** [`dotfiles/dot_local/bin/executable_rg`](dotfiles/dot_local/bin/executable_rg) deploys to `~/.local/bin/rg` and sits ahead of Homebrew/system ripgrep. Short `-r` is `--replace` (it rewrites matches and line numbers silently); the wrapper refuses it. `--replace` is allowed. `command rg` does not bypass a PATH shim — use `RG_GUARD_OFF=1`. Interactive fish has no extra function; it hits the same binary. The wrapper is POSIX so agent zsh/bash/`sh` all see it. Ripgrep is recursive by default; use `-F` for a fixed string.
- **Corporate TLS (e.g. Zscaler):** macOS only for the automation below. **Node:** `NODE_USE_SYSTEM_CA=1` (Node ≥ 22) reads the keychain — no custom CA file. **Python:** pipx tools that need it opt in via mise `uvx_args` + [`pip-system-certs`](https://gitlab.com/alelec/pip-system-certs) (wraps OS [`truststore`](https://github.com/sethmlarson/truststore)); a plain CA bundle fails because Zscaler’s root has non-critical basic constraints OpenSSL rejects. Tool-scoped only — arbitrary `python`/`uv run` is uncovered (revisit: global `truststore`+`sitecustomize`, or upstream system trust).
  - **Java (work + darwin):** JDK ignores the keychain → PKIX failures. `run_onchange_after_zscaler-java-cert` imports System-keychain `Zscaler Root CA` into each real mise JDK `cacerts` (`zscaler-root-ca`). Mise upgrades ship a fresh truststore, so the script must re-run — but plain `run_` always-shows in `chezmoi diff`. Fix: `run_onchange` keyed on a hash of the mise Java install list (not of `cacerts`, which the import mutates and would re-arm forever). Same-version wipe without a list change: `chezmoi state delete-bucket --bucket=scriptState`. Not for bundled IDE JREs; `KeychainStore-ROOT` is JDK 23+ only.

## Editors (VS Code / Cursor)

Settings for both editors come from a single source, [`dotfiles/.chezmoidata/editor.yaml`](dotfiles/.chezmoidata/editor.yaml): a shared `common` block plus `code`/`cursor` overrides. The `run_onchange_after_editor-settings` scripts (POSIX `sh` for macOS/Linux, PowerShell for Windows) merge them (editor-specific wins over common) and merge the result into each editor's `settings.json` under its `User` dir.

- **Paths / XDG:** VS Code and Cursor only honour XDG on Linux (`~/.config/{Code,Cursor}/User`); on macOS they use `~/Library/Application Support/…` and on Windows `%APPDATA%\…`. The scripts branch on OS instead of relying on a single path.
- **UI edits:** the scripts deep-merge the managed keys into whatever is already on disk (`jq -s '.[0] * .[1]'` on POSIX, a recursive hashtable merge in PowerShell) instead of rewriting the file, so keys the editor or an extension wrote — `mssql` connections, `workbench.*` UI state, per-language blocks — survive. Managed keys still win: because these are `run_onchange`, a UI edit to a key that `editor.yaml` owns holds until the next `editor.yaml` change, then the canonical value reasserts. The flip side is that deleting a key from `editor.yaml` no longer deletes it from disk; remove it by hand (or delete `settings.json` and re-apply). If `settings.json` cannot be parsed as strict JSON — the usual cause is `//` comments, which `jq` rejects — the script backs it up to `settings.json.bak` and writes the managed set fresh, so avoid comments in a file you want merged.
- **Auto save + local history:** `files.autoSave: afterDelay` saves ~1 s (`files.autoSaveDelay`, default 1000 ms) after typing stops. VS Code deliberately skips `editor.formatOnSave` on delay-triggered saves (the save participant returns early when the save reason is `AUTO`), so Prettier et al. only run on an explicit `⌘S` — `onFocusChange`/`onWindowChange` would keep formatting but were not chosen. `files.trimTrailingWhitespace` still runs on auto save, except on the cursor's own line. Auto save multiplies Timeline entries, so `workbench.localHistory.maxFileEntries` is raised from the default 50 to 200 (per file, oldest discarded past the cap); `workbench.localHistory.mergeWindow` (10 s) already collapses rapid same-source saves.
- **Per-machine settings:** anything host-specific or not for git (e.g. the `mssql` server connection) goes in the gitignored `.chezmoidata.yaml` under `editor.codeLocal` / `editor.cursorLocal`, which merge with the highest precedence (see `.chezmoidata.yaml.example`).
- **Agent execution:** VS Code sets `chat.agent.sandbox.enabled` to `off`. Cursor's [`sandbox.json`](dotfiles/dot_cursor/sandbox.json.tmpl) uses `workspace_readwrite` with an explicit network allowlist (currently Tavily). Cursor merges policies such that `networkPolicy.default: "deny"` wins over `"allow"`, so `"default": "allow"` alone does not open the network — add hosts under `allow` instead (or have the agent request `full_network`). Private/RFC1918 and cloud-metadata IPs stay blocked. Editor approval modes and team admin policies can still require confirmation.
- **Extensions:** managed by the `vscode "…"` lines in [`dotfiles/packages/Brewfile`](dotfiles/packages/Brewfile) (macOS; `brew bundle` resolves extension dependencies). Not yet automated for Cursor or Linux/Windows.
- **keybindings.json:** managed the same way but currently empty (`editor.keybindings: []`); populate it to deploy. Snippets are not managed (none in use).

## Conventions

- **Secrets:** none committed.
- **Per-machine data:** `dotfiles/.chezmoidata.yaml` (gitignored; see `.chezmoidata.yaml.example`).
- **CI:** `.github/workflows/lint.yml` runs shellcheck, stylua, `chezmoi apply --dry-run`, and `chezmoi doctor`.

## tmux quick reference

### tmux-fingers (link/text grabbing)

Enter fingers mode with `prefix + v`, then press a hint letter. The modifier you hold decides what happens to the selected match:

| Keys | Action |
| --- | --- |
| `<hint>` | Copy match to clipboard |
| `Ctrl + <hint>` | Copy + open in **default** browser |
| `Shift + <hint>` | Copy + paste the match |
| `Alt + <hint>` | Copy + open in **Brave** (work) |

## Git tips

- `git show :/<search-term>` — show the most recent commit whose message contains `<search-term>` (e.g. `git show :/theme`). The `:/<text>` revision syntax works anywhere a commit is expected (`git log :/fix`, `git diff :/wip`).
- `git ptag <tag> [message]` — create an annotated tag and push `refs/tags/<tag>` to `origin`. Message defaults to the tag name (so it stays non-interactive).

### Tag handling (why `fetch.pruneTags` is off)

A tag moved upstream makes any fetch carrying a `refs/tags/*` refspec exit 1, which aborts `git pull` before it merges. `fetch.pruneTags` supplies that refspec, so it stays unset. The `post-merge` hook in `git/template/hooks` force-syncs tags after a pull instead — installed via `init.templateDir`, so `git init` retrofits an existing repo. It deletes local-only tags.

- Repos with their own `post-merge`, or a `core.hooksPath` (husky and similar), never get the hook — run `git fetch --tags --force` by hand there.
- Setting `remote.origin.fetch = +refs/tags/*:refs/tags/*` globally instead would break `git clone`.

## Tooling

- [chezmoi](https://www.chezmoi.io/) — dotfiles manager
- [GitHub CLI (`gh`)](https://cli.github.com/) — auth + GitHub from the terminal
