# Host-Persisted Dataset Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `rmdataset` Zsh command that resolves robomimic dataset selections from the repository registry, downloads them with host `curl`, persists them under `./datasets`, and exposes them at `/opt/robomimic/datasets` in Compose containers.

**Architecture:** A pure Python manifest resolver owns argument validation and registry traversal without importing Hugging Face or CLIP code. The host Zsh function consumes tab-separated records and performs resumable, atomic curl downloads using the host's proxy environment; Compose only supplies the persistent dataset bind mount.

**Tech Stack:** Python 3 standard library, Zsh, curl, Docker Compose, pytest.

---

## File Structure

- Create `robomimic/scripts/resolve_dataset_downloads.py`: pure registry-to-manifest resolver and CLI.
- Create `tests/test_resolve_dataset_downloads.py`: selector expansion, URL, path, and CLI tests.
- Modify `function.zsh`: add `rmdataset` and help text.
- Create `tests/test_dataset_download_function.py`: execute the real Zsh function against fake resolver and curl programs.
- Modify `compose.yaml`: add the explicit host dataset bind mount.
- Modify `.gitignore`: exclude repository datasets.
- Modify `.dockerignore`: exclude repository datasets from image contexts.
- Create `tests/test_dataset_volume_config.py`: verify Compose mount and ignore behavior.

### Task 1: Pure Dataset Manifest Resolver

**Files:**
- Create: `robomimic/scripts/resolve_dataset_downloads.py`
- Create: `tests/test_resolve_dataset_downloads.py`

- [ ] **Step 1: Write failing resolver tests**

Create `tests/test_resolve_dataset_downloads.py`:

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest

from robomimic.scripts.resolve_dataset_downloads import resolve_downloads


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "robomimic" / "scripts" / "resolve_dataset_downloads.py"


def test_default_selection_resolves_lift_ph_low_dim():
    records = resolve_downloads(
        tasks=["lift"],
        dataset_types=["ph"],
        hdf5_types=["low_dim"],
        endpoint="https://huggingface.co",
    )

    assert records == [
        {
            "task": "lift",
            "dataset_type": "ph",
            "hdf5_type": "low_dim",
            "url": (
                "https://huggingface.co/datasets/robomimic/"
                "robomimic_datasets/resolve/main/v1.5/lift/ph/"
                "low_dim_v15.hdf5"
            ),
            "relative_path": "lift/ph/low_dim_v15.hdf5",
        }
    ]


def test_aliases_and_none_urls_are_handled_from_registry():
    sim_records = resolve_downloads(
        tasks=["sim"],
        dataset_types=["ph"],
        hdf5_types=["low_dim"],
        endpoint="https://example.invalid/",
    )
    assert [record["task"] for record in sim_records] == [
        "lift",
        "can",
        "square",
        "transport",
        "tool_hang",
    ]
    assert all(record["url"].startswith("https://example.invalid/") for record in sim_records)

    real_records = resolve_downloads(
        tasks=["real"],
        dataset_types=["ph"],
        hdf5_types=["raw"],
        endpoint="https://example.invalid",
    )
    assert [record["task"] for record in real_records] == [
        "lift_real",
        "can_real",
        "tool_hang_real",
    ]
    assert all(record["url"].startswith("http://downloads.cs.stanford.edu/") for record in real_records)

    no_image_records = resolve_downloads(
        tasks=["lift"],
        dataset_types=["ph"],
        hdf5_types=["image"],
        endpoint="https://huggingface.co",
    )
    assert no_image_records == []


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"tasks": ["unknown"], "dataset_types": ["ph"], "hdf5_types": ["low_dim"]}, "unknown task"),
        ({"tasks": ["all", "lift"], "dataset_types": ["ph"], "hdf5_types": ["low_dim"]}, "must be used alone"),
        ({"tasks": ["lift"], "dataset_types": ["unknown"], "hdf5_types": ["low_dim"]}, "unknown dataset type"),
        ({"tasks": ["lift"], "dataset_types": ["ph"], "hdf5_types": ["unknown"]}, "unknown hdf5 type"),
    ],
)
def test_invalid_selection_has_a_clear_error(kwargs, message):
    with pytest.raises(ValueError, match=message):
        resolve_downloads(endpoint="https://huggingface.co", **kwargs)


