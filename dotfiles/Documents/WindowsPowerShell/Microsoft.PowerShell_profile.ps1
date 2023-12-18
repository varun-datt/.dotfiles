# Alias
Set-Alias -Name g -Value git
Set-Alias -Name kc -Value kubectl
Set-Alias -Name v -Value nvim

# Functions
function st { git status }
function gs { git submodule }
function gsf { git submodule foreach }

# Keymaps
Set-PSReadLineKeyHandler -Chord ctrl+w -Function BackwardDeleteWord

# Zoxide
Invoke-Expression (& {
  $hook = if ($PSVersionTable.PSVersion.Major -lt 6) { 'prompt' } else { 'pwd' }
  (zoxide init --hook $hook powershell | Out-String)
})

Invoke-Expression (&starship init powershell)
