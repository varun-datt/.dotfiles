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

## Tooling

- [chezmoi](https://www.chezmoi.io/) — dotfiles manager
- [GitHub CLI (`gh`)](https://cli.github.com/) — auth + GitHub from the terminal
