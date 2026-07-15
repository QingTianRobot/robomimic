# Docker Domestic Mirrors and Local Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `robomimic:latest` from the current local source without accepting Anaconda Terms of Service or accessing GitHub during the Docker build.

**Architecture:** Preserve the CUDA, Ubuntu, Miniconda, Python, and PyTorch layers. Route Conda and pip through Tsinghua University mirrors, copy a filtered local workspace into `/opt/robomimic`, install it in editable mode, and install binary `mujoco==3.3.7` with the compatible `robosuite==1.5.1` PyPI distribution.

**Tech Stack:** Docker BuildKit, Ubuntu 20.04, Miniconda, Tsinghua Anaconda/PyPI mirrors, Python 3.9, PyTorch 2.0.0, MuJoCo 3.3.7, robomimic, robosuite 1.5.1.

---

## File structure

- Create `.dockerignore`: exclude Git metadata, development caches, local environments, datasets, videos, model files, and large documentation images from the Docker build context.
- Modify `Dockerfile`: retain the Conda mirror fix, remove GitHub cloning and proxy configuration, configure pip, copy local source, and install robosuite from PyPI.

### Task 1: Preserve regression evidence

**Files:**
- Test: `Dockerfile`

- [x] **Step 1: Record the original Conda failure**

Run:

```bash
docker build -t robomimic .
```

Observed: FAIL at `conda create` with `CondaToSNonInteractiveError` for `repo.anaconda.com/pkgs/main` and `repo.anaconda.com/pkgs/r`.

- [x] **Step 2: Record the GitHub failures after the Conda fix**

Observed: direct GitHub timed out; two acceleration services failed with GnuTLS; a third service returned `ls-remote` but stalled on complete repository and archive transfers. This is the RED state for removing build-time GitHub access.

### Task 2: Filter the local Docker context

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore` with exact exclusions**

```dockerignore
.git
.github
.idea
.vscode
**/__pycache__
**/*.py[cod]
.pytest_cache
.mypy_cache
.venv
venv
env
build
dist
**/*.egg-info
docs/_build
docs/images
tests/assets
**/*.hdf5
**/*.mp4
**/*.pth
```

These exclusions retain `setup.py`, `README.md`, `MANIFEST.in`, `requirements-docs.txt`, the `robomimic` package, examples, tests, and documentation sources required by the build.

- [ ] **Step 2: Verify the ignore file contains no whitespace errors**

Run:

```bash
git diff --check
git diff -- .dockerignore
```

Expected: PASS; the diff contains only the exclusions above.

### Task 3: Install local source and robosuite from domestic PyPI

**Files:**
- Modify: `Dockerfile:39-58`

- [ ] **Step 1: Remove GitHub proxy and clone instructions**

Delete the `GITHUB_PROXY` argument and both `git clone` commands. Keep the verified Conda mirror configuration unchanged.

- [ ] **Step 2: Add pip mirror configuration and local-source installation**

Replace the source installation portion with:

```dockerfile
# Use a domestic PyPI mirror for Python dependencies
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

# Install the current robomimic source tree
WORKDIR /opt/robomimic
COPY . .
RUN /opt/conda/bin/conda run -n robomimic_venv pip install -e .

# Install the robosuite version recommended for the current datasets
# MuJoCo 3.3.7 is the latest release with a CPython 3.9 Linux wheel
RUN /opt/conda/bin/conda run -n robomimic_venv pip install --only-binary=mujoco \
    mujoco==3.3.7 robosuite==1.5.1

# Optional: Install robomimic documentation dependencies
RUN /opt/conda/bin/conda run -n robomimic_venv pip install -r requirements-docs.txt
```

Keep the final `WORKDIR /workspace` and existing `CMD` unchanged.

- [ ] **Step 3: Check Dockerfile syntax and review the combined diff**

Run:

```bash
docker build --check .
git diff --check
git diff -- Dockerfile .dockerignore
```

Expected: Docker build check reports no warnings; the production Dockerfile contains no `github.com`, GitHub proxy, or `git clone` string.

### Task 4: Build the corrected image

**Files:**
- Test: `Dockerfile`
- Test: `.dockerignore`

- [ ] **Step 1: Run the complete regression build**

Run:

```bash
docker build --progress=plain -t robomimic .
```

Expected: PASS with exit code 0 and an exported `robomimic:latest` image. The log shows a small transferred build context, cached system/Conda/PyTorch layers where available, Tsinghua PyPI URLs for Python downloads, and no GitHub request.

- [ ] **Step 2: If a package fails, isolate the exact mirror artifact**

Use the first failing package name and URL from the build log. Do not add a GitHub dependency or change unrelated versions. The verified targets are exactly `mujoco==3.3.7` and `robosuite==1.5.1`.

### Task 5: Verify the built runtime

**Files:**
- Test: built image `robomimic:latest`

- [ ] **Step 1: Verify the image tag exists**

Run:

```bash
docker image inspect robomimic:latest --format '{{.Id}}'
```

Expected: PASS and print a `sha256:` image identifier.

- [ ] **Step 2: Verify Python, packages, versions, and local source path**

Run:

```bash
docker run --rm robomimic:latest /opt/conda/bin/conda run -n robomimic_venv python -c "import importlib.metadata as metadata, pathlib, sys, torch, mujoco, robomimic, robosuite; assert sys.version_info[:2] == (3, 9); assert metadata.version('mujoco') == '3.3.7'; assert metadata.version('robosuite') == '1.5.1'; assert str(pathlib.Path(robomimic.__file__).resolve()).startswith('/opt/robomimic/'); print(sys.version.split()[0]); print(torch.__version__); print(metadata.version('mujoco')); print(metadata.version('robosuite')); print(robomimic.__file__); print('imports-ok')"
```

Expected: PASS and print Python `3.9.x`, PyTorch `2.0.0`, MuJoCo `3.3.7`, robosuite `1.5.1`, a robomimic path below `/opt/robomimic`, and `imports-ok`.

### Task 6: Record the implementation

**Files:**
- Create: `.dockerignore`
- Modify: `Dockerfile`

- [ ] **Step 1: Confirm the final worktree contains only intended implementation changes**

Run:

```bash
git status --short
git diff --check
git diff -- Dockerfile .dockerignore
```

Expected: only `Dockerfile` and `.dockerignore` are uncommitted implementation changes, with no whitespace errors.

- [ ] **Step 2: Commit the implementation**

Run:

```bash
git add Dockerfile .dockerignore
git commit -m "fix: build Docker image from local source"
```

Expected: a new commit containing the domestic mirror configuration, local-source copy, MuJoCo and robosuite pins, and Docker context exclusions.
