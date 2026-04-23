# syntax=docker/dockerfile:1

# ================================
# Stage 1: Builder
# ================================
FROM python:3.11-slim AS builder

# Build Arguments
ARG PYTHON_VERSION=3.11
ARG TORCH_VARIANT=cpu
ARG COMFYUI_VERSION=latest
ARG BUILD_DATE
ARG GIT_COMMIT

# Metadata
LABEL maintainer="ComfyUI Team" \
      version="2.0" \
      description="ComfyUI with Flux.1-dev - Simplified Architecture" \
      org.opencontainers.image.source="https://github.com/ValyrianTech/ComfyUI_with_Flux" \
      org.opencontainers.image.title="ComfyUI with Flux" \
      build.date="${BUILD_DATE}" \
      build.git-commit="${GIT_COMMIT}"

# Install system dependencies in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    wget \
    libgomp1 \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set up ComfyUI
WORKDIR /opt/app/ComfyUI
RUN if [ "$COMFYUI_VERSION" = "latest" ]; then \
        git clone https://github.com/comfyanonymous/ComfyUI.git . ; \
    else \
        git clone --branch $COMFYUI_VERSION https://github.com/comfyanonymous/ComfyUI.git . ; \
    fi

# Copy requirements files
COPY comfyui-without-flux/requirements*.txt ./

# Install Python dependencies based on variant
RUN python3 -m pip install --upgrade pip && \
    if [ "$TORCH_VARIANT" = "cu121" ]; then \
        echo "Installing CUDA variant..." && \
        python3 -m pip install --no-cache-dir --default-timeout=1000 \
            torch torchvision torchaudio \
            --index-url https://download.pytorch.org/whl/cu121 && \
        python3 -m pip install --no-cache-dir -r requirements-gpu.txt || true ; \
    else \
        echo "Installing CPU variant..." && \
        python3 -m pip install --no-cache-dir \
            torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 && \
        python3 -m pip install --no-cache-dir -r requirements-cpu.txt ; \
    fi && \
    python3 -m pip install --no-cache-dir -r requirements-base.txt

# Install optional dependencies with graceful fallback
RUN python3 -m pip install --no-cache-dir \
    git+https://github.com/jaretburkett/easy_dwpose.git || \
    echo "⚠️ easy_dwpose installation failed - pose detection may have limited functionality"

# ================================
# Stage 2: Production
# ================================
FROM python:3.11-slim AS production

ARG PYTHON_VERSION=3.11
ARG TORCH_VARIANT

# Environment variables
ENV HUGGINGFACE_TOKEN="" \
    CIVITAI_TOKEN="" \
    AUTO_LOGIN="true" \
    MODEL_CACHE_DIR="/workspace/models" \
    HF_HOME="/workspace/.cache/huggingface" \
    ENABLE_CLEANUP="true" \
    AGGRESSIVE_CLEANUP="false" \
    PYTHONPATH="/opt/app/lib:$PYTHONPATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libsndfile1 \
    ffmpeg \
    git \
    curl \
    file \
    bash \
    bash-completion \
    vim \
    nano \
    procps \
    htop \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /opt/app

# Copy application files from builder
COPY --from=builder /opt/app/ComfyUI /opt/app/ComfyUI
COPY --from=builder /usr/local/lib/python${PYTHON_VERSION}/site-packages /usr/local/lib/python${PYTHON_VERSION}/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy our modular library and scripts
COPY lib/ /opt/app/lib/
COPY scripts/start-on-workspace-new.py /opt/app/start-on-workspace.py
COPY scripts/redeploy_dependencies.py /opt/app/redeploy_dependencies.py
COPY scripts/fix_jupyter_terminal.py /opt/app/fix_jupyter_terminal.py
COPY dependencies.yaml /opt/app/dependencies.yaml
COPY scripts/diagnose.sh /opt/app/diagnose.sh

# Copy workflow templates
RUN mkdir -p /opt/app/workflows
COPY comfyui-without-flux/workflows/*.json /opt/app/workflows/

# Make scripts executable
RUN chmod +x /opt/app/start-on-workspace.py /opt/app/diagnose.sh /opt/app/fix_jupyter_terminal.py

# Expose ports
EXPOSE 8188 8888 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8188/ || exit 1

# Use our new simplified startup script
ENTRYPOINT ["/opt/app/start-on-workspace.py"]
