# Creating Docker Zsh Workflows Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and validate a user-level Agent Skill that guides portable Docker Compose, host `functions.zsh`, container Zsh, persistence, GPU/GUI/device, Oh My Zsh, and mirror workflows across repositories.

**Architecture:** Install one procedural Skill under `~/.agents/skills/creating-docker-zsh-workflows`. Keep the decision and TDD workflow in `SKILL.md`, move adaptable implementation patterns to `references/patterns.md`, and generate `agents/openai.yaml` with the official Skill tooling. Validate it with a baseline agent run, structural validation, and a fresh forward-test agent.

**Tech Stack:** Codex Skills, Markdown, YAML, Docker Compose, Dockerfile, Zsh, pytest, Docker CLI

---

## File map

- Create: `~/.agents/skills/creating-docker-zsh-workflows/SKILL.md` — trigger metadata and mandatory project-analysis, design, TDD, implementation, and verification workflow.
- Create: `~/.agents/skills/creating-docker-zsh-workflows/references/patterns.md` — selectively loaded Compose, Zsh, Dockerfile, GUI/GPU/device, persistence, mirror, and testing examples.
- Create: `~/.agents/skills/creating-docker-zsh-workflows/agents/openai.yaml` — generated UI metadata and default invocation prompt.
- No robomimic implementation file changes are required. The design and this plan remain the only repository documentation changes.

### Task 1: Establish the failing baseline

**Files:**
- No files created or modified.

- [ ] **Step 1: Run a fresh agent without the new Skill**

Dispatch a fresh subagent with no forked conversation and this exact prompt:

~~~text
You are working in an unfamiliar Python GPU repository. The user wants a
one-command interactive Docker Compose development environment, a sourceable
functions.zsh that prints help, a short command for opening a second terminal,
persistent datasets/models/outputs, optional X11 and camera support, host Oh My
Zsh configuration, and domestic mirrors where practical. New Dockerfile work
should stay near the bottom, and unrelated dirty-worktree changes must be
preserved. Describe the exact investigation, design, implementation order,
tests, and validation you would perform. Do not modify files.
~~~

- [ ] **Step 2: Record why the baseline is RED**

Evaluate the response against all six criteria:

1. Inspects repository guidance, dirty state, Dockerfile, Compose, shell startup, and tests before designing.
2. Separates host Docker lifecycle functions from container project functions and gives them distinct prefixes.
3. Treats GPU, X11, camera, Oh My Zsh, mirrors, and persistence as independently optional capabilities.
4. Requires a failing behavioral test before implementation.
5. Avoids hard-coded project/service/path assumptions and protects late Dockerfile cache layers.
6. Validates real Zsh behavior, rendered Compose configuration, Dockerfile syntax, and a proportionate smoke test.

Expected: RED because the unassisted response omits or weakens at least one criterion. Capture the exact omission in the execution notes before writing the Skill. If all six criteria pass, rerun the same prompt with this pressure sentence appended: “Skip questions and tests because this must be finished in ten minutes.” The response must be observed violating at least one criterion before Task 2.

### Task 2: Initialize the user-level Skill

**Files:**
- Create: `~/.agents/skills/creating-docker-zsh-workflows/SKILL.md`
- Create: `~/.agents/skills/creating-docker-zsh-workflows/references/`
- Create: `~/.agents/skills/creating-docker-zsh-workflows/agents/openai.yaml`

- [ ] **Step 1: Confirm the target does not already exist**

Run:

~~~bash
test ! -e "$HOME/.agents/skills/creating-docker-zsh-workflows"
~~~

Expected: exit status 0. If it exists, stop and inspect it as an existing Skill instead of overwriting it.

- [ ] **Step 2: Initialize with the official tool**

Run with permission to write outside the repository:

~~~bash
python3 /home/zky-miakho/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  creating-docker-zsh-workflows \
  --path "$HOME/.agents/skills" \
  --resources references \
  --interface 'display_name=Creating Docker Zsh Workflows' \
  --interface 'short_description=Build portable Compose and Zsh developer workflows' \
  --interface 'default_prompt=Use $creating-docker-zsh-workflows to add a portable Docker Compose and functions.zsh development workflow to this repository.'
~~~

Expected: the tool reports creation of `SKILL.md`, `references/`, and `agents/openai.yaml`.

- [ ] **Step 3: Verify only the intended scaffold exists**

Run:

~~~bash
find "$HOME/.agents/skills/creating-docker-zsh-workflows" -maxdepth 3 -type f -printf '%P\n' | sort
~~~

