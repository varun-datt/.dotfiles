# Shared PATH for all shells (sourced from zshenv, profile, bashrc).

_path_prepend() {
  case ":${PATH}:" in
    *":$1:"*) ;;
    *) PATH="$1${PATH:+:$PATH}" ;;
  esac
}

for _b in /usr/local/sbin /usr/local/bin /opt/homebrew/sbin /opt/homebrew/bin; do
  [ -d "$_b" ] && _path_prepend "$_b"
done
unset _b

if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
  for _prefix in /opt/homebrew /usr/local; do
    for _gnu in coreutils findutils gnu-sed gawk grep; do
      _gnubin="$_prefix/opt/$_gnu/libexec/gnubin"
      [ -d "$_gnubin" ] && _path_prepend "$_gnubin"
    done
  done
  unset _prefix _gnu _gnubin
fi

[ -d "$HOME/.local/bin" ] && _path_prepend "$HOME/.local/bin"

_mise_shims="${MISE_DATA_DIR:-$HOME/.local/share/mise}/shims"
[ -d "$_mise_shims" ] && _path_prepend "$_mise_shims"
unset _mise_shims

export PATH
unset -f _path_prepend

if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
  export NODE_USE_SYSTEM_CA=1
fi
