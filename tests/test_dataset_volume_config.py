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
