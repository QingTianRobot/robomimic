# Container Simulation, Training, and Rollout Shortcuts Design

## Goal

Provide a coherent set of `rs*` commands inside the robomimic container for
checking the runtime, replaying a dataset in simulation, smoke-testing and
running full training, locating checkpoints, and evaluating trained policies
in robosuite. The workflow must persist datasets, checkpoints, logs, and videos
on the host and must run on the host's NVIDIA GeForce RTX 5060 Ti.

## Scope

This design covers simulated robosuite workflows only. "Deployment" means
loading a robomimic `.pth` policy checkpoint and running rollout episodes in
the simulated environment, either offscreen to a video or interactively in an
X11 window. Real-robot and ROS deployment are outside this change.

## Host and Container Command Boundary

The host shortcut file is formally renamed from `function.zsh` to
`functions.zsh`. Host commands continue to use the `rm*` prefix and manage the
Docker lifecycle and host-side dataset download:

```text
rmrun, rmcam, rmshell, rmps, rmdataset, rmhelp
```

Container commands live in a separate file,
`docker/robomimic-functions.zsh`, and use the `rs*` prefix, defined as
"robomimic simulation":

```text
rsstatus, rsplay, rsplay-gui, rstrain, rstrain-full,
rslatest, rseval, rseval-gui, rshelp
```

The container `.zshrc` sources the container function file automatically and
prints a short command summary below the existing yellow container banner.
Docker lifecycle commands are not exposed inside the container because the
image does not need access to the host Docker socket.

All repository documentation and tests use the plural host filename
`functions.zsh` after the rename.

## GPU Runtime Upgrade

The current PyTorch 2.4.1 cu118 build supports CUDA architectures only through
`sm_90`; an actual CUDA tensor operation on the RTX 5060 Ti (`sm_120`) fails
with `no kernel image is available for execution on the device`.

The image is upgraded to:

```text
Base image: nvidia/cuda:12.8.1-base-ubuntu22.04
Python: 3.9
NumPy: 2.0.1
PyTorch: 2.7.1+cu128
torchvision: 0.22.1+cu128
```

The default domestic wheel source becomes:

```text
https://mirrors.aliyun.com/pytorch-wheels/cu128
```

The Aliyun index contains CPython 3.9 x86_64 wheels for both selected PyTorch
packages. Ubuntu 22.04 is required because these wheels use the
`manylinux_2_28` platform tag. The wheel URL remains overridable through the
existing Compose build argument mechanism.

`rsstatus` performs a real CUDA tensor calculation, rather than treating
`torch.cuda.is_available()` as sufficient. It reports the GPU name, device
capability, compiled architecture list, PyTorch/CUDA versions, and the result
of the calculation. A CUDA compatibility error exits non-zero with an action
message.

## Persistent Host Storage

Compose adds a writable bind mount:

```text
./outputs -> /opt/robomimic/outputs
```

The directory contains:

```text
outputs/
├── training/       # experiment directories, logs, checkpoints, rollout video
└── videos/         # dataset playback and explicit checkpoint evaluation video
```

`/outputs/` is excluded from Git and Docker build contexts. Before launching a
container, host `rmrun` and `rmcam` create `datasets/`, `models/huggingface/`,
and `outputs/` as the host user. This avoids Docker creating missing bind
sources as root. Container workflow functions use a permissive output umask so
the host user can remove or replace files produced by the root container.

## Training Script Extension

`robomimic/scripts/train.py` gains an optional `--output_dir` argument. When it
is supplied, it overrides `config.train.output_dir` after debug-mode defaults
are applied. This lets a smoke test keep its shortened epoch and rollout
settings while still writing into the persistent repository output mount.

Debug mode also saves a checkpoint every epoch. The two-epoch `rstrain` smoke
test therefore creates a checkpoint that can be discovered by `rslatest` and
used immediately by `rseval`.

The existing configuration and dataset arguments remain unchanged, so direct
script usage stays compatible.

## Container Commands

### `rsstatus`

Reports:

- active Conda environment;
- Python, NumPy, PyTorch, torchvision, and CUDA versions;
- GPU name and compute capability;
- compiled CUDA architectures and a real CUDA addition result;
- default dataset presence and size;
- output directory writability; and
- latest checkpoint, if one exists.

### `rsplay [dataset] [additional playback arguments]`

Defaults to:

