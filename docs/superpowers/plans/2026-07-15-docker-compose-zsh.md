# Docker Compose and Host Oh My Zsh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-command GPU/X11 Docker Compose development shell that activates `robomimic_venv`, runs Zsh, and reuses the host Oh My Zsh installation with a deterministic container configuration.

**Architecture:** A single Compose service builds and runs `robomimic:latest`, forwards NVIDIA graphics and X11 authorization, and mounts the repository over the editable install path. The Docker image appends a domestic-mirror Zsh layer, a Conda-aware entrypoint, and a container-owned `.zshrc` that uses the host's read-only Oh My Zsh tree without sourcing host-only shell paths.

**Tech Stack:** Dockerfile, Docker Compose v5, Ubuntu 20.04, NVIDIA Container Toolkit, X11/Xauthority, Miniconda, Zsh, Oh My Zsh, Bash smoke tests.

---

## File Structure

- Create `compose.yaml`: define the interactive GPU/X11 development service and runtime bind mounts.
- Create `docker/robomimic-entrypoint.sh`: activate `robomimic_venv` for every container command and forward signals with `exec`.
- Create `docker/robomimic.zshrc`: load the host Oh My Zsh tree with the approved theme and plugin set, then initialize Conda for interactive use.
- Modify `Dockerfile`: install Zsh through the Tsinghua Ubuntu mirror near the bottom and select the new entrypoint and default shell.
- Modify `README.md`: document prerequisites, one-command startup, and the robosuite GUI demo.

### Task 1: Add the Compose service

**Files:**
- Create: `compose.yaml`

- [ ] **Step 1: Run the missing-Compose regression test**

Run:

```bash
docker compose config
```

Expected: FAIL because the repository has no Compose configuration file.

- [ ] **Step 2: Create the Compose service**

Create `compose.yaml` with exactly:

```yaml
name: robomimic

services:
  robomimic:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}
        UBUNTU_APT_MIRROR: ${UBUNTU_APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/ubuntu}
    image: robomimic:latest
    gpus: all
    shm_size: 2gb
    environment:
      DISPLAY: ${DISPLAY:-}
      XAUTHORITY: /tmp/.docker.xauth
      MUJOCO_GL: glfw
      NVIDIA_DRIVER_CAPABILITIES: all
      ZSH_CACHE_DIR: /tmp/oh-my-zsh-cache
    volumes:
      - type: bind
        source: .
        target: /opt/robomimic
      - type: bind
        source: /tmp/.X11-unix
        target: /tmp/.X11-unix
        read_only: true
        bind:
          create_host_path: false
      - type: bind
        source: ${XAUTHORITY:-/dev/null}
        target: /tmp/.docker.xauth
        read_only: true
        bind:
          create_host_path: false
      - type: bind
        source: ${HOME:-/root}/.oh-my-zsh
        target: /root/.oh-my-zsh
        read_only: true
        bind:
          create_host_path: false
    working_dir: /opt/robomimic
    stdin_open: true
    tty: true
    command: ["/usr/bin/zsh", "-l"]
```

- [ ] **Step 3: Validate Compose interpolation and schema**

Run:

```bash
docker compose config --quiet
```

Expected: PASS with exit code 0 both in the desktop session and when `DISPLAY` and `XAUTHORITY` are unset for an image-only build.

- [ ] **Step 4: Commit the Compose service**

```bash
git add compose.yaml
git commit -m "feat: add compose development service"
```

### Task 2: Install and configure Zsh

**Files:**
- Create: `docker/robomimic-entrypoint.sh`
- Create: `docker/robomimic.zshrc`
- Modify: `Dockerfile`

- [ ] **Step 1: Run the missing-Zsh regression test against the current image**

Run:

```bash
docker run --rm robomimic:latest /usr/bin/zsh --version
```

Expected: FAIL because `/usr/bin/zsh` is not present in the current image.

- [ ] **Step 2: Create the Conda-aware entrypoint**

Create `docker/robomimic-entrypoint.sh` with exactly:

```bash
#!/usr/bin/env bash
set -euo pipefail

source /opt/conda/etc/profile.d/conda.sh
conda activate robomimic_venv

exec "$@"
```

- [ ] **Step 3: Create the deterministic Oh My Zsh configuration**

Create `docker/robomimic.zshrc` with exactly:

```zsh
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
```

- [ ] **Step 4: Append the Zsh layer and replace the default command**

Replace the final Bash `CMD` in `Dockerfile` with:

```dockerfile
# Install Zsh through a domestic Ubuntu mirror near the end to preserve existing build cache
ARG UBUNTU_APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu
RUN sed -i \
        -e "s|http://archive.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" \
        -e "s|http://security.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" \
        /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends zsh && \
    rm -rf /var/lib/apt/lists/*

COPY docker/robomimic-entrypoint.sh /usr/local/bin/robomimic-entrypoint
COPY docker/robomimic.zshrc /root/.zshrc
RUN chmod 0755 /usr/local/bin/robomimic-entrypoint && \
    mkdir -p /tmp/oh-my-zsh-cache

ENV SHELL=/usr/bin/zsh \
    ZSH=/root/.oh-my-zsh \
    ZSH_CACHE_DIR=/tmp/oh-my-zsh-cache

ENTRYPOINT ["/usr/local/bin/robomimic-entrypoint"]
CMD ["/usr/bin/zsh", "-l"]
```

- [ ] **Step 5: Validate Dockerfile syntax**

Run:

```bash
docker build --check .
```

Expected: PASS without Dockerfile syntax or undefined-variable errors.

- [ ] **Step 6: Build the updated image through Compose**

Run:

```bash
docker compose build
```

