function cat --wraps=bat --description 'bat when viewing in a terminal, cat otherwise'
  if command -q bat; and isatty stdout
    bat $argv
  else
    command cat $argv
  end
end