def test_cli_emits_tsv_and_marks_dry_run():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--tasks",
            "can",
            "--dataset_types",
            "paired",
            "--hdf5_types",
            "low_dim",
            "--dry_run",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "ROBOMIMIC_DATASET_ENDPOINT": "https://huggingface.co",
        },
    )

    fields = result.stdout.strip().split("\t")
    assert fields == [
        "can",
        "paired",
        "low_dim",
        (
            "https://huggingface.co/datasets/robomimic/"
            "robomimic_datasets/resolve/main/v1.5/can/paired/"
            "low_dim_v15.hdf5"
        ),
        "can/paired/low_dim_v15.hdf5",
        "1",
    ]
```

- [ ] **Step 2: Run the resolver tests and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_resolve_dataset_downloads.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'robomimic.scripts.resolve_dataset_downloads'`.

- [ ] **Step 3: Implement the pure resolver**

Create `robomimic/scripts/resolve_dataset_downloads.py`:

```python
import argparse
import os

from robomimic import DATASET_REGISTRY, HF_REPO_ID


TASK_ALIASES = {
    "all": list(DATASET_REGISTRY),
    "sim": [task for task in DATASET_REGISTRY if "real" not in task],
    "real": [task for task in DATASET_REGISTRY if "real" in task],
}


def _ordered_unique(values):
    return list(dict.fromkeys(values))


DATASET_TYPES = _ordered_unique(
    dataset_type
    for task in DATASET_REGISTRY.values()
    for dataset_type in task
)
HDF5_TYPES = _ordered_unique(
    hdf5_type
    for task in DATASET_REGISTRY.values()
    for dataset_type in task.values()
    for hdf5_type in dataset_type
)


def _expand(values, *, aliases, allowed, label):
    selected_aliases = [value for value in values if value in aliases]
    if selected_aliases:
        if len(values) != 1:
            raise ValueError(f"{selected_aliases[0]} must be used alone for {label}")
        return list(aliases[selected_aliases[0]])

    unknown = [value for value in values if value not in allowed]
    if unknown:
        raise ValueError(f"unknown {label}: {unknown[0]}")
    return list(values)


def resolve_downloads(tasks, dataset_types, hdf5_types, endpoint):
    selected_tasks = _expand(
        tasks,
        aliases=TASK_ALIASES,
        allowed=list(DATASET_REGISTRY),
        label="task",
    )
    selected_dataset_types = _expand(
        dataset_types,
        aliases={"all": DATASET_TYPES},
        allowed=DATASET_TYPES,
        label="dataset type",
    )
    selected_hdf5_types = _expand(
        hdf5_types,
        aliases={"all": HDF5_TYPES},
        allowed=HDF5_TYPES,
        label="hdf5 type",
    )

    endpoint = endpoint.rstrip("/")
    records = []
    for task, task_registry in DATASET_REGISTRY.items():
        if task not in selected_tasks:
            continue
        for dataset_type, dataset_registry in task_registry.items():
            if dataset_type not in selected_dataset_types:
                continue
            for hdf5_type, metadata in dataset_registry.items():
                if hdf5_type not in selected_hdf5_types:
                    continue
                link = metadata["url"]
                if link is None:
                    continue
                if "real" in task:
                    url = link
                else:
                    url = (
                        f"{endpoint}/datasets/{HF_REPO_ID}/resolve/main/{link}"
                    )
                records.append(
                    {
                        "task": task,
                        "dataset_type": dataset_type,
                        "hdf5_type": hdf5_type,
                        "url": url,
                        "relative_path": (
                            f"{task}/{dataset_type}/{os.path.basename(link)}"
                        ),
                    }
                )
    return records


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="+", default=["lift"])
    parser.add_argument("--dataset_types", nargs="+", default=["ph"])
    parser.add_argument("--hdf5_types", nargs="+", default=["low_dim"])
    parser.add_argument("--dry_run", action="store_true")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        records = resolve_downloads(
            tasks=args.tasks,
            dataset_types=args.dataset_types,
            hdf5_types=args.hdf5_types,
            endpoint=os.environ.get(
                "ROBOMIMIC_DATASET_ENDPOINT",
                "https://huggingface.co",
            ),
        )
    except ValueError as error:
        parser.error(str(error))

    if not records:
        parser.error("no downloadable datasets matched the selection")

    dry_run = "1" if args.dry_run else "0"
    for record in records:
        print(
            "\t".join(
                [
                    record["task"],
                    record["dataset_type"],
                    record["hdf5_type"],
                    record["url"],
                    record["relative_path"],
                    dry_run,
                ]
            )
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the resolver tests and verify GREEN**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_resolve_dataset_downloads.py
```

