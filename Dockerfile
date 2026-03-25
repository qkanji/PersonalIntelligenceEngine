# Use a slim CUDA 12.6 base image for RunPod compatibility.
FROM nvidia/cuda:12.6.2-base-ubuntu22.04

# Set non-interactive timezone and environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=180
ENV TMPDIR=/var/tmp/pip-tmp

# Limit PyTorch and vLLM binaries to RTX 4090 architecture (compute capability 8.9) to drastically reduce size.
ENV TORCH_CUDA_ARCH_LIST="8.9"

# Install system dependencies, including python3.10 and explicitly cuda-nvcc-12-6 for vLLM JIT
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3-pip python3.10-dev python3.10-venv \
    curl git wget build-essential \
    cuda-nvcc-12-6 \
    && rm -rf /var/lib/apt/lists/*

# Set python3 as default
RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python3
RUN mkdir -p /var/tmp/pip-tmp

# Upgrade pip only (avoid replacing Debian-managed setuptools/wheel).
RUN python -m pip install --no-cache-dir --upgrade pip

# Install PyTorch compiled for CUDA 12.6
RUN python -m pip install --no-cache-dir --upgrade --prefer-binary \
    torch==2.10.0 \
    torchvision \
    --index-url https://download.pytorch.org/whl/cu126

# Keep torch pinned while installing the rest of the worker stack.
RUN printf "torch>=2.10,<2.11\n" > /tmp/constraints.txt

# Install core inference dependencies first (largest, most failure-prone layer).
RUN python -m pip install --no-cache-dir --prefer-binary \
    -c /tmp/constraints.txt \
    vllm==0.17.1 \
    "transformers>=4.40.0" \
    qwen-vl-utils \
    && rm -rf /tmp/pip-* /var/tmp/pip-tmp/*

# Install remaining worker dependencies in a separate layer.
RUN python -m pip install --no-cache-dir --prefer-binary \
    -c /tmp/constraints.txt \
    sentence-transformers \
    pinecone \
    google-cloud-storage \
    gcloud-aio-storage \
    aiohttp \
    hf_transfer \
    && rm -rf /tmp/pip-* /var/tmp/pip-tmp/*

# Explicitly use hf_transfer for blazing fast huggingface downloads
ENV HF_HUB_ENABLE_HF_TRANSFER=1

# Set up working directory
WORKDIR /app

# Ensure curl / bash is ready for orchestrator's fetch_cmd
CMD ["tail", "-f", "/dev/null"]