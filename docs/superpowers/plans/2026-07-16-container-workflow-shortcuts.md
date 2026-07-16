# Container Simulation, Training, and Rollout Shortcuts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the image for RTX 5060 Ti GPU support and add persistent, tested `rs*` container commands for dataset playback, smoke/full training, checkpoint discovery, and simulated policy rollout.

**Architecture:** Host-only Docker lifecycle functions remain in the renamed `functions.zsh`; container workflow functions live in `docker/robomimic-functions.zsh` and are sourced by the container `.zshrc`. A small train CLI helper applies debug and output overrides predictably, while Compose persists `datasets`, Hugging Face models, and generated `outputs` through explicit bind mounts.

**Tech Stack:** Docker, Docker Compose, NVIDIA CUDA 12.8, PyTorch 2.7.1 cu128, Python 3.9, NumPy 2.0.1, robosuite/MuJoCo, Zsh, pytest.

---

## File Structure

- Rename and modify `function.zsh` to `functions.zsh`: host Docker commands and bind-source preparation.
- Modify `tests/test_dataset_download_function.py`: use the plural host filename and verify runtime directories.
- Modify `README.md`: document the plural source command and host/container command boundary.
- Modify `docs/superpowers/specs/2026-07-16-dataset-host-download-design.md`: update the host filename in the earlier dataset design.
- Modify `docs/superpowers/plans/2026-07-16-host-dataset-download.md`: update the host filename in the earlier dataset plan.
- Modify `Dockerfile`: CUDA 12.8 / cu128 stack and installation of container functions.
- Modify `compose.yaml`: cu128 wheel source and persistent outputs mount.
- Modify `tests/test_docker_ml_stack.py`: exact CUDA/PyTorch architecture contract.
- Create `robomimic/utils/train_cli_utils.py`: deterministic CLI override application.
- Modify `robomimic/scripts/train.py`: expose `--output_dir` and use the helper.
- Create `tests/test_train_cli_utils.py`: debug and output override behavior.
- Modify `.gitignore` and `.dockerignore`: ignore persistent outputs.
- Create `tests/test_output_volume_config.py`: output mount and ignore contracts.
- Create `docker/robomimic-functions.zsh`: `rs*` command implementation.
- Modify `docker/robomimic.zshrc`: source and announce container commands.
- Create `tests/test_container_workflow_functions.py`: command construction, renderer, checkpoint, and error tests.

### Task 1: Formalize the Host Shortcut Rename and Runtime Directories

**Files:**
- Rename: `function.zsh` -> `functions.zsh`
- Modify: `functions.zsh`
- Modify: `tests/test_dataset_download_function.py`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-16-dataset-host-download-design.md`
- Modify: `docs/superpowers/plans/2026-07-16-host-dataset-download.md`

- [ ] **Step 1: Update tests first for the plural filename and missing runtime preparation**

In `tests/test_dataset_download_function.py`, change the shortcut path and add a host runtime-directory test:

```python
FUNCTIONS = ROOT / "functions.zsh"


def test_host_shortcut_file_uses_plural_name():
    assert FUNCTIONS.is_file()
    assert not (ROOT / "function.zsh").exists()
    text = FUNCTIONS.read_text(encoding="utf-8")
    assert "source /path/to/robomimic/functions.zsh" in text
    for relative_path in (
        "docs/superpowers/specs/2026-07-16-dataset-host-download-design.md",
        "docs/superpowers/plans/2026-07-16-host-dataset-download.md",
    ):
        documentation = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "function.zsh" not in documentation


