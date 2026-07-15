export ZSH="${ZSH:-$HOME/.oh-my-zsh}"
export ZSH_CACHE_DIR="${ZSH_CACHE_DIR:-/tmp/oh-my-zsh-cache}"
export ZSH_DISABLE_COMPFIX=true

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