```text
dataset: /opt/robomimic/datasets/lift/ph/low_dim_v15.hdf5
video:   /opt/robomimic/outputs/videos/dataset-playback.mp4
episodes: 1
renderer: EGL
```

It invokes `robomimic/scripts/playback_dataset.py`, using simulator states and
the `agentview` camera. A supplied first positional path replaces the dataset;
remaining arguments are forwarded to the underlying script after defaults, so
callers can override options such as `--n`, `--video_path`, or cameras.

### `rsplay-gui [dataset] [additional playback arguments]`

Uses the same default dataset, selects GLFW, and calls playback with `--render`
for one trajectory. It verifies that `DISPLAY` and the Xauthority file are
available before starting and prints the existing host-side X11 setup guidance
when they are not.

### `rstrain [additional train arguments]`

Runs a safe two-epoch GPU smoke test with:

```text
config:  robomimic/exps/templates/bc.json
dataset: datasets/lift/ph/low_dim_v15.hdf5
name:    lift-bc-smoke
output:  /opt/robomimic/outputs/training
mode:    --debug
renderer: EGL
```

Defaults appear before forwarded arguments, so explicit `--config`,
`--dataset`, `--name`, or `--output_dir` arguments supplied by the user take
precedence.

### `rstrain-full [additional train arguments]`

Uses the same BC, Lift, and output defaults without `--debug`. This starts the
template's complete training schedule and prints a warning that it is a
long-running job before execution. User arguments override the defaults.

### `rslatest`

Finds the newest `.pth` file under `/opt/robomimic/outputs` by modification
time, prints the absolute path, and returns non-zero with a concise explanation
when no checkpoint exists. Temporary and backup files remain eligible only if
they use the `.pth` suffix; the newest valid regular file wins.

### `rseval [checkpoint] [additional rollout arguments]`

Uses the first positional argument as a checkpoint when it is a `.pth` path;
otherwise it calls `rslatest`. Defaults are:

```text
rollouts: 5
seed:     0
camera:   agentview
video:    /opt/robomimic/outputs/videos/eval-<checkpoint-name>.mp4
renderer: EGL
```

It invokes `robomimic/scripts/run_trained_agent.py`. Remaining arguments are
forwarded after defaults and can override rollout count, horizon, seed, video,
camera, or output dataset options.

### `rseval-gui [checkpoint] [additional rollout arguments]`

Uses the explicit or latest checkpoint, selects GLFW, and performs one
on-screen rollout with `--render`. The same display preflight used by
`rsplay-gui` runs before policy loading.

### `rshelp`

Shows every `rs*` command, default dataset/output paths, safe smoke versus full
training behavior, and copyable examples. It is printed once when an
interactive container shell starts.

## Rendering Strategy

Headless commands set `MUJOCO_GL=egl` for predictable simulation, training
rollout video, and checkpoint evaluation without depending on X11. GUI
commands set `MUJOCO_GL=glfw` and use the Compose DISPLAY and Xauthority mounts.

No command sets both `--render` and `--video_path`, because the underlying
scripts explicitly reject that combination.

## Error Handling

Every command validates its required inputs before launching Python:

- missing default or user-supplied dataset;
- missing or empty checkpoint;
- missing output directory or inability to create it;
- missing DISPLAY/Xauthority for GUI commands;
- CUDA unavailable or incompatible;
- underlying Python command returning non-zero; or
- no checkpoint found by `rslatest`.

Errors include the failed path and a copyable recovery command. Functions
propagate the underlying process exit status and never print a success message
after a failed command.

## Testing and Verification

Automated tests cover:

- the formal `function.zsh` to `functions.zsh` rename and updated references;
- host runtime directory creation before `rmrun` and `rmcam`;
- exact cu128 dependency pins and domestic wheel source;
- `train.py --output_dir` precedence after debug defaults;
- debug checkpoint cadence;
- Compose output bind mount and ignore rules;
- container `.zshrc` sourcing the container function library;
- command discovery and `rshelp` output;
- default and user-overridden command construction;
- latest-checkpoint selection and missing-checkpoint errors;
- EGL versus GLFW selection;
- GUI display preflight;
- actual CUDA tensor execution on the RTX 5060 Ti;
- dataset playback producing an MP4;
- GPU smoke training producing a `.pth` checkpoint; and
- headless checkpoint rollout producing an evaluation MP4.

Final verification compares files through both host and container paths,
checks that outputs are ignored by Git, and leaves the downloaded dataset and
generated workflow artifacts on the host for immediate reuse.