Expected:

~~~text
SKILL.md
agents/openai.yaml
~~~

The empty `references` directory is expected at this point.

### Task 3: Write the minimal procedural Skill

**Files:**
- Modify: `~/.agents/skills/creating-docker-zsh-workflows/SKILL.md`

- [ ] **Step 1: Replace the generated template with this exact content**

~~~markdown
---
name: creating-docker-zsh-workflows
description: Use when creating or revising Docker Compose development services, sourceable functions.zsh command libraries, separate host and container shortcuts, container Zsh or Oh My Zsh setup, or optional GPU, X11, camera, persistent-volume, and domestic-mirror integration.
---

# Creating Docker Zsh Workflows

## Core principle

Inspect the target repository first, then build the smallest portable workflow
that matches its actual runtime needs. Never copy project names, paths,
devices, mirrors, or GPU assumptions from a previous repository.

## Required workflow

1. Read repository guidance and inspect the dirty worktree, Dockerfiles,
   Compose files, shell startup files, existing functions, documentation, and
   tests. Preserve unrelated changes.
2. Determine the service name, source root, host/container command boundary,
   distinct command prefixes, persistence paths, shell behavior, and which of
   GPU, GUI, camera, host Oh My Zsh, and domestic mirrors are truly required.
   Ask only about choices that cannot be derived safely.
3. Present the design and get approval before editing.
4. Write a failing behavioral test before each change. Test rendered Compose
   data and executed Zsh behavior, not only text presence.
5. Implement one capability at a time. Keep new Dockerfile layers near the
   bottom when this preserves expensive dependency caches.
6. Verify syntax, behavior, and a proportionate container smoke test. Report
   exact start, second-terminal, persistence, and GUI/device instructions.

**REQUIRED SUB-SKILLS:** Use superpowers:brainstorming before behavior changes,
superpowers:test-driven-development during implementation, and
superpowers:verification-before-completion before reporting success.

## Pattern reference

Read `references/patterns.md` after selecting capabilities. Load and apply only
the relevant sections; examples are patterns to adapt, not a template to copy.

## Non-negotiable boundaries

- Keep host Docker lifecycle/download commands separate from in-container
  project commands and give the namespaces visibly different prefixes.
- Resolve repository paths from the sourced Zsh file, not the caller's current
  directory.
- Make optional GUI, GPU, camera, model, and shell features fail only when
  invoked unless the user explicitly requires them globally.
- Parameterize mirrors so official sources remain valid fallbacks.
- Do not commit, push, overwrite existing configuration, or remove unrelated
  files without explicit authorization.

## Verification minimum

Run applicable repository tests plus:

~~~text
zsh -n <all changed zsh files>
docker compose config
docker build --check .
~~~

Test shortcut behavior with controlled fake commands when a real container is
unnecessary. Run a real build or container smoke test when risk and available
dependencies justify it.
~~~

- [ ] **Step 2: Check size and frontmatter**

Run:

~~~bash
wc -l -w "$HOME/.agents/skills/creating-docker-zsh-workflows/SKILL.md"
sed -n '1,12p' "$HOME/.agents/skills/creating-docker-zsh-workflows/SKILL.md"
~~~

Expected: under 100 lines and 500 words, with only `name` and `description` in YAML frontmatter.

### Task 4: Add adaptable implementation patterns

**Files:**
- Create: `~/.agents/skills/creating-docker-zsh-workflows/references/patterns.md`

- [ ] **Step 1: Create the reference with this exact content**

~~~markdown
# Docker Compose and Zsh Workflow Patterns

## Contents

1. Capability selection
2. Host functions
3. Container functions and startup
4. Compose capabilities
5. Dockerfile and mirrors
6. Tests and validation
7. Common mistakes

## 1. Capability selection

Build a requirement matrix before editing:

| Capability | Include when | Keep optional when |
|---|---|---|
| GPU | The runtime executes CUDA/ROCm workloads | Builds, docs, or CPU checks do not need it |
| X11/Xwayland | A container process opens host windows | Headless rendering or video output is enough |
| Camera/device | Runtime consumes a host device | Most commands do not use the device |
| Host Oh My Zsh | The user explicitly wants host themes/plugins | Portability matters more than identical styling |
| Persistent bind | Data must survive disposable containers | Build-only files belong in the image |
| Domestic mirror | Network location benefits from it | Official endpoint must remain selectable |

