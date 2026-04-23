#!/usr/bin/env python3
"""
ComfyUI Project Cleanup Script
=============================

Comprehensive cleanup utility for removing test artifacts, old Docker images,
build cache, and other development artifacts.

Usage:
    python cleanup.py --help
    python cleanup.py --test-artifacts
    python cleanup.py --docker-images --confirm
    python cleanup.py --all --force
"""

import argparse
import subprocess
import sys
import os
import time
import glob
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class ProjectCleanup:
    """Comprehensive cleanup utility for ComfyUI project."""
    
    def __init__(self, force: bool = False, verbose: bool = False):
        self.force = force
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        self.cleanup_stats = {
            "files_removed": 0,
            "directories_removed": 0,
            "docker_images_removed": 0,
            "space_freed_mb": 0,
            "errors": []
        }
    
    def run_command(self, cmd: List[str], capture_output: bool = True) -> tuple:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=capture_output, text=True, check=False)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", str(e)
    
    def confirm_action(self, message: str) -> bool:
        """Confirm an action unless force mode is enabled."""
        if self.force:
            return True
        
        response = input(f"{message} (y/N): ").strip().lower()
        return response in ('y', 'yes')
    
    def get_file_size(self, path: str) -> int:
        """Get file size in bytes."""
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            elif os.path.isdir(path):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total_size += os.path.getsize(filepath)
                        except (OSError, FileNotFoundError):
                            continue
                return total_size
            return 0
        except (OSError, FileNotFoundError):
            return 0
    
    def cleanup_test_artifacts(self) -> bool:
        """Remove test artifacts and reports."""
        logger.info("Cleaning up test artifacts...")
        
        patterns = [
            "test-report-*.json",
            "build-info.json",
            "*.log",
            "*.tmp",
            "__pycache__",
            "*.pyc",
            ".pytest_cache",
            ".coverage",
            "htmlcov"
        ]
        
        removed_count = 0
        space_freed = 0
        
        for pattern in patterns:
            if '*' in pattern:
                # Handle glob patterns
                matches = glob.glob(pattern)
                for match in matches:
                    if self.verbose:
                        logger.debug(f"Found: {match}")
                    
                    size = self.get_file_size(match)
                    
                    try:
                        if os.path.isfile(match):
                            os.remove(match)
                            removed_count += 1
                            space_freed += size
                            logger.info(f"Removed file: {match}")
                        elif os.path.isdir(match):
                            shutil.rmtree(match)
                            removed_count += 1
                            space_freed += size
                            logger.info(f"Removed directory: {match}")
                    except Exception as e:
                        error_msg = f"Failed to remove {match}: {e}"
                        logger.error(error_msg)
                        self.cleanup_stats["errors"].append(error_msg)
            else:
                # Handle direct paths
                if os.path.exists(pattern):
                    size = self.get_file_size(pattern)
                    
                    try:
                        if os.path.isfile(pattern):
                            os.remove(pattern)
                            removed_count += 1
                            space_freed += size
                            logger.info(f"Removed file: {pattern}")
                        elif os.path.isdir(pattern):
                            shutil.rmtree(pattern)
                            removed_count += 1
                            space_freed += size
                            logger.info(f"Removed directory: {pattern}")
                    except Exception as e:
                        error_msg = f"Failed to remove {pattern}: {e}"
                        logger.error(error_msg)
                        self.cleanup_stats["errors"].append(error_msg)
        
        self.cleanup_stats["files_removed"] += removed_count
        self.cleanup_stats["space_freed_mb"] += space_freed // (1024 * 1024)
        
        logger.info(f"Test artifacts cleanup: {removed_count} items removed, "
                   f"{space_freed // (1024 * 1024)} MB freed")
        
        return True
    
    def cleanup_docker_images(self, remove_all: bool = False) -> bool:
        """Remove Docker images related to ComfyUI."""
        logger.info("Cleaning up Docker images...")
        
        if not remove_all:
            # Remove dangling images first
            exit_code, stdout, stderr = self.run_command([
                "docker", "image", "prune", "-f"
            ])
            
            if exit_code == 0:
                logger.info("Removed dangling Docker images")
            else:
                logger.warning(f"Failed to remove dangling images: {stderr}")
        
        # List ComfyUI images
        exit_code, stdout, stderr = self.run_command([
            "docker", "images", "--filter", "reference=*/comfyui*", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"
        ])
        
        if exit_code != 0:
            logger.error(f"Failed to list Docker images: {stderr}")
            return False
        
        images = []
        for line in stdout.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    image_name = parts[0]
                    image_id = parts[1]
                    images.append((image_name, image_id))
        
        if not images:
            logger.info("No ComfyUI Docker images found")
            return True
        
        logger.info(f"Found {len(images)} ComfyUI images:")
        for image_name, image_id in images:
            logger.info(f"  {image_name} ({image_id[:12]})")
        
        if not self.confirm_action(f"Remove {len(images)} ComfyUI Docker images?"):
            logger.info("Docker image cleanup cancelled")
            return False
        
        removed_count = 0
        for image_name, image_id in images:
            exit_code, stdout, stderr = self.run_command([
                "docker", "rmi", "-f", image_id
            ])
            
            if exit_code == 0:
                logger.info(f"Removed image: {image_name}")
                removed_count += 1
            else:
                error_msg = f"Failed to remove {image_name}: {stderr}"
                logger.error(error_msg)
                self.cleanup_stats["errors"].append(error_msg)
        
        self.cleanup_stats["docker_images_removed"] = removed_count
        
        # Clean build cache
        if remove_all:
            exit_code, stdout, stderr = self.run_command([
                "docker", "builder", "prune", "-f"
            ])
            
            if exit_code == 0:
                logger.info("Cleaned Docker build cache")
            else:
                logger.warning(f"Failed to clean build cache: {stderr}")
        
        logger.info(f"Docker cleanup: {removed_count} images removed")
        return True
    
    def cleanup_git_artifacts(self) -> bool:
        """Clean up Git-related artifacts."""
        logger.info("Cleaning up Git artifacts...")
        
        # Clean untracked files (with confirmation)
        exit_code, stdout, stderr = self.run_command([
            "git", "status", "--porcelain"
        ])
        
        if exit_code != 0:
            logger.warning("Not in a Git repository or Git not available")
            return False
        
        untracked_files = []
        for line in stdout.strip().split('\n'):
            if line.startswith('??'):
                untracked_files.append(line[3:])
        
        if untracked_files:
            logger.info(f"Found {len(untracked_files)} untracked files:")
            for file in untracked_files[:10]:  # Show first 10
                logger.info(f"  {file}")
            if len(untracked_files) > 10:
                logger.info(f"  ... and {len(untracked_files) - 10} more")
            
            if self.confirm_action("Remove untracked files?"):
                exit_code, stdout, stderr = self.run_command([
                    "git", "clean", "-fd"
                ])
                
                if exit_code == 0:
                    logger.info("Removed untracked files")
                    self.cleanup_stats["files_removed"] += len(untracked_files)
                else:
                    error_msg = f"Failed to clean untracked files: {stderr}"
                    logger.error(error_msg)
                    self.cleanup_stats["errors"].append(error_msg)
        else:
            logger.info("No untracked files found")
        
        return True
    
    def cleanup_workspace_artifacts(self) -> bool:
        """Clean up workspace-related artifacts."""
        logger.info("Cleaning up workspace artifacts...")
        
        workspace_patterns = [
            "comfyui-without-flux/ComfyUI/temp/*",
            "comfyui-without-flux/ComfyUI/output/*",
            "comfyui-without-flux/*.log",
            "comfyui-with-flux/temp/*",
            "comfyui-with-flux/output/*"
        ]
        
        removed_count = 0
        space_freed = 0
        
        for pattern in workspace_patterns:
            matches = glob.glob(pattern)
            for match in matches:
                # Skip if it's in a critical directory structure
                if any(critical in match for critical in ['/models/', '/ComfyUI/custom_nodes/']):
                    continue
                
                size = self.get_file_size(match)
                
                try:
                    if os.path.isfile(match):
                        os.remove(match)
                        removed_count += 1
                        space_freed += size
                        logger.info(f"Removed workspace file: {match}")
                    elif os.path.isdir(match) and os.listdir(match):  # Only remove non-empty dirs
                        shutil.rmtree(match)
                        os.makedirs(match)  # Recreate empty directory
                        removed_count += 1
                        space_freed += size
                        logger.info(f"Cleaned workspace directory: {match}")
                except Exception as e:
                    error_msg = f"Failed to remove {match}: {e}"
                    logger.warning(error_msg)
        
        self.cleanup_stats["files_removed"] += removed_count
        self.cleanup_stats["space_freed_mb"] += space_freed // (1024 * 1024)
        
        logger.info(f"Workspace cleanup: {removed_count} items processed, "
                   f"{space_freed // (1024 * 1024)} MB freed")
        
        return True
    
    def cleanup_python_artifacts(self) -> bool:
        """Clean up Python-related artifacts."""
        logger.info("Cleaning up Python artifacts...")
        
        patterns = [
            "**/__pycache__",
            "**/*.pyc",
            "**/*.pyo",
            "**/*.pyd",
            ".tox",
            ".coverage",
            "htmlcov",
            ".pytest_cache",
            "*.egg-info",
            "dist",
            "build"
        ]
        
        removed_count = 0
        space_freed = 0
        
        for pattern in patterns:
            if '**' in pattern:
                # Use pathlib for recursive patterns
                for match in Path('.').rglob(pattern.replace('**/', '')):
                    size = self.get_file_size(str(match))
                    
                    try:
                        if match.is_file():
                            match.unlink()
                            removed_count += 1
                            space_freed += size
                            if self.verbose:
                                logger.debug(f"Removed Python file: {match}")
                        elif match.is_dir():
                            shutil.rmtree(str(match))
                            removed_count += 1
                            space_freed += size
                            if self.verbose:
                                logger.debug(f"Removed Python directory: {match}")
                    except Exception as e:
                        if self.verbose:
                            logger.warning(f"Failed to remove {match}: {e}")
            else:
                # Handle direct patterns
                matches = glob.glob(pattern)
                for match in matches:
                    size = self.get_file_size(match)
                    
                    try:
                        if os.path.isfile(match):
                            os.remove(match)
                            removed_count += 1
                            space_freed += size
                        elif os.path.isdir(match):
                            shutil.rmtree(match)
                            removed_count += 1
                            space_freed += size
                    except Exception as e:
                        if self.verbose:
                            logger.warning(f"Failed to remove {match}: {e}")
        
        self.cleanup_stats["files_removed"] += removed_count
        self.cleanup_stats["space_freed_mb"] += space_freed // (1024 * 1024)
        
        logger.info(f"Python artifacts cleanup: {removed_count} items removed, "
                   f"{space_freed // (1024 * 1024)} MB freed")
        
        return True
    
    def generate_cleanup_report(self) -> str:
        """Generate cleanup summary report."""
        report = []
        report.append("=" * 50)
        report.append("CLEANUP SUMMARY")
        report.append("=" * 50)
        report.append(f"Files/directories removed: {self.cleanup_stats['files_removed']}")
        report.append(f"Docker images removed: {self.cleanup_stats['docker_images_removed']}")
        report.append(f"Space freed: {self.cleanup_stats['space_freed_mb']} MB")
        
        if self.cleanup_stats['errors']:
            report.append(f"Errors encountered: {len(self.cleanup_stats['errors'])}")
            for error in self.cleanup_stats['errors'][:5]:  # Show first 5 errors
                report.append(f"  - {error}")
            if len(self.cleanup_stats['errors']) > 5:
                report.append(f"  ... and {len(self.cleanup_stats['errors']) - 5} more errors")
        else:
            report.append("No errors encountered")
        
        report.append("=" * 50)
        
        return "\n".join(report)
    
    def run_comprehensive_cleanup(self, include_docker: bool = False, include_git: bool = False) -> bool:
        """Run comprehensive cleanup of the project."""
        logger.info("Starting comprehensive project cleanup...")
        
        success = True
        
        # Always clean these
        success &= self.cleanup_test_artifacts()
        success &= self.cleanup_python_artifacts()
        success &= self.cleanup_workspace_artifacts()
        
        # Optional cleanups
        if include_docker:
            success &= self.cleanup_docker_images()
        
        if include_git:
            success &= self.cleanup_git_artifacts()
        
        # Generate and display report
        report = self.generate_cleanup_report()
        print("\n" + report)
        
        return success

