function du --wraps=dust --description 'dust with no args, du otherwise'
  if command -q dust; and test (count $argv) -eq 0
    dust
  else
    command du $argv
  end
end
