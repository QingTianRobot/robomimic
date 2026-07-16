# robomimic simulation workflow shortcuts for container shells.

typeset -g RS_ROOT="${RS_ROOT:-/opt/robomimic}"
typeset -g RS_DEFAULT_DATASET="${RS_DEFAULT_DATASET:-$RS_ROOT/datasets/lift/ph/low_dim_v15.hdf5}"
typeset -g RS_DEFAULT_CONFIG="${RS_DEFAULT_CONFIG:-$RS_ROOT/robomimic/exps/templates/bc.json}"
typeset -g RS_OUTPUT_ROOT="${RS_OUTPUT_ROOT:-$RS_ROOT/outputs}"
typeset -g RS_TRAINING_ROOT="${RS_TRAINING_ROOT:-$RS_OUTPUT_ROOT/training}"
typeset -g RS_VIDEO_ROOT="${RS_VIDEO_ROOT:-$RS_OUTPUT_ROOT/videos}"

_rs_require_file() {
  if [[ ! -s "$1" ]]; then
    print -u2 "文件不存在或为空：$1"
    return 1
  fi
}

_rs_prepare_outputs() {
  (umask 0000; mkdir -p "$RS_TRAINING_ROOT" "$RS_VIDEO_ROOT") || return 1
  chmod a+rwx \
    "$RS_OUTPUT_ROOT" \
    "$RS_TRAINING_ROOT" \
    "$RS_VIDEO_ROOT" 2>/dev/null || true
}