def main():
    parser = argparse.ArgumentParser(
        description="ComfyUI Project Cleanup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean test artifacts only
  python cleanup.py --test-artifacts

  # Clean all Docker images (with confirmation)
  python cleanup.py --docker-images

  # Comprehensive cleanup
  python cleanup.py --all

  # Force cleanup without confirmation
  python cleanup.py --all --force

  # Verbose cleanup with all options
  python cleanup.py --all --include-git --verbose
        """
    )
    
    parser.add_argument(
        "--test-artifacts",
        action="store_true",
        help="Clean test artifacts and reports"
    )
    
    parser.add_argument(
        "--docker-images",
        action="store_true",
        help="Remove ComfyUI Docker images"
    )
    
    parser.add_argument(
        "--python-artifacts",
        action="store_true",
        help="Clean Python cache and build artifacts"
    )
    
    parser.add_argument(
        "--workspace-artifacts",
        action="store_true",
        help="Clean temporary workspace files"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run comprehensive cleanup (excludes Docker and Git by default)"
    )
    
    parser.add_argument(
        "--include-docker",
        action="store_true",
        help="Include Docker cleanup in comprehensive mode"
    )
    
    parser.add_argument(
        "--include-git",
        action="store_true",
        help="Include Git cleanup in comprehensive mode"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Initialize cleanup utility
    cleanup = ProjectCleanup(force=args.force, verbose=args.verbose)
    
    success = True
    
    try:
        if args.all:
            # Comprehensive cleanup
            success = cleanup.run_comprehensive_cleanup(
                include_docker=args.include_docker,
                include_git=args.include_git
            )
        else:
            # Individual cleanup operations
            if args.test_artifacts:
                success &= cleanup.cleanup_test_artifacts()
            
            if args.docker_images:
                success &= cleanup.cleanup_docker_images()
            
            if args.python_artifacts:
                success &= cleanup.cleanup_python_artifacts()
            
            if args.workspace_artifacts:
                success &= cleanup.cleanup_workspace_artifacts()
            
            if not any([args.test_artifacts, args.docker_images, args.python_artifacts, args.workspace_artifacts]):
                parser.print_help()
                return 1
            
            # Generate report for individual operations
            if any([args.test_artifacts, args.docker_images, args.python_artifacts, args.workspace_artifacts]):
                report = cleanup.generate_cleanup_report()
                print("\n" + report)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.warning("Cleanup interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Cleanup failed with exception: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 