# Base image with Python 3.9 and Linux
FROM nvidia/cuda:11.8.0-base-ubuntu20.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    PATH=/opt/conda/bin:$PATH \
    MUJOCO_GL=osmesa

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    curl \
    cmake \
    ca-certificates \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libosmesa6-dev \
    libglfw3-dev \
    patchelf && \
    rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh && \
    conda clean -afy

# Use domestic Conda mirrors and avoid the Anaconda default-channel ToS prompt
RUN /opt/conda/bin/conda config --system --remove-key default_channels || true && \
    /opt/conda/bin/conda config --system --add default_channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main && \
    /opt/conda/bin/conda config --system --add default_channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r && \
    /opt/conda/bin/conda config --system --set channel_alias https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud && \
    /opt/conda/bin/conda config --system --set show_channel_urls true

# Create and activate robomimic conda environment with Python 3.9
RUN /opt/conda/bin/conda create -n robomimic_venv python=3.9 -y

# Use domestic Python package mirrors by default
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PYTORCH_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cu118
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PYTORCH_WHEEL_URL=${PYTORCH_WHEEL_URL}

# PyTorch 2.4.1 is built with NumPy 2 support; keep the CUDA and torchvision
# versions aligned and do not silently fall back to a CPU-only wheel.
RUN /opt/conda/bin/conda run -n robomimic_venv python -m pip install --no-cache-dir \
    --find-links "${PYTORCH_WHEEL_URL}" \
    numpy==2.0.1 \
    torch==2.4.1+cu118 \
    torchvision==0.19.1+cu118

# Install the current robomimic source tree
WORKDIR /opt/robomimic
COPY . .
RUN /opt/conda/bin/conda run -n robomimic_venv pip install -e .

# Install the robosuite version recommended for the current datasets
# MuJoCo 3.3.7 is the latest release with a CPython 3.9 Linux wheel
RUN /opt/conda/bin/conda run -n robomimic_venv pip install --only-binary=mujoco \
    mujoco==3.3.7 robosuite==1.5.1

# Optional: Install robomimic documentation dependencies
RUN /opt/conda/bin/conda run -n robomimic_venv pip install -r requirements-docs.txt

# Set the working directory
WORKDIR /workspace

# Install Zsh through a domestic Ubuntu mirror near the end to preserve existing build cache
ARG UBUNTU_APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu
RUN sed -i \
        -e "s|http://archive.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" \
        -e "s|http://security.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" \
        /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends zsh && \
    rm -rf /var/lib/apt/lists/*

COPY docker/robomimic-entrypoint.sh /usr/local/bin/robomimic-entrypoint
COPY docker/robomimic.zshrc /root/.zshrc
RUN chmod 0755 /usr/local/bin/robomimic-entrypoint && \
    mkdir -p /tmp/oh-my-zsh-cache

ENV SHELL=/usr/bin/zsh \
    ZSH=/root/.oh-my-zsh \
    ZSH_CACHE_DIR=/tmp/oh-my-zsh-cache

ENTRYPOINT ["/usr/local/bin/robomimic-entrypoint"]
CMD ["/usr/bin/zsh", "-l"]
