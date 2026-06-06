function df --wraps=duf --description 'duf with no args, df otherwise'
  if command -q duf; and test (count $argv) -eq 0
    duf
  else
    command df $argv
  end
end
