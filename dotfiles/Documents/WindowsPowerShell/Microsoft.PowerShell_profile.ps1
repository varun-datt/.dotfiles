# Alias
Set-Alias -Name g -Value git
Set-Alias -Name kc -Value kubectl
Set-Alias -Name kns -Value kubens
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

# Import the Chocolatey Profile that contains the necessary code to enable
# tab-completions to function for `choco`.
# Be aware that if you are missing these lines from your profile, tab completion
# for `choco` will not function.
# See https://ch0.co/tab-completion for details.
$ChocolateyProfile = "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
if (Test-Path($ChocolateyProfile)) {
  Import-Module "$ChocolateyProfile"
}
