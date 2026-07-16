export ZSH="${ZSH:-$HOME/.oh-my-zsh}"
export ZSH_CACHE_DIR="${ZSH_CACHE_DIR:-/tmp/oh-my-zsh-cache}"
export ZSH_DISABLE_COMPFIX=true
export CONDA_CHANGEPS1=false

ZSH_THEME="robbyrussell"
plugins=(
  git
  z
  docker
  npm
  extract
  zsh-autosuggestions
  zsh-syntax-highlighting
)

if [[ -r "$ZSH/oh-my-zsh.sh" ]]; then
  source "$ZSH/oh-my-zsh.sh"
else
  print -u2 "warning: Oh My Zsh is not mounted at $ZSH"
fi

if [[ -r /opt/conda/etc/profile.d/conda.sh ]]; then
  source /opt/conda/etc/profile.d/conda.sh
  conda activate robomimic_venv
fi

if [[ -r /usr/local/share/robomimic/robomimic-functions.zsh ]]; then
  source /usr/local/share/robomimic/robomimic-functions.zsh
fi

robomimic_banner() {
  print -P '%F{yellow}%B╭─ ROBOMIMIC CONTAINER ─────────────────────╮%b%f'
  print -P '%F{yellow}%B│%b%f %F{magenta}env: robomimic_venv%f                       %F{yellow}%B│%b%f'
  print -P '%F{yellow}%B│%b%f %F{cyan}workspace: /opt/robomimic%f                 %F{yellow}%B│%b%f'
  print -P '%F{yellow}%B╰───────────────────────────────────────────╯%b%f'
}

robomimic_prompt_conda_env() {
  local env_name="${CONDA_DEFAULT_ENV:-no-conda}"
  print -r -- "${env_name//\%/%%}"
}

setopt prompt_subst
PROMPT='%F{yellow}%B[ROBOMIMIC CONTAINER]%b%f %F{magenta}($(robomimic_prompt_conda_env))%f %F{cyan}%~%f'
if (( $+functions[git_prompt_info] )); then
  PROMPT+=' $(git_prompt_info)'
fi
PROMPT+=$'\n''%(?:%F{green}➜:%F{red}➜)%f '

if [[ -o interactive && -t 1 ]]; then
  robomimic_banner
  rshelp
fi
