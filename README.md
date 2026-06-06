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
- **Shell:** fish on macOS/Linux, PowerShell on Windows. Prompt is starship; tmux for multiplexing; nvim (AstroNvim) as editor.
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
- macOS carries redundant tooling to consolidate when convenient: iterm2 vs ghostty, openshot-video-editor vs shotcut, dbeaver-community vs harlequin.

## Work profile

Auto-enabled on macOS (`workEnabled`). It provisions a separate work SSH key, a `~/sandbox/work` directory, and a git `includeIf` that loads `~/sandbox/work/.gitconfig` for repos cloned there. On first apply you'll be prompted (banner reprints each apply until done) to create that work gitconfig and register the work SSH public key with your git host.

## Conventions

- **Secrets:** none committed.
- **CI:** `.github/workflows/lint.yml` runs shellcheck, stylua, and `chezmoi apply --dry-run` to validate templates.

## Tooling

- [chezmoi](https://www.chezmoi.io/) — dotfiles manager
- [GitHub CLI (`gh`)](https://cli.github.com/) — auth + GitHub from the terminal
