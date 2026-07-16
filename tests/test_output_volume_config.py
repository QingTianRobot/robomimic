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
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "outputs/training/model.pth",
        ],
        cwd=ROOT,
    )
    assert result.returncode == 0
