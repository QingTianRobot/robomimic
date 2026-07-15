# Container Zsh Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unmistakable robomimic container banner and persistent two-line Zsh prompt without changing the host shell configuration or installing another prompt framework.

**Architecture:** Extend the existing container-owned `docker/robomimic.zshrc` after Oh My Zsh and Conda initialization. A TTY-only banner announces the container once at startup, while a custom prompt continuously displays the container name, active Conda environment, current path, Git state, and previous-command status.

**Tech Stack:** Zsh prompt expansion, Oh My Zsh `robbyrussell` Git helpers, Docker Compose, Bash/Zsh smoke tests.

---

## File Structure

- Modify `docker/robomimic.zshrc`: define `robomimic_banner`, add its TTY guard, and replace `PROMPT` with the container-specific two-line prompt.
- Modify `README.md`: show the expected banner and explain that it confirms entry into the container.

### Task 1: Add the banner and persistent container prompt

**Files:**
- Modify: `docker/robomimic.zshrc`
- Modify: `README.md`

- [ ] **Step 1: Run the missing-prompt regression test**

Run:

```bash
docker compose run --rm -T robomimic /usr/bin/zsh -lic 'print -r -- "$PROMPT"' | rg -F '[ROBOMIMIC CONTAINER]'
```

Expected: FAIL because the current `robbyrussell` prompt does not contain the container label.

- [ ] **Step 2: Run the missing-documentation regression test**

Run:

```bash
rg -n 'ROBOMIMIC CONTAINER|already inside the container' README.md
```

Expected: FAIL because the README does not show or explain a container-specific prompt.

- [ ] **Step 3: Disable Conda prompt rewriting**

Add this line after `export ZSH_DISABLE_COMPFIX=true` in `docker/robomimic.zshrc`:

```zsh
export CONDA_CHANGEPS1=false
```

- [ ] **Step 4: Add the container banner and prompt**

Append this exact block after the Conda initialization block in `docker/robomimic.zshrc`:

```zsh
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
fi
```

- [ ] **Step 5: Document the visible entry indicator**

Insert this block immediately after the `docker compose run --rm robomimic` command in `README.md`:

````markdown
A successful interactive startup displays a container-specific banner and prompt:

```text
╭─ ROBOMIMIC CONTAINER ─────────────────────╮
│ env: robomimic_venv                       │
│ workspace: /opt/robomimic                 │
╰───────────────────────────────────────────╯

[ROBOMIMIC CONTAINER] (robomimic_venv) /opt/robomimic git:(master)
➜
```

Seeing `[ROBOMIMIC CONTAINER]` means the shell is already inside the container; type commands directly, and use `exit` or `Ctrl+D` to return to the host.
````

- [ ] **Step 6: Validate Zsh and documentation syntax before building**

Run:

```bash
zsh -n docker/robomimic.zshrc
rg -n 'ROBOMIMIC CONTAINER|already inside the container|Ctrl\+D' README.md
git diff --check
```

Expected: PASS with prompt and README matches and no whitespace errors.

- [ ] **Step 7: Build the final image once**

Run:

```bash
env -u DISPLAY -u XAUTHORITY docker compose build
```

Expected: PASS and rebuild `robomimic:latest` without requiring graphical environment variables.

- [ ] **Step 8: Verify the prompt structure and banner function**

Run:

```bash
docker compose run --rm -T robomimic /usr/bin/zsh -lic '
  [[ "$PROMPT" == *"[ROBOMIMIC CONTAINER]"* ]] || exit 1
  [[ "$PROMPT" == *"robomimic_prompt_conda_env"* ]] || exit 1
  prompt_lines=("${(@f)PROMPT}")
  (( ${#prompt_lines} == 2 )) || exit 1
  (( $+functions[git_prompt_info] )) || exit 1
  (( $+functions[robomimic_banner] )) || exit 1
  banner="$(robomimic_banner)"
  [[ "$banner" == *"ROBOMIMIC CONTAINER"* ]] || exit 1
  [[ "$banner" == *"robomimic_venv"* ]] || exit 1
  [[ "$banner" == *"/opt/robomimic"* ]] || exit 1
  print prompt-banner-ok
'
```

