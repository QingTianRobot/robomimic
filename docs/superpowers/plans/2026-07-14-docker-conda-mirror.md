# Docker Conda Mirror Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docker build -t robomimic .` complete without accepting Anaconda default-channel Terms of Service by routing Conda downloads through the Tsinghua University mirror.

**Architecture:** Preserve the existing CUDA base image, Miniconda installation, Conda environment name, and dependency versions. Add a single Conda configuration layer before environment creation so `defaults` and named channels resolve to domestic mirror URLs, then validate the complete image and its installed Python packages.

**Tech Stack:** Docker BuildKit, Ubuntu 20.04, Miniconda, Tsinghua Anaconda mirror, Python 3.9, PyTorch, robomimic, robosuite.

---

## File structure

- Modify `Dockerfile`: configure Conda mirror endpoints before creating `robomimic_venv`.
- No permanent test file is needed: the production Docker build is the regression test because the failure occurs while executing the Dockerfile itself.

### Task 1: Preserve the failing regression evidence

**Files:**
- Test: `Dockerfile:33`

- [ ] **Step 1: Run the current build and verify the expected failure**

Run:

```bash
docker build -t robomimic .
```

Expected: FAIL at the `conda create -n robomimic_venv python=3.9 -y` layer with `CondaToSNonInteractiveError` naming `https://repo.anaconda.com/pkgs/main` and `https://repo.anaconda.com/pkgs/r`. This failure was reproduced before implementation and is the RED state.

### Task 2: Configure domestic Conda channels

**Files:**
- Modify: `Dockerfile:32`

- [ ] **Step 1: Add the minimal Conda configuration layer**

Insert this block after the Miniconda installation and before `conda create`:

```dockerfile
# Use domestic Conda mirrors and avoid the Anaconda default-channel ToS prompt
RUN /opt/conda/bin/conda config --system --remove-key default_channels || true && \
    /opt/conda/bin/conda config --system --add default_channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main && \
    /opt/conda/bin/conda config --system --add default_channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r && \
    /opt/conda/bin/conda config --system --set channel_alias https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud && \
    /opt/conda/bin/conda config --system --set show_channel_urls true
```

Do not add `conda tos accept`, change package versions, or change unrelated download sources.

- [ ] **Step 2: Check Dockerfile syntax and review the exact diff**

Run:

```bash
docker build --check .
git diff --check
git diff -- Dockerfile
```

Expected: Docker build check and whitespace check exit successfully; the diff contains only the mirror configuration layer.

### Task 3: Build the corrected image

**Files:**
- Test: `Dockerfile`

- [ ] **Step 1: Run the regression command again**

Run:

```bash
docker build --progress=plain -t robomimic .
```

Expected: PASS with exit code 0 and an exported image tagged `robomimic:latest`. The `conda create` output must show Tsinghua mirror URLs and must not raise `CondaToSNonInteractiveError`.

- [ ] **Step 2: If a later source fails, isolate it before changing configuration**

Use the first failing URL and Dockerfile layer from the build log. Keep the Conda mirror change unchanged, and make no additional source change unless the log proves that specific source is unavailable or unacceptably slow.

### Task 4: Verify the built runtime

**Files:**
- Test: built image `robomimic:latest`

- [ ] **Step 1: Verify the image tag exists**

Run:

```bash
docker image inspect robomimic:latest --format '{{.Id}}'
```

Expected: PASS and print a `sha256:` image identifier.

- [ ] **Step 2: Verify Python and required imports inside the Conda environment**

Run:

```bash
docker run --rm robomimic:latest /opt/conda/bin/conda run -n robomimic_venv python -c "import sys, torch, robomimic, robosuite; assert sys.version_info[:2] == (3, 9); print(sys.version.split()[0]); print(torch.__version__); print('imports-ok')"
```

Expected: PASS and print a Python `3.9.x` version, the installed PyTorch version, and `imports-ok`.

### Task 5: Record the implementation

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Confirm the final worktree contains only intended changes**

Run:

```bash
git status --short
git diff --check
git diff -- Dockerfile
```

Expected: only the intended Dockerfile change is uncommitted, with no whitespace errors.

- [ ] **Step 2: Commit the Dockerfile fix**

Run:

```bash
git add Dockerfile
git commit -m "fix: use domestic conda mirrors in Docker build"
```

Expected: a new commit containing only the Dockerfile mirror configuration.