Expected: all resolver tests pass.

- [ ] **Step 5: Commit the resolver**

```bash
git add robomimic/scripts/resolve_dataset_downloads.py tests/test_resolve_dataset_downloads.py
git commit -m "feat: resolve dataset download manifests"
```

### Task 2: Host `rmdataset` Function

**Files:**
- Modify: `function.zsh`
- Create: `tests/test_dataset_download_function.py`

- [ ] **Step 1: Write failing function behavior tests**

Create `tests/test_dataset_download_function.py`:

```python
import os
import shlex
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "function.zsh"


def _write_fake_repo(tmp_path, *, dry_run):
    fake_repo = tmp_path / "repo"
    resolver = fake_repo / "robomimic" / "scripts" / "resolve_dataset_downloads.py"
    resolver.parent.mkdir(parents=True)
    resolver.write_text(
        "print(" + repr(
            "lift\tph\tlow_dim\thttps://example.invalid/data.hdf5\t"
            f"lift/ph/low_dim_v15.hdf5\t{1 if dry_run else 0}"
        ) + ")\n",
        encoding="utf-8",
    )
    return fake_repo


def _write_fake_curl(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env zsh\n"
        "print -r -- \"$@\" >> \"$CURL_LOG\"\n"
        "local output\n"
        "while (( $# )); do\n"
        "  if [[ \"$1\" == --output ]]; then\n"
        "    shift\n"
        "    output=\"$1\"\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "print -n 'dataset-bytes' > \"$output\"\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    return fake_bin


def _run_function(fake_repo, fake_bin, curl_log, *args):
    command = (
        f"source {shlex.quote(str(FUNCTIONS))} >/dev/null; "
        f"ROBOMIMIC_REPO_DIR={shlex.quote(str(fake_repo))}; "
        "rmdataset "
        + " ".join(shlex.quote(argument) for argument in args)
    )
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["CURL_LOG"] = str(curl_log)
    return subprocess.run(
        ["/usr/bin/zsh", "-fc", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_rmdataset_downloads_atomically_and_skips_completed_file(tmp_path):
    fake_repo = _write_fake_repo(tmp_path, dry_run=False)
    fake_bin = _write_fake_curl(tmp_path)
    curl_log = tmp_path / "curl.log"

    first = _run_function(
        fake_repo,
        fake_bin,
        curl_log,
        "--tasks",
        "lift",
        "--dataset_types",
        "ph",
        "--hdf5_types",
        "low_dim",
    )
    assert first.returncode == 0, first.stderr

    target = fake_repo / "datasets" / "lift" / "ph" / "low_dim_v15.hdf5"
    assert target.read_text(encoding="utf-8") == "dataset-bytes"
    assert not Path(f"{target}.part").exists()

    curl_arguments = curl_log.read_text(encoding="utf-8")
    for option in (
        "--fail",
        "--location",
        "--continue-at -",
        "--retry 5",
        "--retry-all-errors",
        f"--output {target}.part",
    ):
        assert option in curl_arguments

    second = _run_function(fake_repo, fake_bin, curl_log)
    assert second.returncode == 0, second.stderr
    assert "已存在，跳过" in second.stdout
    assert len(curl_log.read_text(encoding="utf-8").splitlines()) == 1


def test_rmdataset_dry_run_does_not_call_curl_or_create_dataset_dir(tmp_path):
    fake_repo = _write_fake_repo(tmp_path, dry_run=True)
    fake_bin = _write_fake_curl(tmp_path)
    curl_log = tmp_path / "curl.log"

    result = _run_function(fake_repo, fake_bin, curl_log, "--dry_run")

    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert not curl_log.exists()
    assert not (fake_repo / "datasets").exists()


def test_rmhelp_lists_dataset_command():
    result = subprocess.run(
        [
            "/usr/bin/zsh",
            "-fc",
            f"source {shlex.quote(str(FUNCTIONS))}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "rmdataset" in result.stdout
    assert "--tasks lift can" in result.stdout
```

