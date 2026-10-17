function copilot --description 'Copilot CLI with a larger skill list in interactive shells'
  if status is-interactive
    SKILL_CHAR_BUDGET=30000 command copilot $argv
  else
    command copilot $argv
  end
end
