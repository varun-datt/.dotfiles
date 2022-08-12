# Alias
Set-Alias -Name g -Value git

# Functions
function st { git status }

# Keymaps
Set-PSReadLineKeyHandler -Chord ctrl+w -Function BackwardDeleteWord

# Zoxide
Invoke-Expression (& {
  $hook = if ($PSVersionTable.PSVersion.Major -lt 6) { 'prompt' } else { 'pwd' }
  (zoxide init --hook $hook powershell | Out-String)
})