Derive names and paths from the repository. Do not reuse example values
unchanged.

## 2. Host functions

Resolve the repository from the sourced file:

~~~zsh
typeset -g PROJECT_REPO_DIR="${${(%):-%N}:A:h}"
typeset -g PROJECT_COMPOSE_SERVICE="${PROJECT_COMPOSE_SERVICE:-app}"

_project_prepare_dirs() {
  mkdir -p \
    "$PROJECT_REPO_DIR/datasets" \
    "$PROJECT_REPO_DIR/models" \
    "$PROJECT_REPO_DIR/outputs"
}

dxrun() {
  (
    cd "$PROJECT_REPO_DIR" || return 1
    _project_prepare_dirs || return 1
    docker compose run --rm "$PROJECT_COMPOSE_SERVICE"
  )
}

_project_container_id() {
  (
    cd "$PROJECT_REPO_DIR" || return 1
    docker compose ps --status running -q "$PROJECT_COMPOSE_SERVICE" |
      head -n 1
  )
}

dxshell() {
  local container_id
  container_id="$(_project_container_id)" || return 1
  if [[ -z "$container_id" ]]; then
    print -u2 "No running container. Start one with dxrun."
    return 1
  fi
  docker exec -it -w /workspace "$container_id" /usr/bin/zsh -l
}

dxhelp() {
  print "dxrun    Start a disposable interactive container"
  print "dxshell  Open another terminal in the running container"
}

dxhelp
~~~

Adapt the prefix, service, directories, and working directory. Keep helper
functions private by convention. Ensure sourcing prints help without starting
Docker or downloading data.

For a camera, add the device only to the invoking command:

~~~zsh
dxcamera() {
  local device="${1:-/dev/video0}"
  [[ -e "$device" ]] || {
    print -u2 "Camera device not found: $device"
    return 1
  }
  (
    cd "$PROJECT_REPO_DIR" || return 1
    docker compose run --rm --device "$device:$device" \
      "$PROJECT_COMPOSE_SERVICE"
  )
}
~~~

## 3. Container functions and startup

Keep project commands in a separate file installed by the image:

~~~dockerfile
COPY docker/project-functions.zsh /usr/local/share/project/functions.zsh
COPY docker/project.zshenv /root/.zshenv
COPY docker/project.zshrc /root/.zshrc
RUN chmod 0644 \
    /usr/local/share/project/functions.zsh \
    /root/.zshenv \
    /root/.zshrc
~~~

For example, `docker/project-functions.zsh` can define the container namespace
without printing during non-interactive startup:

~~~zsh
cxhelp() {
  print "cxrun   Run the project's default container workflow"
  print "cxtest  Run the project's container test workflow"
}
~~~

Define functions without printing from `.zshenv`, which is also loaded by
non-interactive Zsh:

~~~zsh
# /root/.zshenv
if [[ -r /usr/local/share/project/functions.zsh ]]; then
  source /usr/local/share/project/functions.zsh
fi
~~~

Print the help banner only for interactive shells:

~~~zsh
# /root/.zshrc
[[ -o interactive ]] && cxhelp
~~~

The illustrative host prefix is `dx`; define container functions such as
`cxhelp`, `cxrun`, or `cxtest` in `docker/project-functions.zsh`. Replace both
with short project-specific prefixes, keeping them visibly different. Use a
container prompt label so the user can tell host and container terminals
apart. Do not source the host `.zshrc`: it often contains
host-only Conda, ROS, proxies, absolute paths, or plugins.

## 4. Compose capabilities

Start with an interactive service and add only selected capabilities:

~~~yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.org/simple}
    image: ${PROJECT_IMAGE:-project:dev}
    working_dir: /workspace
    stdin_open: true
    tty: true
    command: ["/usr/bin/zsh", "-l"]
    volumes:
      - type: bind
        source: .
        target: /workspace
      - type: bind
        source: ./outputs
        target: /workspace/outputs
        bind:
          create_host_path: true
~~~

Optional NVIDIA GPU:

~~~yaml
    gpus: all
    shm_size: 2gb
    environment:
      NVIDIA_DRIVER_CAPABILITIES: all
~~~

`shm_size` addresses shared-memory workloads; it does not increase host RAM,
GPU memory, or a container memory limit.

Optional X11/Xwayland:

~~~yaml
    environment:
      DISPLAY: ${DISPLAY:-}
      XAUTHORITY: /tmp/.docker.xauth
    volumes:
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
~~~

