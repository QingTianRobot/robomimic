# robomimic Docker shortcuts for Zsh.
# Load once in a host terminal with: source /path/to/robomimic/function.zsh

# Resolve the repository from this file instead of the caller's current directory.
typeset -g ROBOMIMIC_REPO_DIR="${${(%):-%N}:A:h}"

_robomimic_container_id() {
  docker ps \
    --filter label=com.docker.compose.project=robomimic \
    --filter label=com.docker.compose.service=robomimic \
    --format '{{.ID}}' | head -n 1
}

rmrun() {
  (
    cd "$ROBOMIMIC_REPO_DIR" || return 1
    docker compose run --rm robomimic
  )
}

rmcam() {
  local camera_device="${1:-/dev/video0}"

  if [[ ! -e "$camera_device" ]]; then
    print -u2 "摄像头设备不存在：$camera_device"
    print -u2 "可先运行：ls -l /dev/video*"
    return 1
  fi

  (
    cd "$ROBOMIMIC_REPO_DIR" || return 1
    docker compose run --rm \
      --device "$camera_device:$camera_device" \
      robomimic
  )
}

rmshell() {
  local container_id
  container_id="$(_robomimic_container_id)"

  if [[ -z "$container_id" ]]; then
    print -u2 "没有正在运行的 robomimic 容器。"
    print -u2 "请先运行 rmrun，或使用 rmcam 启动带摄像头的容器。"
    return 1
  fi

  docker exec -it \
    -w /opt/robomimic \
    "$container_id" \
    /usr/bin/zsh -l
}

rmps() {
  docker ps \
    --filter label=com.docker.compose.project=robomimic \
    --filter label=com.docker.compose.service=robomimic \
    --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
}

rmdataset() {
  local resolver="$ROBOMIMIC_REPO_DIR/robomimic/scripts/resolve_dataset_downloads.py"
  local endpoint="${ROBOMIMIC_DATASET_ENDPOINT:-https://huggingface.co}"
  local manifest

  if ! command -v python3 >/dev/null 2>&1; then
    print -u2 '缺少宿主机命令：python3'
    return 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    print -u2 '缺少宿主机命令：curl'
    return 1
  fi
  if [[ ! -f "$resolver" ]]; then
    print -u2 "找不到数据集清单解析器：$resolver"
    return 1
  fi

  manifest="$(
    PYTHONPATH="$ROBOMIMIC_REPO_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      ROBOMIMIC_DATASET_ENDPOINT="$endpoint" \
      python3 "$resolver" "$@"
  )" || return 1

  local task dataset_type hdf5_type url relative_path dry_run
  local destination partial
  while IFS=$'\t' read -r task dataset_type hdf5_type url relative_path dry_run; do
    [[ -z "$url" ]] && continue
    destination="$ROBOMIMIC_REPO_DIR/datasets/$relative_path"

    if [[ "$dry_run" == 1 ]]; then
      print "[DRY RUN] $task/$dataset_type/$hdf5_type"
      print "  URL：$url"
      print "  宿主机：$destination"
      print "  容器：/opt/robomimic/datasets/$relative_path"
      continue
    fi

    if [[ -s "$destination" ]]; then
      print "数据集已存在，跳过：$destination"
      continue
    fi

    if ! mkdir -p "${destination:h}"; then
      print -u2 "无法创建数据集目录：${destination:h}"
      return 1
    fi

    partial="${destination}.part"
    print "正在下载：$task/$dataset_type/$hdf5_type"
    print "  $url"
    if ! curl \
      --fail \
      --show-error \
      --location \
      --continue-at - \
      --retry 5 \
      --retry-delay 2 \
      --retry-all-errors \
      --output "$partial" \
      "$url"; then
      print -u2 "下载失败，保留断点文件：$partial"
      return 1
    fi

    if ! mv -- "$partial" "$destination"; then
      print -u2 "下载完成但无法写入最终文件：$destination"
      return 1
    fi
    print "下载完成：$destination"
  done <<< "$manifest"
}

rmhelp() {
  print 'robomimic Docker 快捷命令：'
  print '  rmrun              启动一个交互式 robomimic 容器'
  print '  rmcam              使用 /dev/video0 启动带摄像头的容器'
  print '  rmcam /dev/video2  使用指定摄像头设备启动容器'
  print '  rmshell            从新终端进入当前运行中的容器'
  print '  rmps               查看正在运行的 robomimic 容器'
  print '  rmdataset          下载默认 Lift PH low-dim 数据集到宿主机'
  print '  rmdataset --tasks lift can --dataset_types ph --hdf5_types low_dim'
  print '                     使用原 download_datasets.py 参数选择数据集'
  print '  rmdataset --tasks sim --dataset_types ph --hdf5_types low_dim --dry_run'
  print '                     仅展示下载清单，不传输文件'
  print '  rmhelp             显示本帮助'
}

# Show the available shortcuts immediately after this file is sourced.
rmhelp
