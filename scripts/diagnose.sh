#!/bin/bash
# Diagnostic Script for ComfyUI Container Issues
# Run this script to diagnose common deployment problems

echo "=== ComfyUI Container Diagnostics ==="
echo "Timestamp: $(date)"
echo ""

echo "=== System Information ==="
echo "Architecture: $(uname -m)"
echo "Kernel: $(uname -r)"
echo "OS: $(uname -s)"
echo "Hostname: $(hostname)"
echo ""

echo "=== Container Environment ==="
echo "User: $(whoami)"
echo "UID: $(id -u)"
echo "GID: $(id -g)"
echo "Working Directory: $(pwd)"
echo "PATH: $PATH"
echo ""

echo "=== File System Checks ==="
echo "Workspace exists: $([ -d /workspace ] && echo "✅ YES" || echo "❌ NO")"
echo "Startup script exists: $([ -f /opt/app/start-on-workspace.sh ] && echo "✅ YES" || echo "❌ NO")"
echo "Startup script executable: $([ -x /opt/app/start-on-workspace.sh ] && echo "✅ YES" || echo "❌ NO")"
echo ""

if [ -f /opt/app/start-on-workspace.sh ]; then
    echo "=== Startup Script Details ==="
    echo "File type: $(file /opt/app/start-on-workspace.sh)"
    echo "Permissions: $(ls -la /opt/app/start-on-workspace.sh)"
    echo "First line: $(head -n1 /opt/app/start-on-workspace.sh)"
    echo ""
fi

echo "=== Python Environment ==="
echo "Python version: $(python3 --version 2>/dev/null || echo "Not found")"
echo "Python path: $(which python3 2>/dev/null || echo "Not found")"
echo "Pip version: $(pip --version 2>/dev/null || echo "Not found")"
echo ""

echo "=== PyTorch Information ==="
if python3 -c "import torch" 2>/dev/null; then
    echo "PyTorch version: $(python3 -c "import torch; print(torch.__version__)" 2>/dev/null)"
    echo "CUDA available: $(python3 -c "import torch; print(torch.cuda.is_available())" 2>/dev/null)"
    echo "CUDA version: $(python3 -c "import torch; print(torch.version.cuda)" 2>/dev/null)"
    echo "GPU count: $(python3 -c "import torch; print(torch.cuda.device_count())" 2>/dev/null)"
else
    echo "❌ PyTorch not available"
fi
echo ""

echo "=== Network and Ports ==="
echo "Listening on 8188: $(netstat -ln 2>/dev/null | grep :8188 && echo "✅ YES" || echo "❌ NO")"
echo "Listening on 8888: $(netstat -ln 2>/dev/null | grep :8888 && echo "✅ YES" || echo "❌ NO")"
echo "Listening on 7860: $(netstat -ln 2>/dev/null | grep :7860 && echo "✅ YES" || echo "❌ NO")"
echo ""

echo "=== Environment Variables ==="
echo "WORKSPACE: ${WORKSPACE:-<not set>}"
echo "COMFYUI_PORT: ${COMFYUI_PORT:-<not set>}"
echo "JUPYTER_PORT: ${JUPYTER_PORT:-<not set>}"
echo "FLUX_TRAIN_UI_PORT: ${FLUX_TRAIN_UI_PORT:-<not set>}"
echo "HUGGINGFACE_TOKEN: $([ -n "$HUGGINGFACE_TOKEN" ] && echo "Set (${#HUGGINGFACE_TOKEN} chars)" || echo "<not set>")"
echo "CIVITAI_TOKEN: $([ -n "$CIVITAI_TOKEN" ] && echo "Set (${#CIVITAI_TOKEN} chars)" || echo "<not set>")"
echo ""

echo "=== Log Files ==="
if [ -f /workspace/startup.log ]; then
    echo "Startup log exists: ✅ YES"
    echo "Last 10 lines of startup log:"
    tail -n 10 /workspace/startup.log
else
    echo "Startup log exists: ❌ NO"
fi
echo ""

echo "=== Recommendations ==="
echo "1. If you see 'Exec format error', rebuild with: --platform linux/amd64"
echo "2. If ports aren't accessible, check firewall and port mapping"
echo "3. If PyTorch is missing, check the TORCH_VARIANT build argument"
echo "4. For authentication issues, verify token formats and permissions"
echo ""

echo "=== Diagnostics Complete ===" 