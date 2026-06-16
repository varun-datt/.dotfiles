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

Auto-enabled on macOS (`workEnabled`). Override per machine with [`dotfiles/.chezmoidata.local.yaml`](dotfiles/.chezmoidata.local.yaml.example) (copy from the example; gitignored). It provisions a separate work SSH key, a `~/sandbox/work` directory, and a git `includeIf` that loads `~/sandbox/work/.gitconfig` for repos cloned there. On apply you'll see a banner (reprints each apply until done) with SSH public keys until you create that work gitconfig and register them with your git host.

## Agent Skills

Personal, global [Agent Skills](https://agentskills.io/) (portable `SKILL.md` workflows) managed with the [Vercel `skills` CLI](https://github.com/vercel-labs/skills). Skills are installed to the standard `~/.agents/skills/` store and symlinked into whichever agents are detected (GitHub Copilot, Cursor, Claude Code, …).

- **Manifest:** [`dotfiles/.chezmoidata/skills.yaml`](dotfiles/.chezmoidata/skills.yaml) is the single source of truth — a list of `repo` + `skills` sources. Skill folders are **not** vendored into chezmoi; only the manifest is tracked.
- **Apply:** `run_onchange_after_skills.*` renders the manifest (via [`dotfiles/.chezmoitemplates/skills-install.tmpl`](dotfiles/.chezmoitemplates/skills-install.tmpl)) into `npx skills add <repo> -s <skill> -g -y` commands, then runs `npx skills update -g -y` to pull latest. It re-runs whenever the rendered commands change. Node comes from mise.
- **On demand:** `dotfiles-deps` (in `~/.local/bin`) refreshes every dependency the dotfiles installed — system packages (brew/pamac), mise tools, fish (fisher) and tmux (tpm) plugins, the bat theme, yazi packages, and Agent Skills (`npx skills update -g -y`). To add a skill or package permanently, edit the relevant manifest and `chezmoi apply`.
- **Agents:** auto-detected by default. Pin specific agents by uncommenting `skills.agents` in the manifest (adds `-a <agent>` to each install).

## Shells & tools

- **Default shell (zsh):** [`dotfiles/dot_zshenv`](dotfiles/dot_zshenv) prepends `~/.local/bin` and the mise shims dir to `PATH` for **every** zsh invocation. This is what AI agents and non-interactive scripts use, so mise-managed tools resolve without an interactive `mise activate`. fish gets the same shims outside its interactive guard.
- **Corporate TLS (e.g. Zscaler):** on macOS behind a TLS-intercepting proxy, both runtimes verify against the macOS keychain. **Node** gets `NODE_USE_SYSTEM_CA=1` (Node ≥ 22) exported from the shells, which makes `node`/`npm`/`npx` read the keychain directly — no CA file or custom script. **Python** has no built-in switch, so each pipx CLI that needs it bundles [`pip-system-certs`](https://gitlab.com/alelec/pip-system-certs) into its own venv via mise `uvx_args`. Its `.pth` auto-activates inside the venv (it wraps the same OS-native [`truststore`](https://github.com/sethmlarson/truststore)), so there is **no** custom script, `PYTHONPATH`, or `sitecustomize` glue. This works because a CA bundle alone fails — the Zscaler root has non-critical basic constraints that OpenSSL rejects.
  - **Trade-off (revisit later):** this is **tool-scoped** — it only covers pipx CLIs that explicitly opt in (add the same `--with pip-system-certs` per tool). Arbitrary `python …` / `uv run` scripts behind the proxy are **not** covered. If a future need arises for system-wide Python trust, research the alternatives again: a global `truststore` on `PYTHONPATH` + `sitecustomize.py` (previous approach, machine-local artifact, covers all Python), or Python gaining native system-trust upstream.

## Conventions

- **Secrets:** none committed.
- **Per-machine data:** `dotfiles/.chezmoidata.local.yaml` (gitignored; see `.chezmoidata.local.yaml.example`).
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

## Tooling

- [chezmoi](https://www.chezmoi.io/) — dotfiles manager
- [GitHub CLI (`gh`)](https://cli.github.com/) — auth + GitHub from the terminal
