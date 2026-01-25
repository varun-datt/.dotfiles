# Set
set -x VISUAL nvim
set -x EDITOR "$VISUAL"
set -x NODE_OPTIONS "--max_old_space_size=6144"
set -x NVM_DIR "$HOME/.nvm"
set -x NVM_SYMLINK_CURRENT true

# Fish variables
set -U __done_exclude '^(man|v|cat|g (?!push|pull|fetch))'

if status is-interactive
  # Commands to run in interactive sessions can go here
  fish_config theme choose "Catppuccin Mocha"

  if command -v zoxide &> /dev/null
    zoxide init fish | source
  end
  if command -v starship &> /dev/null
    starship init fish | source
  end
  if command -v kubectl &> /dev/null
    kubectl completion fish | source
  end
  if command -v carapace &> /dev/null
    carapace _carapace | source
  end
  if command -v atuin &> /dev/null
    atuin init fish | source
  end
end
