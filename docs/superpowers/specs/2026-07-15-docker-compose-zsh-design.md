# Docker Compose and Host Oh My Zsh Design

## Goal

Provide a one-command Docker Compose development workflow for this repository. The default command must open an interactive Zsh shell with the `robomimic_venv` Conda environment active, preserve the verified NVIDIA/X11 rendering path, and reuse the host's Oh My Zsh installation without importing host-only paths that would break the container environment.

## Current State

The existing image is based on CUDA 11.8 and Ubuntu 20.04. It installs Miniconda, Python 3.9, CPU PyTorch 2.0.0, MuJoCo 3.3.7, robosuite 1.5.1, and the local robomimic source. Conda and pip already use Tsinghua University mirrors. The default command currently activates `robomimic_venv` and starts Bash.

GPU-backed GLFW rendering has been verified when the container receives all NVIDIA devices, the NVIDIA graphics and display driver capabilities, the host X11 socket, and the host Xauthority cookie.

The host has `~/.oh-my-zsh` with the `robbyrussell` theme and these enabled plugins:

- `git`
- `z`
- `docker`
- `npm`
- `extract`
- `zsh-autosuggestions`
- `zsh-syntax-highlighting`

The host `~/.zshrc` also contains absolute paths for its own Conda, Julia, ROS, local binaries, and datasets. Those unrelated host paths must not be sourced inside the container.

## Architecture

### Docker Image

Append the Zsh-specific installation and configuration near the bottom of the existing Dockerfile so the established Python and robomimic dependency layers retain their cache behavior.

The new layer will:

1. Configure `https://mirrors.tuna.tsinghua.edu.cn/ubuntu/` as the Ubuntu APT mirror for the new package installation.
2. Install `zsh` without recommended packages.
3. Copy a container-specific Zsh configuration into the image.
4. Copy an entrypoint that activates `robomimic_venv` before executing the requested command.
5. Make Zsh the image's default interactive command.

The container-specific `.zshrc` will point `ZSH` at `/root/.oh-my-zsh`, select the host's current `robbyrussell` theme, enable the same seven Oh My Zsh plugins, and use a writable cache directory outside the read-only Oh My Zsh mount. It will not source the host's complete `.zshrc`.

The existing Tsinghua Conda and PyPI mirror configuration remains unchanged. The new APT operation will use the Tsinghua Ubuntu mirror. Base-image download behavior remains controlled by the host Docker daemon and cannot be changed reliably from inside the Dockerfile.

### Docker Compose Service

Create one `robomimic` service in `compose.yaml` with these responsibilities:

- Build the current repository as `robomimic:latest`.
- Allocate all available NVIDIA GPUs with Compose's `gpus: all` setting.
- Set `NVIDIA_DRIVER_CAPABILITIES=all`, matching the verified NVIDIA OpenGL launch configuration.
- Forward `DISPLAY`, the read-only X11 Unix socket, and the host Xauthority cookie when the desktop session provides them.
- Bind-mount the repository at `/opt/robomimic`, matching the editable install path already recorded in the Conda environment.
- Bind-mount `${HOME}/.oh-my-zsh` at `/root/.oh-my-zsh` as read-only, using long bind syntax with `create_host_path: false`.
- Allocate a TTY and keep standard input open.
- Use `/opt/robomimic` as the working directory.
- Start an interactive login Zsh shell by default.

The normal entry command will be:

```bash
docker compose run --rm robomimic
```

The runtime mount keeps repository edits immediately visible to the editable robomimic installation. The Oh My Zsh mount keeps the host's framework, bundled plugins, custom plugins, and custom themes available without copying personal files into the image.

### Host Configuration Boundary

Only `~/.oh-my-zsh` is mounted from the host. The complete host `~/.zshrc` is deliberately excluded because it refers to host-only absolute paths and software that the image does not install.

The container-owned `.zshrc` mirrors only the current Oh My Zsh theme and plugin selection. If that selection later changes on the host, the versioned container `.zshrc` must be updated explicitly. This trade-off favors deterministic startup and a valid Conda environment over automatically executing arbitrary host shell initialization.

Because the read-only host tree is owned by the host UID rather than container root, the container configuration disables Oh My Zsh's `compfix` ownership warning. The read-only bind prevents the container from changing the mounted framework or plugins.

## Failure Handling

Compose configuration and image builds must work without desktop variables. An unset `DISPLAY` becomes an empty value and an unset `XAUTHORITY` uses `/dev/null` as a harmless read-only placeholder. The README will state that graphical use still requires a local Linux desktop session, NVIDIA Container Toolkit, a populated `DISPLAY`, and a populated `XAUTHORITY`. The Oh My Zsh bind continues to use `create_host_path: false`, so a missing host installation fails when the service starts instead of creating an empty directory.

The service runs as root. The README will warn that files created inside the writable repository bind can become root-owned on the host.

The entrypoint will stop if Conda initialization or environment activation fails. It will forward signals by replacing itself with the requested command. The Zsh configuration will only source Oh My Zsh when its main script exists, allowing a direct `docker run` shell to remain usable even when the host directory is not mounted.

CPU-only and headless robomimic commands remain possible by overriding Compose GPU or rendering settings, but a separate CPU service is outside this change's scope.

## Documentation

Replace the minimal Docker instructions in `README.md` with:

- Image build instructions.
- The default one-command Compose shell workflow.
- Host requirements for NVIDIA/X11/Xauthority and Oh My Zsh.
- A command for launching the robosuite random-action demo from the Compose shell.
- A short explanation that repository edits are live while the Oh My Zsh mount is read-only.

## Verification

Verification will cover configuration, image contents, shell startup, Python dependencies, and graphics:

1. Before implementation, confirm `docker compose config` fails because `compose.yaml` does not exist.
2. Validate Dockerfile syntax with `docker build --check .`.
3. Validate Compose interpolation and schema with `docker compose config`.
4. Build `robomimic:latest` through Compose.
5. Run a non-interactive Compose shell probe that asserts:
   - Zsh is installed.
   - `ZSH` points to the mounted host Oh My Zsh directory.
   - the configured theme and plugin list load.
   - `CONDA_DEFAULT_ENV` is `robomimic_venv`.
   - Python imports `robomimic`, `robosuite`, `mujoco`, and `torch`.
6. Run a hidden GLFW context probe through Compose and require the renderer to report the host NVIDIA GPU rather than `nvidia-drm` loader errors.
7. Review the final Git diff and confirm the unrelated `MUJOCO_LOG.TXT` remains untouched and uncommitted.

## Files

- Modify `Dockerfile` to install and select Zsh near the bottom.
- Create `compose.yaml` for the GPU/X11 interactive development service.
- Create `docker/robomimic-entrypoint.sh` for Conda activation and command execution.
- Create `docker/robomimic.zshrc` for deterministic Oh My Zsh setup.
- Modify `README.md` with build and run instructions.

## Out of Scope

- Copying personal shell files into the image.
- Installing host-only Conda, ROS, Julia, NVM, Neovim, or local CLI tools.
- Changing robomimic, robosuite, MuJoCo, Python, PyTorch, or CUDA versions.
- Adding a second CPU-only Compose service.
- Changing the host Docker daemon's registry mirror configuration.