_rs_take_optional_path() {
  REPLY=""
  if (( $# > 0 )) && [[ "$1" != -* ]]; then
    REPLY="$1"
    return 0
  fi
  return 1
}

_rs_require_gui() {
  if [[ -z "${DISPLAY:-}" ]]; then
    print -u2 'DISPLAY 未设置；请从宿主机使用 rmrun 或 rmcam 启动容器。'
    return 1
  fi
  if [[ -z "${XAUTHORITY:-}" || ! -f "$XAUTHORITY" || ! -r "$XAUTHORITY" || ! -s "$XAUTHORITY" ]]; then
    print -u2 'XAUTHORITY 授权文件不存在、不可读或为空；请在宿主机导出有效的 XAUTHORITY 后重新运行 rmrun 或 rmcam。'
    return 1
  fi
  local display_number="${DISPLAY#:}"
  display_number="${display_number%%.*}"
  if [[ ! -S "/tmp/.X11-unix/X${display_number}" ]]; then
    print -u2 "找不到 X11 socket：/tmp/.X11-unix/X${display_number}"
    return 1
  fi
}

rslatest() {
  local latest
  latest="$(
    find "$RS_OUTPUT_ROOT" -type f -name '*.pth' -printf '%T@\t%p\n' 2>/dev/null \
      | sort -nr \
      | head -n 1 \
      | cut -f 2-
  )"
  if [[ -z "$latest" ]]; then
    print -u2 "没有找到 checkpoint：$RS_OUTPUT_ROOT"
    print -u2 '请先运行 rstrain 或 rstrain-full。'
    return 1
  fi
  print -r -- "$latest"
}

rsstatus() {
  _rs_prepare_outputs || return 1
  python -c '
import numpy as np
import torch
import torchvision

print("python/torch runtime")
print("numpy", np.__version__)
print("torch", torch.__version__)
print("torchvision", torchvision.__version__)
print("cuda", torch.version.cuda)
print("gpu", torch.cuda.get_device_name(0))
print("capability", torch.cuda.get_device_capability(0))
print("arches", torch.cuda.get_arch_list())
print("cuda_result", (torch.ones(1, device="cuda") + 1).cpu().tolist())
' || return 1
  if [[ -s "$RS_DEFAULT_DATASET" ]]; then
    print "dataset: $RS_DEFAULT_DATASET ($(du -h "$RS_DEFAULT_DATASET" | cut -f1))"
  else
    print -u2 "dataset missing: $RS_DEFAULT_DATASET"
  fi
  print "outputs: $RS_OUTPUT_ROOT"
  local checkpoint
  checkpoint="$(rslatest 2>/dev/null)" \
    && print "latest: $checkpoint" \
    || print 'latest: none'
}

rsplay() {
  local dataset="$RS_DEFAULT_DATASET"
  if _rs_take_optional_path "$@"; then
    dataset="$REPLY"
    shift
  fi
  _rs_require_file "$dataset" || return 1
  _rs_prepare_outputs || return 1
  (
    umask 0000
    MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/playback_dataset.py" \
      --dataset "$dataset" \
      --n 1 \
      --render_image_names agentview \
      --video_path "$RS_VIDEO_ROOT/dataset-playback.mp4" \
      "$@"
  )
}

rsplay-gui() {
  local dataset="$RS_DEFAULT_DATASET"
  if _rs_take_optional_path "$@"; then
    dataset="$REPLY"
    shift
  fi
  _rs_require_file "$dataset" || return 1
  _rs_require_gui || return 1
  (
    umask 0000
    MUJOCO_GL=glfw python "$RS_ROOT/robomimic/scripts/playback_dataset.py" \
      --dataset "$dataset" \
      --n 1 \
      --render \
      --render_image_names agentview \
      "$@"
  )
}

rstrain() {
  _rs_require_file "$RS_DEFAULT_CONFIG" || return 1
  _rs_require_file "$RS_DEFAULT_DATASET" || return 1
  _rs_prepare_outputs || return 1
  local run_name="lift-bc-smoke-$(date +%Y%m%d-%H%M%S-%N)"
  (
    umask 0000
    MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/train.py" \
      --config "$RS_DEFAULT_CONFIG" \
      --dataset "$RS_DEFAULT_DATASET" \
      --name "$run_name" \
      --output_dir "$RS_TRAINING_ROOT" \
      --debug \
      "$@"
  )
}

rstrain-full() {
  _rs_require_file "$RS_DEFAULT_CONFIG" || return 1
  _rs_require_file "$RS_DEFAULT_DATASET" || return 1
  _rs_prepare_outputs || return 1
  print -u2 '即将启动完整训练；BC 模板默认运行 2000 epochs。'
  (
    umask 0000
    MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/train.py" \
      --config "$RS_DEFAULT_CONFIG" \
      --dataset "$RS_DEFAULT_DATASET" \
      --name lift-bc-full \
      --output_dir "$RS_TRAINING_ROOT" \
      "$@"
  )
}

rseval() {
  local checkpoint
  if _rs_take_optional_path "$@"; then
    checkpoint="$REPLY"
    shift
  else
    checkpoint="$(rslatest)" || return 1
  fi
  _rs_require_file "$checkpoint" || return 1
  _rs_prepare_outputs || return 1
  local stem="${checkpoint:t:r}"
  (
    umask 0000
    MUJOCO_GL=egl python "$RS_ROOT/robomimic/scripts/run_trained_agent.py" \
      --agent "$checkpoint" \
      --n_rollouts 5 \
      --seed 0 \
      --camera_names agentview \
      --video_path "$RS_VIDEO_ROOT/eval-${stem}.mp4" \
      "$@"
  )
}

rseval-gui() {
  local checkpoint
  if _rs_take_optional_path "$@"; then
    checkpoint="$REPLY"
    shift
  else
    checkpoint="$(rslatest)" || return 1
  fi
  _rs_require_file "$checkpoint" || return 1
  _rs_require_gui || return 1
  (
    umask 0000
    MUJOCO_GL=glfw python "$RS_ROOT/robomimic/scripts/run_trained_agent.py" \
      --agent "$checkpoint" \
      --n_rollouts 1 \
      --seed 0 \
      --camera_names agentview \
      --render \
      "$@"
  )
}

rshelp() {
  print 'robomimic simulation 容器命令：'
  print '  rsstatus                    检查 CUDA、数据集、输出与 checkpoint'
  print '  rsplay [dataset]            回放数据集并生成 outputs/videos/dataset-playback.mp4'
  print '  rsplay-gui [dataset]        使用 X11 窗口回放数据集'
  print '  rstrain [train.py 参数]     运行 2 epoch GPU smoke test'
  print '  rstrain-full [参数]         启动完整 BC 训练'
  print '  rslatest                    打印 outputs 下最新 checkpoint'
  print '  rseval [checkpoint] [参数]  仿真 rollout 并保存视频'
  print '  rseval-gui [checkpoint]     实时窗口运行策略'
  print '  rshelp                      显示本帮助'
  print
  print "默认数据集：$RS_DEFAULT_DATASET"
  print "训练输出：$RS_TRAINING_ROOT"
  print "视频输出：$RS_VIDEO_ROOT"
  print
  print '推荐的安全验证流程（可逐行复制）：'
  print '  rsstatus'
  print '  rsplay'
  print '  rstrain'
  print '  rslatest'
  print '  rseval --n_rollouts 1 --horizon 10'
  print '完整训练需显式运行：rstrain-full'
}
