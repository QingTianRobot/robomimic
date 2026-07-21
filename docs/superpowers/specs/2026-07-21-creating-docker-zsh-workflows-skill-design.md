# Reusable Docker Compose and Zsh Workflow Skill Design

## Goal

Create a user-level Codex Skill that helps build reusable Docker Compose and
Zsh shortcut workflows in different repositories. The Skill must generalize
the lessons from this repository without copying robomimic-specific service
names, paths, commands, CUDA versions, or training behavior into unrelated
projects.

The Skill will live at:

```text
~/.agents/skills/creating-docker-zsh-workflows/
```

## Trigger and scope

The Skill should trigger when a user asks to create or revise any combination
of:

- a `compose.yaml` or `docker-compose.yml` development service;
- a sourceable `functions.zsh` command library;
- separate host and container shortcut commands;
- Zsh or Oh My Zsh integration in an image;
- GPU, X11/Xwayland, camera, device, shared-memory, or interactive-terminal
  support;
- persistent model, dataset, cache, output, or source bind mounts;
- domestic APT, Conda, PyPI, PyTorch, or Hugging Face mirrors.

It will not act as a fixed robomimic scaffold or silently impose GPU, GUI,
camera, mirror, volume, or shell requirements on projects that do not need
them.

## Skill structure

Use a small procedural Skill with one selectively loaded reference:

```text
creating-docker-zsh-workflows/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── patterns.md
```

`SKILL.md` will contain the decision-making and implementation workflow.
`references/patterns.md` will contain adaptable examples and validation
patterns for Docker Compose, host Zsh functions, container Zsh functions,
Dockerfile integration, GUI authorization, GPU/device access, persistence, and
mirrors. No generator script or copy-ready whole-project template will be
included because repository layouts and runtime requirements vary too much.

## Workflow

When the Skill is used, the agent will:

1. Inspect repository guidance, dirty worktree state, Dockerfiles, Compose
   files, shell startup files, existing shortcut libraries, documentation, and
   tests before proposing changes.
2. Determine the service name, host and container responsibilities, command
   prefixes, interactive behavior, runtime devices, persistence needs, shell
   configuration, and mirror policy. It must ask only for choices that cannot
   be derived safely from the repository.
3. Present a focused design before implementation. Host commands will manage
   Docker lifecycle and host downloads; container commands will run project
   workflows. The two command namespaces must remain visually distinct.
4. Add failing tests before changing behavior. Tests should cover rendered
   Compose configuration and real Zsh behavior rather than only searching for
   strings.
5. Make the minimum changes needed. New Dockerfile layers should remain near
   the bottom when possible so expensive dependency layers retain their cache.
6. Validate syntax and behavior, then report exact entry commands, persistent
   host paths, and any GUI or device prerequisites.

The Skill will not commit or push unless the user explicitly asks for those
repository mutations.

## Reusable patterns

The reference will document these patterns without hard-coded project names:

- Resolve the repository directory from the sourced Zsh file rather than the
  caller's current working directory.
- Create bind-source directories before starting Compose when the service
  expects them to exist.
- Use `docker compose run --rm SERVICE` for a disposable interactive shell and
  discover a running Compose container by labels before using `docker exec`
  for additional terminals.
- Print an accurate help summary when a function library is sourced.
- Prefer long-form bind mounts when source/target intent or creation behavior
  matters; mount configuration directories read-only where appropriate.
- Treat `DISPLAY`, `XAUTHORITY`, X11 sockets, GPU access, cameras, and other
  devices as optional capabilities with explicit prerequisites and actionable
  error messages.
- Parameterize domestic mirrors with build arguments or environment variables
  so official sources remain usable as fallbacks.
- Keep host-only setup out of container shell startup and make non-interactive
  Zsh activation deterministic.
- Preserve unrelated user changes and avoid destructive cleanup.

## Error handling

Generated workflows must fail early with readable diagnostics when commands,
files, devices, display authorization, or persistent inputs are missing.
Optional capabilities must not break image-only builds. A missing desktop
session, camera, Oh My Zsh installation, or local model directory should only
block the command that actually requires it unless the user explicitly makes
that dependency mandatory.

## Testing strategy

Skill development will follow RED-GREEN-REFACTOR for process documentation:

1. Give a fresh agent a realistic cross-project request without this Skill and
   record omissions, hard-coded assumptions, or unverifiable recommendations.
2. Create the minimum Skill that addresses the observed failures.
3. Give a fresh agent the same request with the Skill and verify it inspects
   context, separates host/container concerns, adds tests first, and proposes
   portable configuration.
4. Refine the Skill only when the forward test reveals a concrete gap.

Validate the final Skill with the official `quick_validate.py` tool. Validate
example workflow changes with the target repository's tests plus relevant
commands such as:

```text
zsh -n functions.zsh
docker compose config
docker build --check .
```

Run a build or container smoke test when it is proportionate to the requested
change and required dependencies are available.

## Success criteria

- Codex discovers the Skill for Docker Compose plus Zsh workflow requests.
- The Skill is available to projects outside this repository.
- Its instructions adapt to the inspected project instead of cloning
  robomimic-specific configuration.
- Host and container command responsibilities are explicit and tested.
- Optional GPU, GUI, camera, volume, Oh My Zsh, and mirror features are included
  only when required.
- The Skill passes structural validation and a realistic forward test.
