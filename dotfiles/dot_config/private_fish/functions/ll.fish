# Defined in - @ line 1
function ll --wraps=lsd --description 'alias ll=lsd'
  lsd -lhrtA $argv
end
