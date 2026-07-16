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
    assert all(
        record["url"].startswith("https://example.invalid/")
        for record in sim_records
    )

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
    assert all(
        record["url"].startswith("http://downloads.cs.stanford.edu/")
        for record in real_records
    )

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
        (
            {
                "tasks": ["unknown"],
                "dataset_types": ["ph"],
                "hdf5_types": ["low_dim"],
            },
            "unknown task",
        ),
        (
            {
                "tasks": ["all", "lift"],
                "dataset_types": ["ph"],
                "hdf5_types": ["low_dim"],
            },
            "must be used alone",
        ),
        (
            {
                "tasks": ["lift"],
                "dataset_types": ["unknown"],
                "hdf5_types": ["low_dim"],
            },
            "unknown dataset type",
        ),
        (
            {
                "tasks": ["lift"],
                "dataset_types": ["ph"],
                "hdf5_types": ["unknown"],
            },
            "unknown hdf5 type",
        ),
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
