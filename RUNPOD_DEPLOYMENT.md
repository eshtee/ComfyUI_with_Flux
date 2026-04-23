# RunPod Deployment Guide

This guide helps you deploy ComfyUI with Flux on RunPod and avoid common issues like "Exec format error".

## Quick Fix for "Exec format error"

The most common cause is architecture mismatch. Follow these steps:

### 1. Build for Correct Architecture

**If building locally (e.g., on Apple Silicon):**
```bash
# Use the provided build script
./build_script.sh

# Or manually specify platform
docker buildx build --platform linux/amd64 \
    --build-arg TORCH_VARIANT=cu121 \
    --tag your-registry/comfyui-flux:latest \
    .
```

**Important:** Always use `--platform linux/amd64` when building for RunPod!

### 2. Push to Docker Registry

```bash
# Tag and push to your registry
docker tag comfyui-flux:latest your-registry/comfyui-flux:latest
docker push your-registry/comfyui-flux:latest
```

### 3. RunPod Template Configuration

```yaml
# RunPod Template Settings
containerDiskInGb: 50
dockerArgs: ""
env:
  - name: HUGGINGFACE_TOKEN
    value: "hf_your_token_here"
  - name: CIVITAI_TOKEN  
    value: "your_civitai_token_here"
  - name: TORCH_VARIANT
    value: "cu121"
imageName: "your-registry/comfyui-flux:latest"
ports: "8188/http,8888/http,7860/http"
volumeInGb: 100
volumeMountPath: "/workspace"
```

## Troubleshooting

### If you still get "Exec format error":

1. **Run diagnostics inside the container:**
   ```bash
   # In RunPod terminal
   /opt/app/diagnose.sh
   ```

2. **Check the container architecture:**
   ```bash
   uname -m  # Should show "x86_64" on RunPod
   ```

3. **Verify script format:**
   ```bash
   file /opt/app/start-on-workspace.sh
   ls -la /opt/app/start-on-workspace.sh
   ```

### Alternative Startup Method

If the main script fails, try running components individually:

```bash
# Start with bash shell override
docker run -it --entrypoint /bin/bash your-image

# Then manually run:
cd /workspace
/opt/app/diagnose.sh
/opt/app/start-on-workspace.sh
```

## Port Access

- **ComfyUI**: Port 8188 - Web interface
- **JupyterLab**: Port 8888 - Notebook environment  
- **Flux Train UI**: Port 7860 - Model training interface

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HUGGINGFACE_TOKEN` | HF authentication token | "" |
| `CIVITAI_TOKEN` | CivitAI authentication token | "" |
| `TORCH_VARIANT` | PyTorch variant (cpu/cu121) | "cu121" |
| `ENABLE_CLEANUP` | Enable startup cleanup | "true" |
| `AGGRESSIVE_CLEANUP` | More thorough cleanup | "false" |

## Common Issues

### 1. "Exec format error"
- **Cause**: Architecture mismatch (ARM64 vs x86_64)
- **Solution**: Rebuild with `--platform linux/amd64`

### 2. PyTorch CUDA errors
- **Cause**: Wrong PyTorch variant for GPU
- **Solution**: Use `TORCH_VARIANT=cu121` for GPU pods

### 3. Port not accessible
- **Cause**: Service not started or firewall
- **Solution**: Check logs, verify port mapping

### 4. Authentication failures
- **Cause**: Invalid tokens
- **Solution**: Verify token format and permissions

## Support

If issues persist:
1. Run `/opt/app/diagnose.sh` and share output
2. Check `/workspace/startup.log` for detailed logs
3. Verify build platform matches RunPod architecture 