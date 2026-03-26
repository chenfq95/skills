# Common Config File Paths

Reference list of common software configuration file locations by platform.

## Shell

| Software | macOS | Linux | Windows |
|----------|-------|-------|---------|
| Zsh | `~/.zshrc`, `~/.zprofile`, `~/.zshenv` | Same | N/A |
| Bash | `~/.bashrc`, `~/.bash_profile` | Same | N/A |
| Fish | `~/.config/fish/config.fish` | Same | N/A |
| PowerShell | N/A | N/A | `~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1` |
| Oh My Zsh | `~/.oh-my-zsh/custom/` | Same | N/A |
| Starship | `~/.config/starship.toml` | Same | `~/.config/starship.toml` |
| Atuin | `~/.config/atuin/config.toml` | Same | `~/.config/atuin/config.toml` |

## Git

| File | Path |
|------|------|
| Main config | `~/.gitconfig` |
| Global ignore | `~/.gitignore_global` |
| Commit template | `~/.gitmessage` |
| GitHub CLI | `~/.config/gh/` |

## Editors

| Software | macOS | Linux | Windows |
|----------|-------|-------|---------|
| Vim | `~/.vimrc`, `~/.vim/` | Same | Same |
| Neovim | `~/.config/nvim/` | Same | `~/.config/nvim/` |
| VS Code | `~/Library/Application Support/Code/User/` | `~/.config/Code/User/` | `~/AppData/Roaming/Code/User/` |
| Cursor | `~/Library/Application Support/Cursor/User/` | `~/.config/Cursor/User/` | `~/AppData/Roaming/Cursor/User/` |
| Zed | `~/Library/Application Support/Zed/` | `~/.config/zed/` | `~/AppData/Roaming/Zed/` |
| Emacs | `~/.emacs`, `~/.emacs.d/` | Same | Same |
| Sublime Text | `~/Library/Application Support/Sublime Text/Packages/User/` | `~/.config/sublime-text/Packages/User/` | `~/AppData/Roaming/Sublime Text/Packages/User/` |
| JetBrains IDEs | `~/Library/Application Support/JetBrains/<product><version>/options/` | `~/.config/JetBrains/<product><version>/options/` | `~/AppData/Roaming/JetBrains/<product><version>/options/` |

## Terminal

| Software | macOS | Linux | Windows |
|----------|-------|-------|---------|
| Tmux | `~/.tmux.conf`, `~/.tmux/` | Same | N/A |
| Alacritty | `~/.config/alacritty/` | Same | `~/.config/alacritty/` |
| Ghostty | `~/Library/Application Support/com.mitchellh.ghostty/` | `~/.config/ghostty/` | `~/AppData/Roaming/ghostty/` |
| Kitty | `~/.config/kitty/` | Same | `~/.config/kitty/` |
| WezTerm | `~/.config/wezterm/` | Same | `~/.config/wezterm/` |
| Windows Terminal | N/A | N/A | `~/AppData/Local/Microsoft/Windows Terminal/` |
| iTerm2 | `~/Library/Application Support/iTerm2/` | N/A | N/A |
| Readline | `~/.inputrc` | Same | Same |
| PowerShell 7 profile | N/A | N/A | `~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1` |
| Windows PowerShell 5 profile | N/A | N/A | `~/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1` |

## Dev Tools

| Software | macOS/Linux | Windows |
|----------|-------------|---------|
| npm | `~/.npmrc` | `~/AppData/Roaming/npm/npmrc` |
| Yarn | `~/.yarnrc` | Same |
| Cargo/Rust | `~/.cargo/config.toml` | Same |
| pip | `~/.pip/pip.conf` | `~/pip/pip.ini` |
| Poetry | `~/Library/Application Support/pypoetry/` | `~/.config/pypoetry/` | `~/AppData/Roaming/pypoetry/` |
| Pylint | `~/.pylintrc` | Same |
| Flake8 | `~/.flake8` | Same |
| ESLint | `~/.eslintrc.*` | Same |
| Prettier | `~/.prettierrc` | Same |
| EditorConfig | `~/.editorconfig` | Same |
| ASDF | `~/.tool-versions` | Same |

## Containers & Cloud

| Software | Path |
|----------|------|
| Docker | `~/.docker/` |
| Kubernetes | `~/.kube/config` |
| AWS CLI | `~/.aws/` |
| GCloud | `~/.config/gcloud/` |
| Azure | `~/.azure/` |

## Windows Notes

- Many Windows apps store settings under `AppData/Roaming` or `AppData/Local`; keep these subpaths intact in the repo instead of flattening them.
- Prefer copy-based local restore/install flows so behavior stays consistent even when symlinks are unavailable or undesirable.
- Prefer PowerShell-friendly commands in docs when the user is clearly on Windows, for example `py -3 install.py` and `winget export`.

## Cross-Platform Restore Notes

- During restore, filter out repo backups whose paths are clearly platform-specific for another OS before asking for per-software confirmation.
- Typical examples: `AppData/...` and PowerShell profile backups are Windows-only; `Library/Application Support/...` paths are macOS-only; Linux editor and terminal configs usually live under `~/.config/...`.
- Keep platform-agnostic files such as `~/.gitconfig`, `~/.editorconfig`, `~/.config/nvim/`, `~/.config/wezterm/`, and `~/.config/kitty/` eligible on every platform where the target path is valid.

## Package Managers (macOS)

| Software | Path |
|----------|------|
| Homebrew | `~/Brewfile` |
| MacPorts | `/opt/local/etc/macports/` |

## SSH & GPG

| Software | Path |
|----------|------|
| SSH config | `~/.ssh/config` (NOT private keys!) |
| GPG agent | `~/.gnupg/gpg-agent.conf` |

## Files to EXCLUDE

Never sync these files:

- `~/.ssh/id_*` — SSH private keys
- `~/.gnupg/private-keys-v1.d/` — GPG private keys
- `*.pem`, `*.key` — Private key files
- `.env` files — May contain secrets
- `~/.netrc` — May contain credentials
- `~/.local/share/keyrings/` — System keyring
- Any file containing `password`, `secret`, `token`, `api_key`
