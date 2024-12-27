function lpf --wraps="lpass show" --description "lpass-find: find lpass entry"
  lpass ls | fzf | sed -r "s|.*?id: (.+)]|\1|" | xargs -I{} lpass show {} $argv
end