Expected: PASS and tag the result as `robomimic:latest`; the new APT output uses `mirrors.tuna.tsinghua.edu.cn` for Zsh installation.

- [ ] **Step 7: Verify Zsh, Oh My Zsh, Conda, and Python imports**

Run:

```bash
docker compose run --rm -T robomimic /usr/bin/zsh -lic '
  [[ "$CONDA_DEFAULT_ENV" == "robomimic_venv" ]] || exit 1
  [[ "$ZSH" == "/root/.oh-my-zsh" ]] || exit 1
  [[ "$ZSH_THEME" == "robbyrussell" ]] || exit 1
  [[ " ${plugins[*]} " == *" zsh-autosuggestions "* ]] || exit 1
  [[ " ${plugins[*]} " == *" zsh-syntax-highlighting "* ]] || exit 1
  python -c "import mujoco, robomimic, robosuite, torch; print(\"shell-imports-ok\")"
'
```

Expected: PASS and print `shell-imports-ok`.

- [ ] **Step 8: Commit the image and shell configuration**

```bash
git add Dockerfile docker/robomimic-entrypoint.sh docker/robomimic.zshrc
git commit -m "feat: add zsh compose environment"
```

### Task 3: Document the one-command workflow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run the missing-documentation regression test**

Run:

```bash
rg -n 'docker compose run --rm robomimic' README.md
```

Expected: FAIL because the Compose command is not documented yet.

- [ ] **Step 2: Replace the README Docker section**

Replace the existing `## Docker` section with:

````markdown
## Docker

The Docker image provides Python 3.9, Miniconda, robosuite, MuJoCo, PyTorch, Zsh, and a Compose-based GPU/X11 development shell. Conda, pip, and the additional Zsh installation use domestic mirrors where available.

Build the image:

```bash
docker compose build
```

The graphical Compose workflow requires:

- Linux with a local X11 or Xwayland desktop session
- NVIDIA Container Toolkit
- `DISPLAY` and `XAUTHORITY` exported by the desktop session
- Oh My Zsh installed at `${HOME}/.oh-my-zsh`

These graphical variables are not required to build the image, but they must be present before starting a GUI application from the container.

Open the repository in an interactive Zsh shell with `robomimic_venv` activated:

```bash
docker compose run --rm robomimic
```

The repository is bind-mounted at `/opt/robomimic`, so local source edits are immediately visible to the editable installation. The host Oh My Zsh directory is mounted read-only; the container uses the same `robbyrussell` theme and plugin selection without sourcing host-only Conda, ROS, Julia, or local-tool paths.

The development container runs as root. Files created under the bind-mounted repository, such as training outputs or caches, can therefore become root-owned on the host.

From the Compose shell, launch the robosuite random-action GUI demo:

```bash
python /opt/conda/envs/robomimic_venv/lib/python3.9/site-packages/robosuite/demos/demo_random_action.py
```

For a direct image build without Compose:

```bash
docker build -t robomimic .
```
````

- [ ] **Step 3: Verify the new instructions are discoverable**

Run:

```bash
rg -n 'docker compose build|docker compose run --rm robomimic|demo_random_action.py|XAUTHORITY|\.oh-my-zsh' README.md
```

Expected: PASS and print matches for all build, startup, GUI, Xauthority, and Oh My Zsh instructions.

- [ ] **Step 4: Commit the documentation**

```bash
git add README.md
git commit -m "docs: explain compose zsh workflow"
```

### Task 4: Verify GPU rendering and final repository state

**Files:**
- Test: `compose.yaml`
- Test: `Dockerfile`
- Test: `docker/robomimic-entrypoint.sh`
- Test: `docker/robomimic.zshrc`
- Test: `README.md`

- [ ] **Step 1: Verify the resolved Compose service**

Run:

```bash
docker compose config
```

Expected: the resolved service contains `gpus: all`, `NVIDIA_DRIVER_CAPABILITIES: all`, `MUJOCO_GL: glfw`, a read-only `/tmp/.X11-unix` mount, the Xauthority file mount, the repository mount, and the read-only Oh My Zsh mount.

- [ ] **Step 2: Verify a hidden NVIDIA GLFW context**

Run:

```bash
docker compose run --rm -T robomimic python -c "import glfw; from OpenGL.GL import GL_RENDERER, glGetString; assert glfw.init(); glfw.window_hint(glfw.VISIBLE, glfw.FALSE); window = glfw.create_window(64, 64, 'probe', None, None); assert window; glfw.make_context_current(window); renderer = glGetString(GL_RENDERER); assert renderer is not None; renderer = renderer.decode(); print(renderer); assert 'NVIDIA' in renderer; glfw.destroy_window(window); glfw.terminate()"
```

Expected: PASS and print `NVIDIA GeForce RTX 5060 Ti/PCIe/SSE2` without `failed to load driver: nvidia-drm`.

- [ ] **Step 3: Verify the Lift physics simulation**

Run:

```bash
docker compose run --rm -T -e MUJOCO_GL=osmesa robomimic python -c "import numpy as np, robosuite as suite; env=suite.make(env_name='Lift', robots='Panda', has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False); env.reset(); low, high = env.action_spec; [env.step(np.zeros_like(low)) for _ in range(20)]; print('simulation-ok', env.action_dim); env.close()"
```

Expected: PASS and print `simulation-ok 7`.

- [ ] **Step 4: Review changes and preserve unrelated state**

Run:

```bash
git diff --check
git status --short --branch
git log -5 --oneline --decorate
```

Expected: no whitespace errors; `master` contains the Compose, Zsh, and README commits; `MUJOCO_LOG.TXT` remains the only unrelated untracked file.
