from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "compose.yaml"


def test_dockerfile_pins_numpy_2_compatible_cuda_stack():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM nvidia/cuda:11.8.0-base-ubuntu20.04" in dockerfile
    assert "numpy==2.0.1" in dockerfile
    assert "torch==2.4.1+cu118" in dockerfile
    assert "torchvision==0.19.1+cu118" in dockerfile
    assert "cpuonly" not in dockerfile
    assert "torch==2.0.0" not in dockerfile
    assert "torchvision==0.15.0" not in dockerfile


def test_pytorch_wheels_default_to_an_overridable_domestic_mirror():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    compose = COMPOSE_FILE.read_text(encoding="utf-8")

    assert (
        "ARG PYTORCH_WHEEL_URL="
        "https://mirrors.aliyun.com/pytorch-wheels/cu118"
    ) in dockerfile
    assert '--find-links "${PYTORCH_WHEEL_URL}"' in dockerfile
    assert "--extra-index-url" not in dockerfile
    assert (
        "PYTORCH_WHEEL_URL: ${PYTORCH_WHEEL_URL:-"
        "https://mirrors.aliyun.com/pytorch-wheels/cu118}"
    ) in compose
