# Set
set -x VISUAL nvim
set -x EDITOR "$VISUAL"

if status is-interactive
  # Commands to run in interactive sessions can go here
  if command -v starship &> /dev/null
    starship init fish | source
  end
end
