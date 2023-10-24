#!/bin/sh

# load fish history file

git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm

git clone --depth 1 https://github.com/AstroNvim/AstroNvim ~/.config/nvim

fisher update
