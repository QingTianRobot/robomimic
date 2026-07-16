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
            raise ValueError(
                f"{selected_aliases[0]} must be used alone for {label}"
            )
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