- [ ] **Step 2: Run the function tests and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_download_function.py
```

Expected: failures report `rmdataset: command not found` and missing help text.

- [ ] **Step 3: Implement `rmdataset` and help text**

Add this function before `rmhelp` in `function.zsh`:

```zsh
rmdataset() {
  local resolver="$ROBOMIMIC_REPO_DIR/robomimic/scripts/resolve_dataset_downloads.py"
  local endpoint="${ROBOMIMIC_DATASET_ENDPOINT:-https://huggingface.co}"
  local manifest

  if ! command -v python3 >/dev/null 2>&1; then
    print -u2 '缺少宿主机命令：python3'
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    print -u2 '缺少宿主机命令：curl'
    return 1
  fi
  if [[ ! -f "$resolver" ]]; then
    print -u2 "找不到数据集清单解析器：$resolver"
    return 1
  fi

  manifest="$(
    PYTHONPATH="$ROBOMIMIC_REPO_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      ROBOMIMIC_DATASET_ENDPOINT="$endpoint" \
      python3 "$resolver" "$@"
  )" || return 1

  local task dataset_type hdf5_type url relative_path dry_run
  local destination partial
  while IFS=$'\t' read -r task dataset_type hdf5_type url relative_path dry_run; do
    [[ -z "$url" ]] && continue
    destination="$ROBOMIMIC_REPO_DIR/datasets/$relative_path"

    if [[ "$dry_run" == 1 ]]; then
      print "[DRY RUN] $task/$dataset_type/$hdf5_type"
      print "  URL：$url"
      print "  宿主机：$destination"
      print "  容器：/opt/robomimic/datasets/$relative_path"
      continue
    fi

    if [[ -s "$destination" ]]; then
      print "数据集已存在，跳过：$destination"
      continue
    fi

    if ! mkdir -p "${destination:h}"; then
      print -u2 "无法创建数据集目录：${destination:h}"
      return 1
    fi

    partial="${destination}.part"
    print "正在下载：$task/$dataset_type/$hdf5_type"
    print "  $url"
    if ! curl \
      --fail \
      --show-error \
      --location \
      --continue-at - \
      --retry 5 \
      --retry-delay 2 \
      --retry-all-errors \
      --output "$partial" \
      "$url"; then
      print -u2 "下载失败，保留断点文件：$partial"
      return 1
    fi

    if ! mv -- "$partial" "$destination"; then
      print -u2 "下载完成但无法写入最终文件：$destination"
      return 1
    fi
    print "下载完成：$destination"
  done <<< "$manifest"
}
```

Add these lines inside `rmhelp` before the existing `rmhelp` line:

```zsh
  print '  rmdataset          下载默认 Lift PH low-dim 数据集到宿主机'
  print '  rmdataset --tasks lift can --dataset_types ph --hdf5_types low_dim'
  print '                     使用原 download_datasets.py 参数选择数据集'
  print '  rmdataset --tasks sim --dataset_types ph --hdf5_types low_dim --dry_run'
  print '                     仅展示下载清单，不传输文件'
```

- [ ] **Step 4: Run the function tests and verify GREEN**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_download_function.py
```

Expected: all function tests pass.

- [ ] **Step 5: Commit the function**

```bash
git add function.zsh tests/test_dataset_download_function.py
git commit -m "feat: add host dataset download shortcut"
```

### Task 3: Compose Dataset Volume and Ignore Rules

**Files:**
- Modify: `compose.yaml`
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Create: `tests/test_dataset_volume_config.py`

- [ ] **Step 1: Write failing Compose and ignore tests**

Create `tests/test_dataset_volume_config.py`:

```python
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _resolved_service():
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


def test_dataset_directory_is_a_writable_explicit_bind_mount():
    service = _resolved_service()
    dataset_mount = next(
        volume
        for volume in service["volumes"]
        if volume["target"] == "/opt/robomimic/datasets"
    )

    assert dataset_mount["type"] == "bind"
    assert Path(dataset_mount["source"]) == ROOT / "datasets"
    assert dataset_mount.get("read_only", False) is False


def test_dataset_directory_is_ignored_by_git_and_docker():
    for ignore_file in (".gitignore", ".dockerignore"):
        lines = (ROOT / ignore_file).read_text(encoding="utf-8").splitlines()
        assert "/datasets/" in lines

    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "datasets/lift/ph/low_dim_v15.hdf5",
        ],
        cwd=ROOT,
    )
    assert ignored.returncode == 0
```

