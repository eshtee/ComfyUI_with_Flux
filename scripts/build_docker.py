#!/usr/bin/env python3
"""
Simplified ComfyUI Docker Build Script
=====================================

A streamlined Docker build script focusing on core functionality with
intelligent dependency checking and clear user experience.

Usage:
    python scripts/build_docker_new.py --help
    python scripts/build_docker_new.py --username myuser --tag latest
    python scripts/build_docker_new.py --runpod --username myuser --push
"""

import argparse
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.common import Logger, get_timestamp, get_git_commit
from lib.dependency_manager import DependencyManager
from lib.docker_utils import DockerBuilder, DockerImageManager


class SimplifiedBuildScript:
    """Simplified build script with focused functionality."""
    
    def __init__(self):
        self.logger = Logger.get_logger("BuildScript", level="INFO")
        self.start_time = get_timestamp()
        
        # Build configurations
        self.presets = {
            "basic": {
                "torch_variant": "cu121",
                "platforms": ["linux/amd64"],
                "description": "Basic CUDA build for general use"
            },
            "cpu": {
                "torch_variant": "cpu",
                "platforms": ["linux/arm64"],
                "description": "CPU-only build for local development"
            },
            "runpod": {
                "torch_variant": "cu121",
                "platforms": ["linux/amd64"],
                "description": "RunPod-optimized build"
            }
        }
    
    def check_dependencies(self) -> bool:
        """Check project dependencies."""
        self.logger.info("🔍 Checking project dependencies...")
        
        dep_manager = DependencyManager()
        
        # Load dependencies first
        if not dep_manager.load_dependencies("minimal"):
            self.logger.error("❌ Failed to load dependencies")
            return False
        
        result = dep_manager.check_all_dependencies()
        
        if not result["success"]:
            self.logger.error("❌ Failed to check dependencies")
            return False
        
        # Validate dependency structure
        errors = dep_manager.validate_dependency_structure()
        if errors:
            self.logger.warning(f"⚠️  Found {len(errors)} dependency structure issues:")
            for error in errors[:3]:  # Show first 3 errors
                self.logger.warning(f"  • {error}")
            if len(errors) > 3:
                self.logger.warning(f"  ... and {len(errors) - 3} more")
        
        return True
    
    def build_image(self, args) -> bool:
        """Build Docker image with specified configuration."""
        
        # Check dependencies first
        if not self.check_dependencies():
            return False
        
        # Determine build configuration
        preset = "runpod" if args.runpod else ("cpu" if args.torch_variant == "cpu" else "basic")
        config = self.presets[preset]
        
        self.logger.info(f"🐳 Building with '{preset}' preset: {config['description']}")
        
        # Generate image name
        image_name = self._generate_image_name(args)
        
        # Build arguments
        build_args = {
            "TORCH_VARIANT": args.torch_variant or config["torch_variant"],
            "PYTHON_VERSION": args.python_version,
            "BUILD_DATE": self.start_time,
        }
        
        # Add git commit if available
        git_commit = get_git_commit()
        if git_commit:
            build_args["GIT_COMMIT"] = git_commit
        
        # Initialize builder
        builder = DockerBuilder(self.logger)
        
        # Build image
        success = builder.build_image(
            image_name=image_name,
            dockerfile=args.dockerfile,
            build_context=args.build_context,
            platforms=config["platforms"],
            build_args=build_args,
            no_cache=args.no_cache,
            push=args.push
        )
        
        if success and args.additional_tags:
            # Tag with additional tags
            manager = DockerImageManager(self.logger)
            additional_tags = [f"{args.username}/{args.image_name}:{tag}" for tag in args.additional_tags]
            manager.tag_and_push_all(image_name, additional_tags)
        
        return success
    
    def _generate_image_name(self, args) -> str:
        """Generate image name from arguments."""
        base_name = f"{args.username}/{args.image_name}"
        
        if args.runpod:
            return f"{base_name}:runpod"
        
        tag = args.tag
        if args.torch_variant == "cpu" and not tag.endswith("-cpu"):
            tag = f"{tag}-cpu"
        
        return f"{base_name}:{tag}"
    
    def list_presets(self):
        """List available build presets."""
        self.logger.info("📋 Available build presets:")
        for name, config in self.presets.items():
            self.logger.info(f"  • {name:8} - {config['description']}")
            self.logger.info(f"    {'':10} Torch: {config['torch_variant']}, Platforms: {', '.join(config['platforms'])}")
    
    def clean_cache(self) -> bool:
        """Clean Docker build cache."""
        builder = DockerBuilder(self.logger)
        return builder.clean_build_cache()


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Simplified ComfyUI Docker Build Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic CUDA build
  python scripts/build_docker_new.py --username myuser --tag latest
  
  # CPU-only build
  python scripts/build_docker_new.py --username myuser --tag latest --torch-variant cpu
  
  # RunPod-optimized build with push
  python scripts/build_docker_new.py --runpod --username myuser --push
  
  # Check dependencies only
  python scripts/build_docker_new.py --check-dependencies
        """
    )
    
    # Main arguments
    parser.add_argument("--username", "-u", help="Docker Hub username")
    parser.add_argument("--tag", "-t", default="latest", help="Image tag (default: latest)")
    parser.add_argument("--image-name", default="comfyui-flux", help="Image name (default: comfyui-flux)")
    
    # Build options
    parser.add_argument("--torch-variant", choices=["cpu", "cu121"], help="PyTorch variant")
    parser.add_argument("--python-version", default="3.11", help="Python version (default: 3.11)")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Dockerfile path")
    parser.add_argument("--build-context", default=".", help="Build context path")
    
    # Presets
    parser.add_argument("--runpod", action="store_true", help="Use RunPod-optimized settings")
    
    # Actions
    parser.add_argument("--push", action="store_true", help="Push image to registry")
    parser.add_argument("--no-cache", action="store_true", help="Build without cache")
    parser.add_argument("--additional-tags", nargs="+", help="Additional tags to apply")
    
    # Utility commands
    parser.add_argument("--check-dependencies", action="store_true", help="Check dependencies only")
    parser.add_argument("--list-presets", action="store_true", help="List available build presets")
    parser.add_argument("--clean-cache", action="store_true", help="Clean Docker build cache")
    
    # Logging
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet logging")
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize build script
    script = SimplifiedBuildScript()
    
    # Set logging level
    if args.verbose:
        script.logger.setLevel("DEBUG")
    elif args.quiet:
        script.logger.setLevel("WARNING")
    
    # Handle utility commands
    if args.check_dependencies:
        success = script.check_dependencies()
        sys.exit(0 if success else 1)
    
    if args.list_presets:
        script.list_presets()
        sys.exit(0)
    
    if args.clean_cache:
        success = script.clean_cache()
        sys.exit(0 if success else 1)
    
    # Validate required arguments for build
    if not args.username:
        script.logger.error("❌ Username is required for build operations")
        sys.exit(1)
    
    # Build image
    script.logger.info("🚀 Starting ComfyUI Docker build...")
    success = script.build_image(args)
    
    if success:
        script.logger.info("✅ Build completed successfully!")
        sys.exit(0)
    else:
        script.logger.error("❌ Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 