# Docker Conda Mirror Build Design

## Goal

Make `docker build -t robomimic .` succeed without accepting the Anaconda default-channel Terms of Service, while preferring a domestic mirror for Conda downloads.

## Current failure

The Dockerfile downloads `Miniconda3-latest` and immediately runs `conda create`. The current Miniconda release rejects this non-interactive operation because the Dockerfile neither accepts the Anaconda default-channel Terms of Service nor replaces those channels.

## Chosen approach

Keep Miniconda and the existing image structure. Before creating `robomimic_venv`, configure Conda's `default_channels` to use the Tsinghua University mirror and set `channel_alias` so named channels such as `pytorch` resolve through the same mirror. Do not add a `conda tos accept` step.

This is preferred over accepting the Terms of Service because it matches the requested domestic-mirror policy. It is preferred over replacing Miniconda with Miniforge because it is a smaller change and preserves the existing environment layout.

## Scope

Only the Conda channel configuration in `Dockerfile` will change initially. Docker Hub, Ubuntu APT, Miniconda installer, GitHub, and pip URLs remain unchanged. If a later build step proves slow or unavailable, that source will be handled separately using evidence from the build log.

## Build and verification

The existing failed command is the pre-fix regression case:

```text
docker build -t robomimic .
```

After the Dockerfile change, run the same command and require a successful exit. Then verify:

1. The local image tag `robomimic` exists.
2. The container activates `robomimic_venv` successfully.
3. Python reports version 3.9.
4. `torch`, `robomimic`, and `robosuite` import successfully.

## Failure handling

If the Tsinghua mirror does not contain a required package or channel, stop and identify the exact missing artifact before changing another source. Avoid bundling unrelated mirror, dependency, or version changes into the same fix.
