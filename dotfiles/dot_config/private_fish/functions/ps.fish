function ps --wraps=procs --description 'alias ps=procs'
  if test (count $argv) -eq 0
    procs
  else
    command ps $argv
  end
end
