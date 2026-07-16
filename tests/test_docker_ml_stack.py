from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"


def test_dockerfile_pins_blackwell_compatible_numpy_2_cuda_stack():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM nvidia/cuda:12.8.1-base-ubuntu22.04" in dockerfile
    assert "numpy==2.0.1" in dockerfile
    assert "torch==2.7.1+cu128" in dockerfile
    assert "torchvision==0.22.1+cu128" in dockerfile
    for obsolete in (
        "nvidia/cuda:11.8.0-base-ubuntu20.04",
        "torch==2.4.1+cu118",
        "torchvision==0.19.1+cu118",
        "cpuonly",
    ):
        assert obsolete not in dockerfile


def test_pytorch_wheels_default_to_overridable_domestic_cu128_mirror():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    mirror = "https://mirrors.aliyun.com/pytorch-wheels/cu128"
    assert f"ARG PYTORCH_WHEEL_URL={mirror}" in dockerfile
    assert '--find-links "${PYTORCH_WHEEL_URL}"' in dockerfile
    assert "--extra-index-url" not in dockerfile
    assert f"PYTORCH_WHEEL_URL: ${{PYTORCH_WHEEL_URL:-{mirror}}}" in compose