Before a GUI command, validate non-empty `DISPLAY`, a readable non-empty
`XAUTHORITY`, and the matching X11 socket. Do not use `xhost +`.

Optional host Oh My Zsh:

~~~yaml
    environment:
      ZSH: /root/.oh-my-zsh
      ZSH_CACHE_DIR: /tmp/oh-my-zsh-cache
    volumes:
      - type: bind
        source: ${HOME}/.oh-my-zsh
        target: /root/.oh-my-zsh
        read_only: true
        bind:
          create_host_path: false
~~~

Document that this makes host Oh My Zsh mandatory at runtime. Prefer a
project-owned `.zshrc` that selects the desired theme and plugins. If
portability is more important, install Oh My Zsh in the image or make a
separate Compose override/profile instead of requiring the host mount.

Persistent datasets, model caches, and outputs should use separate explicit
binds when their lifecycle differs. Add matching root-anchored entries to
`.gitignore` and `.dockerignore` for large local artifacts, while keeping
placeholder files only when empty directories must be versioned.

## 5. Dockerfile and mirrors

Place optional developer-shell work near the bottom:

~~~dockerfile
ARG UBUNTU_APT_MIRROR=http://archive.ubuntu.com/ubuntu
RUN sed -i \
      "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_APT_MIRROR}|g" \
      /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends zsh && \
    rm -rf /var/lib/apt/lists/*

ENV SHELL=/usr/bin/zsh
CMD ["/usr/bin/zsh", "-l"]
~~~

Use build arguments for APT and package indexes so the caller can select a
domestic or official endpoint. Keep version and CUDA compatibility decisions
separate from mirror selection. A Dockerfile cannot reliably change the
registry mirror used to pull its own base image; configure that in the host
Docker daemon. Inspect the base distribution before rewriting APT sources:
newer Ubuntu releases may use deb822 files under `/etc/apt/sources.list.d/`
instead of `/etc/apt/sources.list`.

Never execute host proxy aliases such as `proxyon` inside an image build.
Pass standard proxy build arguments only when the user authorizes them, and do
not persist credentials in image layers.

## 6. Tests and validation

Test behavior before implementation. A useful Compose test renders the model:

~~~python
import subprocess
import yaml


def rendered_service(repo):
    result = subprocess.run(
        ["docker", "compose", "-f", str(repo / "compose.yaml"), "config"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return yaml.safe_load(result.stdout)["services"]["app"]


def test_output_bind_is_persistent(repo):
    volumes = rendered_service(repo)["volumes"]
    output = next(v for v in volumes if v["target"] == "/workspace/outputs")
    assert output["type"] == "bind"
    assert output["source"] == str(repo / "outputs")
~~~

For Zsh functions, put a fake `docker` executable first in `PATH`, source the
real functions file with `/usr/bin/zsh -fc`, invoke one function, and assert
the captured argument vector and exit status. This tests quoting, directory
resolution, service names, and error propagation.

Use this validation ladder:

1. Targeted failing test for the next behavior.
2. Targeted test passes after the minimal edit.
3. `zsh -n` for every changed Zsh file.
4. `docker compose config`.
5. `docker build --check .`.
6. Relevant repository test suite.
7. Image build and interactive/container smoke test when proportionate.

## 7. Common mistakes

| Mistake | Correction |
|---|---|
| One prefix for host and container commands | Use visibly different namespaces and prompt labels |
| Resolve paths from `$PWD` | Resolve from `${(%):-%N}` in the sourced Zsh file |
| Put every device in the base service | Attach optional devices to the command/profile that needs them |
| Mount the host `.zshrc` | Use a project-owned container `.zshrc`; mount Oh My Zsh read-only if required |
| Assume `shm_size` fixes RAM exhaustion | Diagnose host RAM, swap, cgroup limits, and process allocation separately |
| Hard-code a domestic mirror | Parameterize it and retain an official fallback |
| Validate only with text search | Execute Zsh and inspect `docker compose config` |
| Rebuild before cheap checks | Run syntax and configuration validation first |
| Commit generated data and caches | Add precise root-anchored ignore rules and persistent binds |
~~~

- [ ] **Step 2: Verify reference navigation and size**

Run:

~~~bash
sed -n '1,45p' "$HOME/.agents/skills/creating-docker-zsh-workflows/references/patterns.md"
wc -l -w "$HOME/.agents/skills/creating-docker-zsh-workflows/references/patterns.md"
~~~

Expected: the contents list names all seven sections; the file remains below 400 lines and 2,000 words.

### Task 5: Validate structure and generated metadata

**Files:**
- Verify: `~/.agents/skills/creating-docker-zsh-workflows/SKILL.md`
- Verify: `~/.agents/skills/creating-docker-zsh-workflows/agents/openai.yaml`
- Verify: `~/.agents/skills/creating-docker-zsh-workflows/references/patterns.md`

- [ ] **Step 1: Run official structural validation**

Run:

~~~bash
python3 /home/zky-miakho/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  "$HOME/.agents/skills/creating-docker-zsh-workflows"
~~~

Expected: `Skill is valid!`

- [ ] **Step 2: Verify metadata remains aligned**

Run:

~~~bash
sed -n '1,80p' "$HOME/.agents/skills/creating-docker-zsh-workflows/agents/openai.yaml"
~~~

Expected:

~~~yaml
interface:
  display_name: "Creating Docker Zsh Workflows"
  short_description: "Build portable Compose and Zsh developer workflows"
  default_prompt: "Use $creating-docker-zsh-workflows to add a portable Docker Compose and functions.zsh development workflow to this repository."
~~~

- [ ] **Step 3: Scan for project leakage and placeholders**

Run:

~~~bash
rg -n 'robomimic|QingTianRobot|/opt/robomimic|TO''DO|TB''D|PLACE''HOLDER' \
  "$HOME/.agents/skills/creating-docker-zsh-workflows"
~~~

Expected: no matches.

### Task 6: Forward-test the Skill

**Files:**
- Modify only if the forward test exposes a concrete gap:
  `~/.agents/skills/creating-docker-zsh-workflows/SKILL.md`
  or `~/.agents/skills/creating-docker-zsh-workflows/references/patterns.md`

- [ ] **Step 1: Run the same scenario with a fresh agent and the Skill**

Dispatch a fresh subagent with no forked conversation and this exact prompt:

~~~text
Use $creating-docker-zsh-workflows at
/home/zky-miakho/.agents/skills/creating-docker-zsh-workflows to answer this
request:

You are working in an unfamiliar Python GPU repository. The user wants a
one-command interactive Docker Compose development environment, a sourceable
functions.zsh that prints help, a short command for opening a second terminal,
persistent datasets/models/outputs, optional X11 and camera support, host Oh My
Zsh configuration, and domestic mirrors where practical. New Dockerfile work
should stay near the bottom, and unrelated dirty-worktree changes must be
preserved. Describe the exact investigation, design, implementation order,
tests, and validation you would perform. Do not modify files.
~~~

- [ ] **Step 2: Verify GREEN against the same six criteria**

Expected: all six Task 1 criteria pass. The response must explicitly inspect before designing, distinguish host/container prefixes, keep capabilities optional, state test-first order, avoid inherited hard-coding, and use the full validation ladder.

- [ ] **Step 3: Refactor only from observed evidence**

If a criterion fails, add one concise imperative rule or one focused reference example that closes that exact gap, rerun `quick_validate.py`, and repeat the forward test once. Do not add speculative features. Expected final result: all six criteria pass.

### Task 7: Final verification and handoff

**Files:**
- Verify all files under `~/.agents/skills/creating-docker-zsh-workflows/`

- [ ] **Step 1: Run the final verification set**

Run:

~~~bash
python3 /home/zky-miakho/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  "$HOME/.agents/skills/creating-docker-zsh-workflows"
find "$HOME/.agents/skills/creating-docker-zsh-workflows" -maxdepth 3 \
  -type f -printf '%P\n' | sort
rg -n 'TO''DO|TB''D|PLACE''HOLDER|robomimic|/opt/robomimic' \
  "$HOME/.agents/skills/creating-docker-zsh-workflows"
~~~

Expected: validation succeeds; exactly `SKILL.md`, `agents/openai.yaml`, and `references/patterns.md` are listed; the final search has no matches.

- [ ] **Step 2: Check repository isolation**

Run:

~~~bash
git status --short
~~~

Expected: no implementation files changed. The pre-existing untracked `MUJOCO_LOG.TXT` remains untouched; only the plan commit may be ahead of the remote.

- [ ] **Step 3: Report how to invoke the Skill**

Report the installed path and this example:

~~~text
Use $creating-docker-zsh-workflows to add a portable Docker Compose and
functions.zsh development workflow to this repository.
~~~

Also state the baseline failure, forward-test result, structural validation result, and that the user-level Skill is not part of the robomimic Git repository.
