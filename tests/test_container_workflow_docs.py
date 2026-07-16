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
