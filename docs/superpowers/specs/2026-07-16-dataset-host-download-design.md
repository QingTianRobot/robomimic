# Host-Persisted Dataset Download Design

## Goal

Provide a `function.zsh` command that accepts the same dataset-selection
arguments as `robomimic/scripts/download_datasets.py`, downloads files through
the host's working network and proxy configuration, stores them under the
repository, and exposes the same files to every Compose container through an
explicit bind mount.

## Root Cause

The current Compose service sets `HF_ENDPOINT=https://hf-mirror.com`, but it
does not pass host proxy variables into the container. Dataset resolution
redirects from Hugging Face to `cas-bridge.xethub.hf.co`; direct TLS handshakes
from the container time out, and `huggingface_hub` reports the network failure
as `LocalEntryNotFoundError` because the requested file is not already cached.

The same dataset URL succeeds from the host with `curl` while the host's
`proxyon` environment is active. Python `requests` is not selected as the host
transport because it reproduced a TLS EOF failure through the same proxy,
whereas `curl` reached the final object and returned `200 OK`.

## Architecture

The download workflow has two responsibilities:

1. A small Python manifest resolver reads robomimic's existing
   `DATASET_REGISTRY`, applies the same `--tasks`, `--dataset_types`,
   `--hdf5_types`, and `--dry_run` selection rules, and emits machine-readable
   download records. It does not import the Hugging Face client or load CLIP.
2. The host-side `rmdataset` Zsh function consumes those records and downloads
   each URL with host `curl`. This automatically uses proxy variables exported
   by `proxyon` without attempting to translate loopback addresses into a
   container network.

The resolver remains the single place that interprets command-line selection.
Dataset URLs and horizons remain owned by `robomimic.DATASET_REGISTRY`; the Zsh
function does not hard-code task-specific URLs.

## Storage and Container Mount

Datasets are stored at:

```text
<repository>/datasets/<task>/<dataset_type>/<filename>
```

Compose explicitly bind-mounts the directory as:

```text
./datasets -> /opt/robomimic/datasets
```

The container working directory remains `/opt/robomimic`, so existing training
commands can continue to reference paths such as:

```text
datasets/lift/ph/low_dim_v15.hdf5
```

Both `.gitignore` and `.dockerignore` ignore `/datasets/` so downloaded HDF5
files cannot be committed accidentally or copied into image build contexts.

## Command Interface

After sourcing `function.zsh`, the default command downloads Lift PH low-dim:

```zsh
rmdataset
```

The function accepts the downloader's existing arguments without translating
them into a different positional syntax:

```zsh
rmdataset \
  --tasks lift can \
  --dataset_types ph \
  --hdf5_types low_dim
```

Selection-only mode remains available:

```zsh
rmdataset \
  --tasks sim \
  --dataset_types ph \
  --hdf5_types low_dim \
  --dry_run
```

`rmhelp` documents these forms and identifies the host and container dataset
paths.

## Download Behavior

For each manifest record, `rmdataset`:

1. Creates the target directory under `<repository>/datasets`.
2. Skips a non-empty completed destination file and prints its path.
3. Downloads to `<filename>.part` with `curl --fail --location`.
4. Resumes an existing partial file with `--continue-at -`.
5. Retries transient failures with bounded retries and `--retry-all-errors`.
6. Atomically renames the completed `.part` file to the final filename.

The default Hugging Face base URL is `https://huggingface.co`, which is the
endpoint proven to work with host `curl`. It can be overridden for one command
with `ROBOMIMIC_DATASET_ENDPOINT`. Real-robot entries keep their Stanford URLs
from `DATASET_REGISTRY` and do not use the Hugging Face base URL.

No completed dataset is overwritten automatically. To fetch it again, the user
removes the completed file first. An interrupted `.part` file is intentionally
preserved for the next invocation to resume.

## Error Handling

The function exits non-zero and prints a concise diagnostic when:

- `python3` or `curl` is missing on the host;
- selection arguments are invalid;
- no downloadable dataset matches the selection;
- directory creation fails;
- `curl` exhausts its retries; or
- the final atomic rename fails.

On a transfer failure, the `.part` file remains available for resume. The
function must not print a successful completion message for a failed transfer.

## Testing and Verification

Automated tests cover:

- default Lift PH low-dim manifest resolution;
- `all`, `sim`, and `real` task expansion;
- dataset-type and HDF5-type filtering;
- skipped registry entries whose URL is `None`;
- Hugging Face and Stanford URL construction;
- output paths under `datasets/<task>/<dataset_type>`;
- `--dry_run` producing no transfer;
- Compose resolving the explicit dataset bind mount;
- `/datasets/` being ignored by Git and Docker;
- `function.zsh` exposing `rmdataset` and documenting it in `rmhelp`;
- curl retry, redirect, resume, temporary-file, and atomic-rename contracts.

Final runtime verification downloads the approximately 20 MB Lift PH low-dim
dataset, confirms it exists on the host, confirms the Compose container sees
the identical file at `/opt/robomimic/datasets/lift/ph/low_dim_v15.hdf5`, and
checks that an immediate second invocation skips the completed file.