Expected: PASS and print `prompt-banner-ok`.

- [ ] **Step 9: Verify Conda switching does not mutate the prompt**

Run:

```bash
docker compose run --rm -T robomimic /usr/bin/zsh -lic '
  initial="$PROMPT"
  conda activate base
  [[ "$PROMPT" == "$initial" ]] || exit 1
  conda activate robomimic_venv
  [[ "$PROMPT" == "$initial" ]] || exit 1
  CONDA_DEFAULT_ENV="%n"
  rendered="$(print -P "$PROMPT")"
  [[ "$rendered" == *"(%n)"* ]] || exit 1
  print conda-prompt-ok
'
```

Expected: PASS and print `conda-prompt-ok` without a duplicate `(base)` or `(robomimic_venv)` prefix.

- [ ] **Step 10: Verify that non-TTY scripted shells do not print the banner automatically**

Run:

```bash
output=$(docker compose run --rm -T robomimic /usr/bin/zsh -lic 'print non-tty-ok' 2>&1)
printf '%s\n' "$output"
if printf '%s\n' "$output" | rg -q '╭─ ROBOMIMIC CONTAINER'; then exit 1; fi
```

Expected: PASS, print `non-tty-ok`, and contain no startup banner.

- [ ] **Step 11: Commit the prompt and documentation**

```bash
git add docker/robomimic.zshrc README.md
git commit -m "feat: distinguish the container zsh prompt"
```

### Task 2: Run final runtime regressions and review

**Files:**
- Test: `docker/robomimic.zshrc`
- Test: `compose.yaml`
- Test: `Dockerfile`
- Test: `README.md`

- [ ] **Step 1: Verify Shell, Oh My Zsh, Conda, and imports**

Run:

```bash
output=$(docker compose run --rm -T robomimic /usr/bin/zsh -lic '
  [[ "$CONDA_DEFAULT_ENV" == "robomimic_venv" ]] || exit 1
  [[ "$ZSH" == "/root/.oh-my-zsh" ]] || exit 1
  whence -w _git
  python -c "import mujoco, robomimic, robosuite, torch; print(\"shell-imports-ok\")"
' 2>&1)
printf '%s\n' "$output"
if printf '%s\n' "$output" | rg -q 'Insecure completion-dependent directories'; then exit 1; fi
```

Expected: PASS, `_git` remains a function, and print `shell-imports-ok` without the compfix warning.

- [ ] **Step 2: Verify read-only X11 and NVIDIA rendering**

Run:

```bash
docker compose run --rm -T robomimic /bin/bash -lc 'mount | grep " /tmp/.X11-unix " | grep -q "(ro[,)]" && python -c "import glfw; from OpenGL.GL import GL_RENDERER, glGetString; assert glfw.init(); glfw.window_hint(glfw.VISIBLE, glfw.FALSE); window = glfw.create_window(64, 64, \"probe\", None, None); assert window; glfw.make_context_current(window); renderer = glGetString(GL_RENDERER); assert renderer is not None; renderer = renderer.decode(); print(renderer); assert \"NVIDIA\" in renderer; glfw.destroy_window(window); glfw.terminate()"'
```

Expected: PASS and print the NVIDIA renderer.

- [ ] **Step 3: Verify Lift physics**

Run:

```bash
docker compose run --rm -T -e MUJOCO_GL=osmesa robomimic python -c "import numpy as np, robosuite as suite; env=suite.make(env_name='Lift', robots='Panda', has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False); env.reset(); low, high = env.action_spec; [env.step(np.zeros_like(low)) for _ in range(20)]; print('simulation-ok', env.action_dim); env.close()"
```

Expected: PASS and print `simulation-ok 7`.

- [ ] **Step 4: Review repository state**

Run:

```bash
docker build --check .
git diff --check
git status --short --branch
git log -6 --oneline --decorate
```

Expected: Dockerfile check reports no warnings; `master` contains the prompt implementation commit; `MUJOCO_LOG.TXT` remains the only unrelated untracked file.
