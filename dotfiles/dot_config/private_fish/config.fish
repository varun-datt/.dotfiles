# Set
set -x VISUAL nvim
set -x EDITOR "$VISUAL"
set -x NODE_OPTIONS "--max_old_space_size=6144"
set -x NVM_SYMLINK_CURRENT true
set fish_color_command --bold

if status is-interactive
  # Commands to run in interactive sessions can go here

  if command -v zoxide &> /dev/null
    zoxide init fish | source
  end
  if command -v starship &> /dev/null
    starship init fish | source
  end
end