- [ ] **Step 2: Run the volume tests and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_volume_config.py
```

Expected: the mount lookup raises `StopIteration` and `/datasets/` assertions fail.

- [ ] **Step 3: Add the explicit dataset mount and ignores**

Add this volume immediately after the repository bind mount in `compose.yaml`:

```yaml
      - type: bind
        source: ./datasets
        target: /opt/robomimic/datasets
        bind:
          create_host_path: true
```

Add this entry near the local cache entries in both `.gitignore` and `.dockerignore`:

```text
# local downloaded datasets
/datasets/
```

- [ ] **Step 4: Run the volume tests and verify GREEN**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_dataset_volume_config.py
```

Expected: both volume and ignore tests pass.

- [ ] **Step 5: Commit the mount and ignore rules**

```bash
git add compose.yaml .gitignore .dockerignore tests/test_dataset_volume_config.py
git commit -m "feat: persist datasets through compose"
```

### Task 4: Runtime Download and Full Regression Verification

**Files:**
- Verify: `datasets/lift/ph/low_dim_v15.hdf5` (ignored runtime artifact)
- Verify: all implementation and test files from Tasks 1-3

- [ ] **Step 1: Run all focused automated tests**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider \
  tests/test_resolve_dataset_downloads.py \
  tests/test_dataset_download_function.py \
  tests/test_dataset_volume_config.py \
  tests/test_clip_model_cache_config.py \
  tests/test_lang_utils_cache.py \
  tests/test_docker_ml_stack.py \
  tests/test_notify_feishu.py \
  tests/test_publish_workflow.py
```

Expected: all selected tests and subtests pass.

- [ ] **Step 2: Run static repository and Docker checks**

Run:

```bash
git diff --check
docker compose config --quiet
docker build --check .
```

Expected: all three commands exit zero and Docker reports no warnings.

- [ ] **Step 3: Verify the dry-run user interface without network transfer**

Run:

```bash
/usr/bin/zsh -lc 'source ./function.zsh >/dev/null; rmdataset --tasks lift --dataset_types ph --hdf5_types low_dim --dry_run'
```

Expected: output includes the official Hugging Face URL, the host path ending in `datasets/lift/ph/low_dim_v15.hdf5`, and the matching container path; no `.part` or completed dataset is created by this command.

- [ ] **Step 4: Download the default dataset through host curl**

Run with the user's existing `proxyon` environment active:

```bash
/usr/bin/zsh -lc 'source ./function.zsh >/dev/null; rmdataset --tasks lift --dataset_types ph --hdf5_types low_dim'
```

Expected: curl follows the Hugging Face/Xet redirects, downloads approximately 20 MB, and atomically creates `datasets/lift/ph/low_dim_v15.hdf5` with no remaining `.part` file.

- [ ] **Step 5: Confirm the Compose container sees the host file**

Run:

```bash
HOST_SHA=$(sha256sum datasets/lift/ph/low_dim_v15.hdf5 | awk '{print $1}')
CONTAINER_SHA=$(docker compose run --rm --no-deps -T robomimic sha256sum /opt/robomimic/datasets/lift/ph/low_dim_v15.hdf5 | awk '{print $1}')
test "$HOST_SHA" = "$CONTAINER_SHA"
printf 'host=%s\ncontainer=%s\n' "$HOST_SHA" "$CONTAINER_SHA"
```

Expected: host and container SHA-256 values are identical.

- [ ] **Step 6: Confirm an immediate second invocation skips curl**

Run:

```bash
/usr/bin/zsh -lc 'source ./function.zsh >/dev/null; rmdataset --tasks lift --dataset_types ph --hdf5_types low_dim'
```

Expected: output contains `数据集已存在，跳过` and returns immediately.

- [ ] **Step 7: Review final status without adding runtime data**

Run:

```bash
git status --short
git check-ignore -v datasets/lift/ph/low_dim_v15.hdf5
```

Expected: the dataset is ignored, `MUJOCO_LOG.TXT` remains untouched, and no implementation changes are left uncommitted after the task commits.
