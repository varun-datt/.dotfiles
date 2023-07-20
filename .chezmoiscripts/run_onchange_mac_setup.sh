#!/bin/sh

# Finder
defaults write com.apple.finder "AppleShowAllFiles" -bool "true"
defaults write com.apple.finder "ShowPathbar" -bool "true"
defaults write com.apple.finder "FXDefaultSearchScope" -string "SCcf" 
defaults write com.apple.finder "FXPreferredViewStyle" -string "Nlsv"
killall Finder

# Global
defaults write NSGlobalDomain "AppleShowAllExtensions" -bool "true"
defaults write NSGlobalDomain KeyRepeat -int 0
defaults write NSGlobalDomain InitialKeyRepeat -int 10

# Menu
defaults write com.apple.menuextra.clock "DateFormat" -string "\"EEE d MMM HH:mm:ss\"" 

# Dock
defaults write com.apple.dock "autohide" -bool "true" && killall Dock

