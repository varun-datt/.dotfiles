# Defined in - @ line 1
function st --wraps='git status' --description 'alias st=git status'
  git status $argv;
end
