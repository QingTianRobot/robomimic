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
    (rs_root / "robomimic/exps/templates/bc.json").write_text(
        "{}", encoding="utf-8"
    )
    return rs_root


def _fake_python(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable = fake_bin / "python"
    executable.write_text(
        "#!/usr/bin/env zsh\n"
        'print -r -- "UMASK=$(umask) MUJOCO_GL=$MUJOCO_GL $@" '
        '>> "$RS_COMMAND_LOG"\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return fake_bin


def _run(tmp_path, body, *, display="", xauthority=""):
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
    environment["XAUTHORITY"] = xauthority
    result = subprocess.run(
        ["/usr/bin/zsh", "-fc", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, rs_root, log


def test_rsplay_and_training_commands_use_safe_defaults_and_forward_overrides(
    tmp_path,
):
    result, rs_root, log = _run(
        tmp_path,
        "rsplay --n 2; rstrain --name custom-smoke; "
        "rstrain-full --name custom-full",
    )
    assert result.returncode == 0, result.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert all("UMASK=000" in line for line in lines)
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


def test_output_preparation_preserves_the_interactive_shell_umask(tmp_path):
    result, _, _ = _run(
        tmp_path,
        'umask 022; print "before=$(umask)"; rsplay; print "after=$(umask)"',
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines == ["before=022", "after=022"]


def test_repeated_smoke_training_uses_unique_default_run_names(tmp_path):
    result, _, log = _run(tmp_path, "rstrain; rstrain")
    assert result.returncode == 0, result.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    names = []
    for line in lines:
        marker = "--name "
        name = line.split(marker, 1)[1].split(" ", 1)[0]
        names.append(name)

    assert len(names) == 2
    assert all(name.startswith("lift-bc-smoke-") for name in names)
    assert names[0] != names[1]


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
        f"source {shlex.quote(str(FUNCTIONS))}; "
        "rslatest; rseval --n_rollouts 2"
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


def test_gui_commands_reject_the_empty_compose_xauthority_mount(tmp_path):
    playback, _, playback_log = _run(
        tmp_path / "playback",
        "rsplay-gui",
        display=":99",
        xauthority="/dev/null",
    )
    assert playback.returncode != 0
    assert "XAUTHORITY" in playback.stderr
    assert not playback_log.exists()

    rollout, _, rollout_log = _run(
        tmp_path / "rollout",
        'print checkpoint > "$RS_TRAINING_ROOT/run/models/latest.pth"; '
        "rseval-gui",
        display=":99",
        xauthority="/dev/null",
    )
    assert rollout.returncode != 0
    assert "XAUTHORITY" in rollout.stderr
    assert not rollout_log.exists()


def test_rshelp_and_install_hooks_are_present():
    functions = FUNCTIONS.read_text(encoding="utf-8")
    zshenv_path = ROOT / "docker/robomimic.zshenv"
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
    assert zshenv_path.is_file()
    zshenv = zshenv_path.read_text(encoding="utf-8")
    assert "source /usr/local/share/robomimic/robomimic-functions.zsh" in zshenv
    assert "robomimic-functions.zsh" in zshrc
    assert "COPY docker/robomimic-functions.zsh" in dockerfile
    assert "COPY docker/robomimic.zshenv /root/.zshenv" in dockerfile


def test_rshelp_shows_default_paths_and_a_copyable_safe_workflow(tmp_path):
    result, rs_root, _ = _run(tmp_path, "rshelp")
    assert result.returncode == 0, result.stderr
    for snippet in (
        str(rs_root / "datasets/lift/ph/low_dim_v15.hdf5"),
        str(rs_root / "outputs/training"),
        str(rs_root / "outputs/videos"),
        "rsstatus",
        "rsplay",
        "rstrain",
        "rslatest",
        "rseval",
        "rstrain-full",
    ):
        assert snippet in result.stdout