def test_rmrun_prepares_host_bind_directories(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/usr/bin/env zsh\nexit 0\n", encoding="utf-8")
    fake_docker.chmod(0o755)

    command = (
        f"source {shlex.quote(str(FUNCTIONS))} >/dev/null; "
        f"ROBOMIMIC_REPO_DIR={shlex.quote(str(tmp_path / 'repo'))}; "
        "mkdir -p \"$ROBOMIMIC_REPO_DIR\"; rmrun"
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    result = subprocess.run(
        ["/usr/bin/zsh", "-fc", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for relative_path in (
        "datasets",
        "models/huggingface",
        "outputs/training",
        "outputs/videos",
    ):
        assert (tmp_path / "repo" / relative_path).is_dir()
```

- [ ] **Step 2: Run the host shortcut tests and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_download_function.py
```

Expected: the rename assertion or source comment fails, and the runtime output directories are missing.

- [ ] **Step 3: Complete the rename and runtime preparation**

Keep the user's existing rename, update the first comment in `functions.zsh`, and add this helper after `ROBOMIMIC_REPO_DIR`:

```zsh
# Load once in a host terminal with: source /path/to/robomimic/functions.zsh

_robomimic_prepare_runtime_dirs() {
  mkdir -p \
    "$ROBOMIMIC_REPO_DIR/datasets" \
    "$ROBOMIMIC_REPO_DIR/models/huggingface" \
    "$ROBOMIMIC_REPO_DIR/outputs/training" \
    "$ROBOMIMIC_REPO_DIR/outputs/videos"
}
```

Call it inside both `rmrun` and `rmcam`, immediately after changing to the repository:

```zsh
    _robomimic_prepare_runtime_dirs || return 1
```

Add a host shortcut section to `README.md` before the existing Compose startup example:

````markdown
### Host shortcuts

Load the host-only Docker and dataset commands from the repository:

```zsh
source ./functions.zsh
rmhelp
```

The host commands use the `rm*` prefix. Commands shown by `rshelp` are available
only after entering the container.
````

In both earlier dataset workflow documents, replace every host shortcut
reference from `function.zsh` to `functions.zsh`. Do not change the new
container-workflow design sentence that explicitly describes the rename from
the old filename.

- [ ] **Step 4: Run the host shortcut tests and verify GREEN**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_download_function.py
```

Expected: all host shortcut and dataset download tests pass.

- [ ] **Step 5: Commit the rename**

```bash
git add -A function.zsh functions.zsh tests/test_dataset_download_function.py README.md \
  docs/superpowers/specs/2026-07-16-dataset-host-download-design.md \
  docs/superpowers/plans/2026-07-16-host-dataset-download.md
git commit -m "feat: formalize host shortcut setup"
```

### Task 2: Upgrade the CUDA and PyTorch Runtime

**Files:**
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Modify: `tests/test_docker_ml_stack.py`

- [ ] **Step 1: Change the dependency contract test to cu128**

Replace `tests/test_docker_ml_stack.py` with:

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"


def test_dockerfile_pins_blackwell_compatible_numpy_2_cuda_stack():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM nvidia/cuda:12.8.1-base-ubuntu22.04" in dockerfile
    assert "numpy==2.0.1" in dockerfile
    assert "torch==2.7.1+cu128" in dockerfile
    assert "torchvision==0.22.1+cu128" in dockerfile
    for obsolete in (
        "nvidia/cuda:11.8.0-base-ubuntu20.04",
        "torch==2.4.1+cu118",
        "torchvision==0.19.1+cu118",
        "cpuonly",
    ):
        assert obsolete not in dockerfile


def test_pytorch_wheels_default_to_overridable_domestic_cu128_mirror():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    mirror = "https://mirrors.aliyun.com/pytorch-wheels/cu128"
    assert f"ARG PYTORCH_WHEEL_URL={mirror}" in dockerfile
    assert '--find-links "${PYTORCH_WHEEL_URL}"' in dockerfile
    assert "--extra-index-url" not in dockerfile
    assert f"PYTORCH_WHEEL_URL: ${{PYTORCH_WHEEL_URL:-{mirror}}}" in compose
```

- [ ] **Step 2: Run the stack test and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_docker_ml_stack.py
```

Expected: assertions show the current cu118 base, wheels, and mirror.

- [ ] **Step 3: Update Docker and Compose pins**

Apply these exact substitutions:

```dockerfile
FROM nvidia/cuda:12.8.1-base-ubuntu22.04
```

```dockerfile
ARG PYTORCH_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cu128
```

```dockerfile
RUN /opt/conda/bin/conda run -n robomimic_venv python -m pip install --no-cache-dir \
    --find-links "${PYTORCH_WHEEL_URL}" \
    numpy==2.0.1 \
    torch==2.7.1+cu128 \
    torchvision==0.22.1+cu128
```

Update the Compose build argument:

```yaml
        PYTORCH_WHEEL_URL: ${PYTORCH_WHEEL_URL:-https://mirrors.aliyun.com/pytorch-wheels/cu128}
```

- [ ] **Step 4: Run the stack test and Docker static check**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_docker_ml_stack.py
docker build --check .
```

Expected: both tests pass and Docker reports no warnings.

- [ ] **Step 5: Commit the runtime pins**

```bash
git add Dockerfile compose.yaml tests/test_docker_ml_stack.py
git commit -m "feat: upgrade runtime for Blackwell GPUs"
```

### Task 3: Add Persistent Train Output Overrides

**Files:**
- Create: `robomimic/utils/train_cli_utils.py`
- Modify: `robomimic/scripts/train.py`
- Create: `tests/test_train_cli_utils.py`

- [ ] **Step 1: Write failing pure helper tests**

Create `tests/test_train_cli_utils.py`:

```python
from types import SimpleNamespace

from robomimic.utils.train_cli_utils import apply_train_cli_overrides


class FakeConfig(SimpleNamespace):
    def unlock(self):
        self.unlock_called = True

    def lock_keys(self):
        self.lock_keys_called = True


def _config():
    return FakeConfig(
        unlock_called=False,
        lock_keys_called=False,
        experiment=SimpleNamespace(
            name="template",
            epoch_every_n_steps=100,
            validation_epoch_every_n_steps=10,
            rollout=SimpleNamespace(rate=50, n=50, horizon=400),
            save=SimpleNamespace(every_n_epochs=50),
        ),
        train=SimpleNamespace(
            data=None,
            num_epochs=2000,
            output_dir="../bc_trained_models",
        ),
    )


def test_debug_mode_is_short_and_persistent_output_wins():
    config = _config()
    args = SimpleNamespace(
        dataset="/data/lift.hdf5",
        name="lift-smoke",
        debug=True,
        output_dir="/opt/robomimic/outputs/training",
    )

    apply_train_cli_overrides(config, args)

    assert config.train.data == [{"path": "/data/lift.hdf5"}]
    assert config.experiment.name == "lift-smoke"
    assert config.train.num_epochs == 2
    assert config.experiment.epoch_every_n_steps == 3
    assert config.experiment.validation_epoch_every_n_steps == 3
    assert config.experiment.rollout.rate == 1
    assert config.experiment.rollout.n == 2
    assert config.experiment.rollout.horizon == 10
    assert config.experiment.save.every_n_epochs == 1
    assert config.train.output_dir == "/opt/robomimic/outputs/training"
    assert config.unlock_called and config.lock_keys_called


def test_full_training_preserves_template_defaults_without_overrides():
    config = _config()
    args = SimpleNamespace(
        dataset=None,
        name=None,
        debug=False,
        output_dir=None,
    )

    apply_train_cli_overrides(config, args)

    assert config.train.num_epochs == 2000
    assert config.experiment.save.every_n_epochs == 50
    assert config.train.output_dir == "../bc_trained_models"
```

- [ ] **Step 2: Run the helper tests and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_train_cli_utils.py
```

Expected: `ModuleNotFoundError` for `robomimic.utils.train_cli_utils`.

- [ ] **Step 3: Implement the helper**

Create `robomimic/utils/train_cli_utils.py`:

```python
def apply_train_cli_overrides(config, args):
    if args.dataset is not None:
        config.train.data = [{"path": args.dataset}]

    if args.name is not None:
        config.experiment.name = args.name

    if args.debug:
        config.unlock()
        config.lock_keys()
        config.experiment.epoch_every_n_steps = 3
        config.experiment.validation_epoch_every_n_steps = 3
        config.train.num_epochs = 2
        config.experiment.rollout.rate = 1
        config.experiment.rollout.n = 2
        config.experiment.rollout.horizon = 10
        config.experiment.save.every_n_epochs = 1
        config.train.output_dir = "/tmp/tmp_trained_models"

    if args.output_dir is not None:
        config.train.output_dir = args.output_dir
```

Modify `robomimic/scripts/train.py` to import the helper:

```python
from robomimic.utils.train_cli_utils import apply_train_cli_overrides
```

Replace the current dataset, name, and debug mutation block with:

```python
    apply_train_cli_overrides(config, args)

    device = TorchUtils.get_torch_device(try_to_use_cuda=config.train.cuda)
```

Add this parser argument after `--dataset`:

```python
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="(optional) override the directory used for logs, checkpoints, and videos",
    )
```

- [ ] **Step 4: Run tests and syntax checks**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_train_cli_utils.py
python3 -m py_compile robomimic/utils/train_cli_utils.py robomimic/scripts/train.py
```

Expected: both helper tests pass and both Python files compile.

- [ ] **Step 5: Commit the train CLI extension**

```bash
git add robomimic/utils/train_cli_utils.py robomimic/scripts/train.py tests/test_train_cli_utils.py
git commit -m "feat: persist debug training outputs"
```

### Task 4: Persist Container Workflow Outputs

**Files:**
- Modify: `compose.yaml`
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Create: `tests/test_output_volume_config.py`

- [ ] **Step 1: Write failing output mount tests**

Create `tests/test_output_volume_config.py`:

```python
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service():
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("COMPOSE_"):
            environment.pop(key)
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            os.devnull,
            "-f",
            str(ROOT / "compose.yaml"),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["services"]["robomimic"]


def test_outputs_are_a_writable_explicit_bind_mount():
    mount = next(
        volume
        for volume in _service()["volumes"]
        if volume["target"] == "/opt/robomimic/outputs"
    )
    assert mount["type"] == "bind"
    assert Path(mount["source"]) == ROOT / "outputs"
    assert mount.get("read_only", False) is False


def test_outputs_are_ignored_by_git_and_docker():
    for ignore_file in (".gitignore", ".dockerignore"):
        lines = (ROOT / ignore_file).read_text(encoding="utf-8").splitlines()
        assert "/outputs/" in lines

    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "outputs/training/model.pth"],
        cwd=ROOT,
    )
    assert result.returncode == 0
```

- [ ] **Step 2: Run the output tests and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_output_volume_config.py
```

Expected: the output mount lookup and ignore assertions fail.

- [ ] **Step 3: Add the mount and ignore rules**

Add this Compose volume after the dataset bind:

```yaml
      - type: bind
        source: ./outputs
        target: /opt/robomimic/outputs
        bind:
          create_host_path: true
```

Add to both ignore files:

```text
# local training, checkpoint, and rollout outputs
/outputs/
```

- [ ] **Step 4: Run the output tests and verify GREEN**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_output_volume_config.py
```

Expected: both output persistence tests pass.

- [ ] **Step 5: Commit output persistence**

```bash
git add compose.yaml .gitignore .dockerignore tests/test_output_volume_config.py
git commit -m "feat: persist training and rollout outputs"
```

### Task 5: Add the Container `rs*` Command Library

**Files:**
- Create: `docker/robomimic-functions.zsh`
- Modify: `docker/robomimic.zshrc`
- Modify: `Dockerfile`
- Create: `tests/test_container_workflow_functions.py`

- [ ] **Step 1: Write failing command-library tests**

Create `tests/test_container_workflow_functions.py` with tests that source the
real Zsh file against a temporary `RS_ROOT` and fake `python` executable:

```python
import os
import shlex
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "docker" / "robomimic-functions.zsh"


def _fixture(tmp_path):
    rs_root = tmp_path / "repo"
    for path in (
        rs_root / "datasets/lift/ph",
        rs_root / "robomimic/exps/templates",
        rs_root / "robomimic/scripts",
        rs_root / "outputs/training/run/models",
        rs_root / "outputs/videos",
    ):
        path.mkdir(parents=True, exist_ok=True)
    (rs_root / "datasets/lift/ph/low_dim_v15.hdf5").write_bytes(b"hdf5")
    (rs_root / "robomimic/exps/templates/bc.json").write_text("{}", encoding="utf-8")
    return rs_root


def _fake_python(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable = fake_bin / "python"
    executable.write_text(
        "#!/usr/bin/env zsh\n"
        "print -r -- \"MUJOCO_GL=$MUJOCO_GL $@\" >> \"$RS_COMMAND_LOG\"\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return fake_bin


def _run(tmp_path, body, *, display=""):
    rs_root = _fixture(tmp_path)
    fake_bin = _fake_python(tmp_path)
    log = tmp_path / "commands.log"
    command = (
        f"RS_ROOT={shlex.quote(str(rs_root))}; "
        f"source {shlex.quote(str(FUNCTIONS))}; {body}"
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["RS_COMMAND_LOG"] = str(log)
    environment["DISPLAY"] = display
    result = subprocess.run(
        ["/usr/bin/zsh", "-fc", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, rs_root, log


def test_rsplay_and_training_commands_use_safe_defaults_and_forward_overrides(tmp_path):
    result, rs_root, log = _run(
        tmp_path,
        "rsplay --n 2; rstrain --name custom-smoke; rstrain-full --name custom-full",
    )
    assert result.returncode == 0, result.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert "MUJOCO_GL=egl" in lines[0]
    assert "playback_dataset.py" in lines[0]
    assert "--n 1" in lines[0] and "--n 2" in lines[0]
    assert "--video_path" in lines[0]
    assert "train.py" in lines[1] and "--debug" in lines[1]
    assert "--name lift-bc-smoke" in lines[1]
    assert "--name custom-smoke" in lines[1]
    assert "--output_dir" in lines[1]
    assert "--debug" not in lines[2]
    assert "--name custom-full" in lines[2]
    assert (rs_root / "outputs/videos").is_dir()


def test_rslatest_and_rseval_use_newest_checkpoint(tmp_path):
    result, rs_root, log = _run(tmp_path, "true")
    assert result.returncode == 0
    older = rs_root / "outputs/training/run/models/older.pth"
    newer = rs_root / "outputs/training/run/models/newer.pth"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))

    command = (
        f"RS_ROOT={shlex.quote(str(rs_root))}; "
        f"source {shlex.quote(str(FUNCTIONS))}; rslatest; rseval --n_rollouts 2"
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{log.parent / 'bin'}:{environment['PATH']}"
    environment["RS_COMMAND_LOG"] = str(log)
    evaluated = subprocess.run(
        ["/usr/bin/zsh", "-fc", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert evaluated.returncode == 0, evaluated.stderr
    assert str(newer) in evaluated.stdout
    invocation = log.read_text(encoding="utf-8").splitlines()[-1]
    assert f"--agent {newer}" in invocation
    assert "--n_rollouts 5" in invocation and "--n_rollouts 2" in invocation
    assert "MUJOCO_GL=egl" in invocation


def test_missing_checkpoint_and_missing_display_fail_before_python(tmp_path):
    missing, _, _ = _run(tmp_path / "missing", "rseval")
    assert missing.returncode != 0
    assert "没有找到 checkpoint" in missing.stderr

    gui, _, log = _run(tmp_path / "gui", "rsplay-gui", display="")
    assert gui.returncode != 0
    assert "DISPLAY" in gui.stderr
    assert not log.exists()


def test_rshelp_and_install_hooks_are_present():
    functions = FUNCTIONS.read_text(encoding="utf-8")
    zshrc = (ROOT / "docker/robomimic.zshrc").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for name in (
        "rsstatus",
        "rsplay",
        "rsplay-gui",
        "rstrain",
        "rstrain-full",
        "rslatest",
        "rseval",
        "rseval-gui",
        "rshelp",
    ):
        assert f"{name}()" in functions
    assert "robomimic-functions.zsh" in zshrc
    assert "COPY docker/robomimic-functions.zsh" in dockerfile
```

- [ ] **Step 2: Run the command tests and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_container_workflow_functions.py
```

Expected: the container function file is missing and all command tests fail.

- [ ] **Step 3: Implement `docker/robomimic-functions.zsh`**

Create the file with these functions and defaults:

```zsh
typeset -g RS_ROOT="${RS_ROOT:-/opt/robomimic}"
typeset -g RS_DEFAULT_DATASET="${RS_DEFAULT_DATASET:-$RS_ROOT/datasets/lift/ph/low_dim_v15.hdf5}"
typeset -g RS_DEFAULT_CONFIG="${RS_DEFAULT_CONFIG:-$RS_ROOT/robomimic/exps/templates/bc.json}"
typeset -g RS_OUTPUT_ROOT="${RS_OUTPUT_ROOT:-$RS_ROOT/outputs}"
typeset -g RS_TRAINING_ROOT="${RS_TRAINING_ROOT:-$RS_OUTPUT_ROOT/training}"
typeset -g RS_VIDEO_ROOT="${RS_VIDEO_ROOT:-$RS_OUTPUT_ROOT/videos}"

_rs_require_file() {
  if [[ ! -s "$1" ]]; then
    print -u2 "文件不存在或为空：$1"
    return 1
  fi
}

_rs_prepare_outputs() {
  umask 0000
  mkdir -p "$RS_TRAINING_ROOT" "$RS_VIDEO_ROOT" || return 1
  chmod a+rwx "$RS_OUTPUT_ROOT" "$RS_TRAINING_ROOT" "$RS_VIDEO_ROOT" 2>/dev/null || true
}

_rs_take_optional_path() {
  REPLY=""
  if (( $# > 0 )) && [[ "$1" != -* ]]; then
    REPLY="$1"
    return 0
  fi
  return 1
}

_rs_require_gui() {
  if [[ -z "${DISPLAY:-}" ]]; then
    print -u2 'DISPLAY 未设置；请从宿主机使用 rmrun 或 rmcam 启动容器。'
    return 1
  fi
  local display_number="${DISPLAY#:}"
  display_number="${display_number%%.*}"
  if [[ ! -S "/tmp/.X11-unix/X${display_number}" ]]; then
    print -u2 "找不到 X11 socket：/tmp/.X11-unix/X${display_number}"
    return 1
  fi
}

rslatest() {
  local latest
  latest="$(
    find "$RS_OUTPUT_ROOT" -type f -name '*.pth' -printf '%T@\t%p\n' 2>/dev/null \
      | sort -nr \
      | head -n 1 \
      | cut -f 2-
  )"
  if [[ -z "$latest" ]]; then
    print -u2 "没有找到 checkpoint：$RS_OUTPUT_ROOT"
    print -u2 '请先运行 rstrain 或 rstrain-full。'
    return 1
  fi
  print -r -- "$latest"
}

rsstatus() {
  _rs_prepare_outputs || return 1
  python -c 'import numpy as np, torch, torchvision; print("python/torch runtime"); print("numpy", np.__version__); print("torch", torch.__version__); print("torchvision", torchvision.__version__); print("cuda", torch.version.cuda); print("gpu", torch.cuda.get_device_name(0)); print("capability", torch.cuda.get_device_capability(0)); print("arches", torch.cuda.get_arch_list()); print("cuda_result", (torch.ones(1, device="cuda") + 1).cpu().tolist())' || return 1
  [[ -s "$RS_DEFAULT_DATASET" ]] && print "dataset: $RS_DEFAULT_DATASET ($(du -h "$RS_DEFAULT_DATASET" | cut -f1))" || print -u2 "dataset missing: $RS_DEFAULT_DATASET"
  print "outputs: $RS_OUTPUT_ROOT"
  local checkpoint
  checkpoint="$(rslatest 2>/dev/null)" && print "latest: $checkpoint" || print 'latest: none'
}

rsplay() {
  local dataset="$RS_DEFAULT_DATASET"
  if _rs_take_optional_path "$@"; then dataset="$REPLY"; shift; fi
  _rs_require_file "$dataset" || return 1
  _rs_prepare_outputs || return 1
  MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/playback_dataset.py" \
    --dataset "$dataset" --n 1 --render_image_names agentview \
    --video_path "$RS_VIDEO_ROOT/dataset-playback.mp4" "$@"
}

rsplay-gui() {
  local dataset="$RS_DEFAULT_DATASET"
  if _rs_take_optional_path "$@"; then dataset="$REPLY"; shift; fi
  _rs_require_file "$dataset" || return 1
  _rs_require_gui || return 1
  MUJOCO_GL=glfw python "$RS_ROOT/robomimic/scripts/playback_dataset.py" \
    --dataset "$dataset" --n 1 --render --render_image_names agentview "$@"
}

rstrain() {
  _rs_require_file "$RS_DEFAULT_CONFIG" || return 1
  _rs_require_file "$RS_DEFAULT_DATASET" || return 1
  _rs_prepare_outputs || return 1
  MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/train.py" \
    --config "$RS_DEFAULT_CONFIG" --dataset "$RS_DEFAULT_DATASET" \
    --name lift-bc-smoke --output_dir "$RS_TRAINING_ROOT" --debug "$@"
}

rstrain-full() {
  _rs_require_file "$RS_DEFAULT_CONFIG" || return 1
  _rs_require_file "$RS_DEFAULT_DATASET" || return 1
  _rs_prepare_outputs || return 1
  print -u2 '即将启动完整训练；BC 模板默认运行 2000 epochs。'
  MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/train.py" \
    --config "$RS_DEFAULT_CONFIG" --dataset "$RS_DEFAULT_DATASET" \
    --name lift-bc-full --output_dir "$RS_TRAINING_ROOT" "$@"
}

rseval() {
  local checkpoint
  if _rs_take_optional_path "$@"; then checkpoint="$REPLY"; shift; else checkpoint="$(rslatest)" || return 1; fi
  _rs_require_file "$checkpoint" || return 1
  _rs_prepare_outputs || return 1
  local stem="${checkpoint:t:r}"
  MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/run_trained_agent.py" \
    --agent "$checkpoint" --n_rollouts 5 --seed 0 --camera_names agentview \
    --video_path "$RS_VIDEO_ROOT/eval-${stem}.mp4" "$@"
}

rseval-gui() {
  local checkpoint
  if _rs_take_optional_path "$@"; then checkpoint="$REPLY"; shift; else checkpoint="$(rslatest)" || return 1; fi
  _rs_require_file "$checkpoint" || return 1
  _rs_require_gui || return 1
  MUJOCO_GL=glfw python "$RS_ROOT/robomimic/scripts/run_trained_agent.py" \
    --agent "$checkpoint" --n_rollouts 1 --seed 0 --camera_names agentview --render "$@"
}

rshelp() {
  print 'robomimic simulation 容器命令：'
  print '  rsstatus                    检查 CUDA、数据集、输出与 checkpoint'
  print '  rsplay [dataset]            回放数据集并生成 outputs/videos/dataset-playback.mp4'
  print '  rsplay-gui [dataset]        使用 X11 窗口回放数据集'
  print '  rstrain [train.py 参数]     运行 2 epoch GPU smoke test'
  print '  rstrain-full [参数]         启动完整 BC 训练'
  print '  rslatest                    打印 outputs 下最新 checkpoint'
  print '  rseval [checkpoint] [参数]  仿真 rollout 并保存视频'
  print '  rseval-gui [checkpoint]     实时窗口运行策略'
  print '  rshelp                      显示本帮助'
}
```

- [ ] **Step 4: Install and source the function library**

Add to `Dockerfile` near the existing Zsh copies:

```dockerfile
COPY docker/robomimic-functions.zsh /usr/local/share/robomimic/robomimic-functions.zsh
```

Extend the existing permission setup:

```dockerfile
RUN chmod 0755 /usr/local/bin/robomimic-entrypoint && \
    chmod 0644 /usr/local/share/robomimic/robomimic-functions.zsh && \
    mkdir -p /tmp/oh-my-zsh-cache
```

Add to `docker/robomimic.zshrc` after Conda activation:

```zsh
if [[ -r /usr/local/share/robomimic/robomimic-functions.zsh ]]; then
  source /usr/local/share/robomimic/robomimic-functions.zsh
fi
```

Inside the existing interactive guard, print `rshelp` after the banner:

```zsh
  rshelp
```

- [ ] **Step 5: Run command and syntax tests**

Run:

```bash
zsh -n docker/robomimic-functions.zsh docker/robomimic.zshrc
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_container_workflow_functions.py
```

Expected: syntax checking and all command-library tests pass.

- [ ] **Step 6: Commit the container command library**

```bash
git add Dockerfile docker/robomimic-functions.zsh docker/robomimic.zshrc tests/test_container_workflow_functions.py
git commit -m "feat: add container simulation workflow commands"
```

### Task 6: Document the End-to-End Workflow

**Files:**
- Modify: `README.md`
- Create: `tests/test_container_workflow_docs.py`

- [ ] **Step 1: Write a failing documentation contract test**

Create `tests/test_container_workflow_docs.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_copyable_host_and_container_workflow():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for snippet in (
        "source ./functions.zsh",
        "rmrun",
        "rsstatus",
        "rsplay",
        "rstrain",
        "rstrain-full",
        "rslatest",
        "rseval",
        "outputs/training",
        "outputs/videos",
        "PyTorch 2.7.1",
        "CUDA 12.8",
    ):
        assert snippet in readme
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_container_workflow_docs.py
```

Expected: missing `rs*`, output path, and CUDA stack snippets fail.

- [ ] **Step 3: Add a copyable workflow section to README**

Add a section after the interactive container explanation with these commands:

````markdown
### Simulation, training, and policy rollout inside the container

The image uses PyTorch 2.7.1 with CUDA 12.8 for RTX 50-series GPU support.
After entering with `rmrun`, the container prints `rshelp` automatically.

```zsh
rsstatus
rsplay
rstrain
rslatest
rseval
```

Use `rstrain-full` only when you intend to start the complete BC schedule. Use
`rsplay-gui` and `rseval-gui` for X11 windows. Training artifacts are persisted
under `outputs/training`; playback and evaluation videos are stored under
`outputs/videos` on both the host and container bind mount.
````

- [ ] **Step 4: Run the documentation test and verify GREEN**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_container_workflow_docs.py
```

Expected: the README workflow contract passes.

- [ ] **Step 5: Commit the documentation**

```bash
git add README.md tests/test_container_workflow_docs.py
git commit -m "docs: explain container simulation workflow"
```

### Task 7: Build and Runtime Verification

**Files:**
- Verify: `robomimic:latest`
- Generate ignored artifacts under `outputs/`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider \
  tests/test_dataset_download_function.py \
  tests/test_docker_ml_stack.py \
  tests/test_train_cli_utils.py \
  tests/test_output_volume_config.py \
  tests/test_container_workflow_functions.py \
  tests/test_container_workflow_docs.py \
  tests/test_dataset_volume_config.py \
  tests/test_clip_model_cache_config.py \
  tests/test_lang_utils_cache.py \
  tests/test_notify_feishu.py \
  tests/test_publish_workflow.py
```

Expected: all selected tests and subtests pass.

- [ ] **Step 2: Run static checks**

```bash
git diff --check
docker compose config --quiet
docker build --check .
zsh -n functions.zsh docker/robomimic.zshrc docker/robomimic-functions.zsh
```

Expected: all commands exit zero and Docker reports no warnings.

- [ ] **Step 3: Build the cu128 image**

```bash
docker compose build robomimic
```

Expected: image `robomimic:latest` builds with PyTorch 2.7.1+cu128,
torchvision 0.22.1+cu128, and NumPy 2.0.1.

- [ ] **Step 4: Verify RTX 5060 Ti CUDA execution through `rsstatus`**

```bash
docker compose run --rm --no-deps -T robomimic /usr/bin/zsh -lc rsstatus
```

Expected: device capability `(12, 0)`, compiled `sm_120` support, and
`cuda_result [2.0]` with exit code zero.

- [ ] **Step 5: Produce a headless dataset playback video**

```bash
docker compose run --rm --no-deps -T robomimic /usr/bin/zsh -lc rsplay
test -s outputs/videos/dataset-playback.mp4
```

Expected: the MP4 exists and is non-empty.

- [ ] **Step 6: Run the GPU smoke training workflow**

```bash
docker compose run --rm --no-deps -T robomimic /usr/bin/zsh -lc rstrain
find outputs/training -type f -name '*.pth' -print -quit | grep .
```

Expected: two debug epochs complete and at least one checkpoint is persisted.

- [ ] **Step 7: Evaluate the latest checkpoint headlessly**

```bash
LATEST=$(find outputs/training -type f -name '*.pth' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)
docker compose run --rm --no-deps -T robomimic /usr/bin/zsh -lc 'rslatest; rseval --n_rollouts 1 --horizon 10'
test -n "$LATEST"
find outputs/videos -type f -name 'eval-*.mp4' -size +0c -print -quit | grep .
```

Expected: `rslatest` prints the same checkpoint and evaluation produces a
non-empty MP4.

- [ ] **Step 8: Final repository and artifact review**

```bash
git status --short
git check-ignore -v outputs/videos/dataset-playback.mp4
git check-ignore -v outputs/training
docker image inspect robomimic:latest --format '{{.Id}}'
```

Expected: only the pre-existing `MUJOCO_LOG.TXT` is untracked, generated output
artifacts are ignored, and the final image ID is printed.
