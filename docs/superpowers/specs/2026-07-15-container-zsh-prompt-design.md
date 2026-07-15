# Container Zsh Prompt Design

## Goal

Make the interactive robomimic container immediately distinguishable from the host terminal while preserving the existing host-mounted Oh My Zsh framework, plugin selection, Conda activation, and Git prompt information.

## Current State

Both the host and container use the `robbyrussell` Oh My Zsh theme. Its prompt starts with the same colored arrow, current directory, and Git status in both environments. After `docker compose run --rm robomimic` creates the container, the user can therefore see a blank-looking cursor or a familiar prompt without realizing that the shell is already running inside the container.

The container configuration is stored in `docker/robomimic.zshrc`. It loads the read-only host Oh My Zsh tree, enables the approved plugins, and activates `robomimic_venv`.

## Chosen Design

Keep `robbyrussell` and the existing plugins, then override the prompt at the end of the container-owned `.zshrc`. This avoids changing the host configuration or adding a second theme file inside the read-only host Oh My Zsh mount.

The interactive shell will display this structure:

```text
╭─ ROBOMIMIC CONTAINER ─────────────────────╮
│ env: robomimic_venv                       │
│ workspace: /opt/robomimic                 │
╰───────────────────────────────────────────╯

[ROBOMIMIC CONTAINER] (robomimic_venv) /opt/robomimic git:(master)
➜
```

Terminal colors will distinguish each part:

- `ROBOMIMIC CONTAINER`: bold yellow
- Conda environment: magenta
- Current path: cyan
- Successful command arrow: green
- Failed command arrow: red
- Git branch and dirty state: the existing `robbyrussell` Git colors

## Components

### Startup Banner

Add a `robomimic_banner` Zsh function to `docker/robomimic.zshrc`. It will render a compact Unicode box with the fixed container name, active Conda environment, and `/opt/robomimic` workspace path.

Call the function only when the shell is interactive and standard output is attached to a TTY. Non-interactive Compose checks and scripted commands must not receive banner output.

### Persistent Prompt

After Oh My Zsh and Conda initialization, replace `PROMPT` with a two-line prompt. The first line always includes the explicit `[ROBOMIMIC CONTAINER]` label, `robomimic_venv`, the abbreviated current directory, and `git_prompt_info`. The second line contains the success or failure arrow followed by the command input position.

The prompt will reuse the `git_prompt_info` function and Git color variables loaded by `robbyrussell`. No external prompt tool or additional package is required.

Set `CONDA_CHANGEPS1=false` before Conda initialization so later `conda activate` commands update `CONDA_DEFAULT_ENV` without prepending their own prompt modifier. Render the environment through a helper that doubles literal `%` characters before Zsh prompt expansion.

### Fallback Behavior

If the host Oh My Zsh directory is unavailable, the existing warning remains. The custom container label, Conda environment, directory, and status arrow still render; only Git prompt information may be absent. The prompt implementation will check whether `git_prompt_info` exists before calling it.

## Files

- Modify `docker/robomimic.zshrc` to add the banner function and custom prompt.
- Modify `README.md` to show the container prompt and explain that seeing the banner means the user has already entered the container.

No Dockerfile, Compose, package, mirror, GPU, or X11 changes are required.

## Verification

1. Before implementation, inspect the current `PROMPT` through a Compose Zsh command and confirm it does not contain `ROBOMIMIC CONTAINER`.
2. Rebuild the image after changing `docker/robomimic.zshrc`.
3. Run a non-interactive Zsh probe and require:
   - `PROMPT` contains `[ROBOMIMIC CONTAINER]`.
   - `PROMPT` contains `robomimic_venv`.
   - the prompt remains two lines.
   - `git_prompt_info` is available when Oh My Zsh is mounted.
   - switching to `base` and back to `robomimic_venv` does not mutate the prompt structure.
   - an environment name containing `%` renders literally rather than becoming a Zsh prompt escape.
4. Invoke `robomimic_banner` directly and require the output to contain the container name, Conda environment, and workspace.
5. Run an interactive Compose shell to visually confirm the banner and prompt render correctly.
6. Re-run the existing shell imports, NVIDIA GLFW renderer, and Lift physics smoke tests to confirm that the prompt-only change does not affect the runtime environment.
7. Confirm `MUJOCO_LOG.TXT` remains untouched and uncommitted.

## Out of Scope

- Changing the host terminal prompt or host `.zshrc`.
- Installing Powerlevel10k, Starship, Figlet, or additional fonts.
- Changing the Oh My Zsh theme or plugin list.
- Renaming the Compose service or container image.
