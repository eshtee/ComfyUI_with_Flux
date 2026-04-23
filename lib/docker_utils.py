"""
Docker build and management utilities.
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from .common import Logger, CommandRunner, EnvironmentValidator, format_duration


class DockerBuilder:
    """Simplified Docker builder focused on core functionality."""
    
    def __init__(self, logger: Optional = None):
        self.logger = logger or Logger.get_logger("DockerBuilder")
        self.runner = CommandRunner(self.logger)
        self.validator = EnvironmentValidator(self.logger)
        self.start_time = time.time()
        
        # Supported configurations
        self.supported_platforms = ["linux/amd64", "linux/arm64"]
        self.supported_torch_variants = ["cpu", "cu121"]
    
    def validate_environment(self) -> bool:
        """Validate Docker environment."""
        self.logger.info("Validating Docker environment...")
        
        status = self.validator.check_docker_available()
        
        if not status["docker_installed"]:
            self.logger.error("Docker not found or not accessible")
            return False
        
        if not status["docker_running"]:
            self.logger.error("Docker daemon is not running")
            return False
        
        self.logger.info(f"Docker version: {status['version']}")
        
        if status["buildx_available"]:
            self.logger.info("Docker Buildx available for multi-platform builds")
        else:
            self.logger.warning("Docker Buildx not available - multi-platform builds disabled")
        
        return True
    
    def build_image(
        self,
        image_name: str,
        dockerfile: str = "Dockerfile",
        build_context: str = ".",
        platforms: Optional[List[str]] = None,
        build_args: Optional[Dict[str, str]] = None,
        no_cache: bool = False,
        push: bool = False
    ) -> bool:
        """Build Docker image with specified configuration."""
        
        if not self.validate_environment():
            return False
        
        self.logger.info(f"Building Docker image: {image_name}")
        
        # Build command
        cmd = ["docker"]
        
        # Use buildx for multi-platform builds
        is_multi_platform = platforms and len(platforms) > 1
        
        if is_multi_platform:
            cmd.extend(["buildx", "build"])
            cmd.extend(["--platform", ",".join(platforms)])
            # Multi-platform builds require --push, cannot use --load
            if not push:
                self.logger.warning("Multi-platform builds require --push flag. Building for single platform instead.")
                cmd = ["docker", "buildx", "build"]
                cmd.extend(["--platform", platforms[0]])  # Use first platform only
        else:
            # Single platform build
            if platforms and len(platforms) == 1:
                cmd.extend(["buildx", "build"])
                cmd.extend(["--platform", platforms[0]])
            else:
                cmd.append("build")
        
        # Add build arguments
        if build_args:
            for key, value in build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])
        
        # Add options
        if no_cache:
            cmd.append("--no-cache")
        
        # Handle push vs load
        if push:
            cmd.append("--push")
        elif not is_multi_platform or not push:
            cmd.append("--load")
        
        # Add progress and output options for better visibility
        cmd.append("--progress=plain")
        # Add image name and context
        cmd.extend(["-t", image_name])
        cmd.extend(["-f", dockerfile])
        cmd.append(build_context)
        
        # Execute build
        try:
            self.logger.info(f"Executing: {' '.join(cmd)}")
            self.logger.info("Starting Docker build with real-time progress...")
            # Use streaming for real-time Docker build output
            result = self.runner.run_streaming(cmd, timeout=3600)  # 1 hour timeout
            
            duration = time.time() - self.start_time
            self.logger.info(f"✅ Build completed in {format_duration(duration)}")
            
            if not push:
                self._show_usage_instructions(image_name)
            
            return True
            
        except Exception as e:
            duration = time.time() - self.start_time
            self.logger.error(f"❌ Build failed after {format_duration(duration)}: {e}")
            return False
    
    def push_image(self, image_name: str) -> bool:
        """Push image to registry."""
        self.logger.info(f"Pushing image: {image_name}")
        
        try:
            result = self.runner.run(["docker", "push", image_name])
            self.logger.info(f"✅ Successfully pushed: {image_name}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to push {image_name}: {e}")
            return False
    
    def tag_image(self, source: str, target: str) -> bool:
        """Tag an image."""
        try:
            result = self.runner.run(["docker", "tag", source, target])
            self.logger.debug(f"Tagged {source} as {target}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to tag {source} as {target}: {e}")
            return False
    
    def list_images(self, pattern: str = None) -> List[str]:
        """List Docker images matching pattern."""
        cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
        if pattern:
            cmd.append(pattern)
        
        try:
            result = self.runner.run(cmd)
            images = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return [img for img in images if img and img != '<none>:<none>']
        except Exception as e:
            self.logger.error(f"Failed to list images: {e}")
            return []
    
    def get_build_context_size(self, context_path: str = ".") -> str:
        """Get build context size."""
        try:
            context = Path(context_path)
            if not context.exists():
                return "Unknown"
            
            # Use docker build --dry-run to get context size (if available)
            # Fallback to simple directory size calculation
            total_size = 0
            for item in context.rglob('*'):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                    except (PermissionError, OSError):
                        pass
            
            # Convert to human readable
            for unit in ['B', 'KB', 'MB', 'GB']:
                if total_size < 1024.0:
                    return f"{total_size:.1f} {unit}"
                total_size /= 1024.0
            return f"{total_size:.1f} TB"
            
        except Exception:
            return "Unknown"
    
    def clean_build_cache(self) -> bool:
        """Clean Docker build cache."""
        self.logger.info("Cleaning Docker build cache...")
        
        try:
            result = self.runner.run(["docker", "builder", "prune", "-f"])
            self.logger.info("✅ Build cache cleaned")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clean build cache: {e}")
            return False
    
    def _show_usage_instructions(self, image_name: str) -> None:
        """Show usage instructions after successful build."""
        self.logger.info("\n" + "="*60)
        self.logger.info("🎉 BUILD SUCCESSFUL!")
        self.logger.info("="*60)
        self.logger.info(f"Image: {image_name}")
        self.logger.info("")
        self.logger.info("Usage:")
        self.logger.info(f"  docker run -p 8188:8188 -p 8888:8888 -p 7860:7860 {image_name}")
        self.logger.info("")
        self.logger.info("Services will be available at:")
        self.logger.info("  • ComfyUI:      http://localhost:8188")
        self.logger.info("  • JupyterLab:   http://localhost:8888")
        self.logger.info("  • Flux Train:   http://localhost:7860")
        self.logger.info("="*60)


class DockerImageManager:
    """Manage Docker image operations like tagging and pushing."""
    
    def __init__(self, logger: Optional = None):
        self.logger = logger or Logger.get_logger("DockerImageManager")
        self.runner = CommandRunner(self.logger)
    
    def generate_tags(
        self,
        base_name: str,
        version: str,
        torch_variant: str = "cpu",
        additional_tags: Optional[List[str]] = None
    ) -> List[str]:
        """Generate list of tags for an image."""
        tags = [f"{base_name}:{version}"]
        
        # Add variant-specific tag
        if torch_variant != "cpu":
            tags.append(f"{base_name}:{version}-{torch_variant}")
        
        # Add latest tag for main versions
        if version in ["latest", "main"]:
            tags.append(f"{base_name}:latest")
        
        # Add additional tags
        if additional_tags:
            for tag in additional_tags:
                if tag not in tags:
                    tags.append(f"{base_name}:{tag}")
        
        return tags
    
    def tag_and_push_all(self, source_image: str, target_tags: List[str]) -> bool:
        """Tag source image with all target tags and push them."""
        builder = DockerBuilder(self.logger)
        
        success = True
        for tag in target_tags:
            if not builder.tag_image(source_image, tag):
                success = False
                continue
            
            if not builder.push_image(tag):
                success = False
        
        return success 