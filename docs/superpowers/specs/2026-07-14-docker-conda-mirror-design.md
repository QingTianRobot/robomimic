# Docker Domestic Mirrors and Local Source Build Design

## Goal

Make `docker build -t robomimic .` succeed without accepting the Anaconda default-channel Terms of Service or depending on GitHub connectivity during the build.

## Current failure

The Dockerfile downloads `Miniconda3-latest` and immediately runs `conda create`. The current Miniconda release rejects this non-interactive operation because the Dockerfile neither accepts the Anaconda default-channel Terms of Service nor replaces those channels.

After replacing the Conda channels, the build progressed to its GitHub steps. Direct GitHub access timed out, two GitHub acceleration services failed with the container's Ubuntu 20.04 Git/GnuTLS stack, and another proxy stalled during repository or archive transfer. This shows that cloning upstream repositories during every build is not reliable in the target network environment.

## Chosen approach

Keep Miniconda and the existing environment structure. Before creating `robomimic_venv`, configure Conda's `default_channels` to use the Tsinghua University mirror and set `channel_alias` so named channels such as `pytorch` resolve through the same mirror. Do not add a `conda tos accept` step.

This is preferred over accepting the Terms of Service because it matches the requested domestic-mirror policy. It is preferred over replacing Miniconda with Miniforge because it is a smaller change and preserves the existing environment layout.

Replace the GitHub clone steps with a local-source build:

1. Add `.dockerignore` so `.git`, caches, local environments, datasets, videos, and large documentation images are excluded from the Docker context.
2. Copy the current workspace into `/opt/robomimic` and install it in editable mode. The image therefore contains the exact source being built instead of an unrelated fresh clone of upstream.
3. Configure pip to use the Tsinghua University PyPI mirror.
4. Install `mujoco==3.3.7` as a binary wheel, then install `robosuite==1.5.1` from that mirror. MuJoCo 3.3.7 is the latest mirrored release with a CPython 3.9 Linux wheel; newer MuJoCo releases fall back to a source build that requires an external `MUJOCO_PATH`. Robosuite 1.5.1 is the version recommended by this repository for its current datasets.

## Scope

Modify `Dockerfile` to configure Conda and pip mirrors, copy the local robomimic source, and install `mujoco==3.3.7` with `robosuite==1.5.1`. Create `.dockerignore` to keep the build context small. Docker Hub, Ubuntu APT, the Miniconda installer, Python, PyTorch, and torchvision versions remain unchanged.

The existing GitHub clone commands and their proxy argument will be removed. No third-party GitHub proxy will remain in the production Dockerfile.

## Build and verification

The existing failed command is the pre-fix regression case:

```text
docker build -t robomimic .
```

After the Dockerfile and `.dockerignore` changes, run the same command and require a successful exit. Then verify:

1. The local image tag `robomimic` exists.
2. The container activates `robomimic_venv` successfully.
3. Python reports version 3.9.
4. `torch`, `robomimic`, and `robosuite` import successfully.
5. The installed robomimic package resolves to `/opt/robomimic`.
6. The installed MuJoCo distribution reports version 3.3.7.
7. The installed robosuite distribution reports version 1.5.1.

## Failure handling

If either Tsinghua mirror does not contain a required artifact, stop and identify the exact missing package before changing another source. The pip mirror has already been verified to publish robosuite 1.5.1. Avoid adding another GitHub proxy or unrelated dependency change without new build evidence.
