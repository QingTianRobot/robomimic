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
        "print("
        + repr(
            "lift\tph\tlow_dim\thttps://example.invalid/data.hdf5\t"
            f"lift/ph/low_dim_v15.hdf5\t{1 if dry_run else 0}"
        )
        + ")\n",
        encoding="utf-8",
    )
    return fake_repo


def _write_fake_curl(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/usr/bin/env zsh\n"
        'print -r -- "$@" >> "$CURL_LOG"\n'
        "typeset output\n"
        "while (( $# )); do\n"
        '  if [[ "$1" == --output ]]; then\n'
        "    shift\n"
        '    output="$1"\n'
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
