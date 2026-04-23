#!/usr/bin/env python3
"""
ComfyUI Dependency Redeployment Script

This script allows you to check, validate, and redownload dependencies
for ComfyUI in a running container. It provides granular control over
dependency management without requiring a full restart.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any

# Add lib directory to path
lib_path = str(Path(__file__).parent.parent / 'lib')
sys.path.insert(0, lib_path)

# Import the lib package
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import Logger
from lib.dependency_manager import DependencyManager


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ComfyUI Dependency Redeployment Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check all dependencies (default preset)
  python3 redeploy_dependencies.py --check

  # Redownload all missing dependencies
  python3 redeploy_dependencies.py --download

  # Force redownload all dependencies
  python3 redeploy_dependencies.py --download --force

  # Use specific preset
  python3 redeploy_dependencies.py --preset full --download

  # Check specific categories
  python3 redeploy_dependencies.py --check --categories core_dependencies,essential_models

  # Interactive mode with prompts
  python3 redeploy_dependencies.py --interactive

  # Show available presets
  python3 redeploy_dependencies.py --list-presets

Environment Variables:
  DEPENDENCY_PRESET      Default preset to use (minimal, standard, full)
  WORKSPACE             Workspace directory (default: /workspace)
        """
    )
    
    parser.add_argument(
        '--preset', '-p',
        choices=['minimal', 'standard', 'full'],
        help='Dependency preset to use (default: from DEPENDENCY_PRESET env var or "standard")'
    )
    
    parser.add_argument(
        '--workspace', '-w',
        default=os.getenv('WORKSPACE', '/workspace'),
        help='Workspace directory (default: /workspace or WORKSPACE env var)'
    )
    
    parser.add_argument(
        '--dependencies-file',
        default='dependencies.yaml',
        help='Dependencies configuration file (default: dependencies.yaml)'
    )
    
    # Actions
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check existing dependencies and show status'
    )
    
    action_group.add_argument(
        '--download', '-d',
        action='store_true',
        help='Download missing dependencies'
    )
    
    action_group.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Interactive mode with prompts for actions'
    )
    
    action_group.add_argument(
        '--list-presets',
        action='store_true',
        help='List available dependency presets'
    )
    
    action_group.add_argument(
        '--summary',
        action='store_true',
        help='Show dependency summary by category and type'
    )
    
    # Options
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Force redownload even if dependencies exist'
    )
    
    parser.add_argument(
        '--categories',
        help='Comma-separated list of categories to process (e.g., core_dependencies,essential_models)'
    )
    
    parser.add_argument(
        '--priorities',
        help='Comma-separated list of priorities to process (e.g., high,medium)'
    )
    
    parser.add_argument(
        '--types',
        help='Comma-separated list of dependency types to process (e.g., git,file,huggingface)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--log-file',
        help='Log file path (default: workspace/dependency_redeploy.log)'
    )
    
    return parser.parse_args()


def setup_logger(args: argparse.Namespace) -> Logger:
    """Set up logging configuration."""
    log_level = "DEBUG" if args.verbose else "INFO"
    log_file = args.log_file or f"{args.workspace}/dependency_redeploy.log"
    return Logger.get_logger("DependencyRedeploy", level=log_level, log_file=log_file)


def filter_dependencies(dependencies: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Filter dependencies based on command line criteria."""
    filtered = dependencies
    
    # Filter by categories
    if args.categories:
        categories = [cat.strip() for cat in args.categories.split(',')]
        filtered = [dep for dep in filtered if dep.get('category') in categories]
    
    # Filter by priorities
    if args.priorities:
        priorities = [pri.strip() for pri in args.priorities.split(',')]
        filtered = [dep for dep in filtered if dep.get('priority') in priorities]
    
    # Filter by types
    if args.types:
        types = [typ.strip() for typ in args.types.split(',')]
        filtered = [dep for dep in filtered if dep.get('type') in types]
    
    return filtered


def check_dependencies(dep_manager: DependencyManager, logger: Logger, filtered_deps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Check dependency status and return detailed results."""
    logger.info("Checking dependency status...")
    
    existing = []
    missing = []
    
    for dep in filtered_deps:
        name = dep.get('name', 'unnamed')
        if dep_manager._check_dependency_exists(dep):
            existing.append(dep)
            logger.info(f"  ✓ {name}")
        else:
            missing.append(dep)
            logger.info(f"  ✗ {name}")
    
    total = len(filtered_deps)
    completion_rate = (len(existing) / total) * 100 if total > 0 else 0
    
    results = {
        'total': total,
        'existing': existing,
        'missing': missing,
        'completion_rate': completion_rate
    }
    
    logger.info("\nDependency Status Summary:")
    logger.info(f"  Total dependencies: {total}")
    logger.info(f"  ✅ Existing: {len(existing)}")
    logger.info(f"  ❌ Missing: {len(missing)}")
    logger.info(f"  📊 Completion: {completion_rate:.1f}%")
    
    return results


def download_dependencies(dep_manager: DependencyManager, logger: Logger, deps_to_download: List[Dict[str, Any]], force: bool = False) -> bool:
    """Download specified dependencies."""
    if not deps_to_download:
        logger.info("No dependencies to download")
        return True
    
    logger.info(f"Downloading {len(deps_to_download)} dependencies...")
    
    # Temporarily replace the manager's dependencies for download
    original_deps = dep_manager.dependencies
    dep_manager.dependencies = deps_to_download
    
    try:
        success = dep_manager.download_dependencies(force_download=force)
        return success
    finally:
        # Restore original dependencies
        dep_manager.dependencies = original_deps


def interactive_mode(dep_manager: DependencyManager, logger: Logger, args: argparse.Namespace) -> None:
    """Run in interactive mode with user prompts."""
    logger.info("🔧 Interactive Dependency Management")
    logger.info("=" * 50)
    
    while True:
        print("\nAvailable actions:")
        print("1. Check dependency status")
        print("2. Download missing dependencies")
        print("3. Force redownload all dependencies")
        print("4. Show dependency summary")
        print("5. List available presets")
        print("6. Change preset")
        print("7. Exit")
        
        try:
            choice = input("\nSelect an action (1-7): ").strip()
            
            if choice == '1':
                # Check dependencies
                filtered_deps = filter_dependencies(dep_manager.dependencies, args)
                check_dependencies(dep_manager, logger, filtered_deps)
                
            elif choice == '2':
                # Download missing
                filtered_deps = filter_dependencies(dep_manager.dependencies, args)
                status = check_dependencies(dep_manager, logger, filtered_deps)
                
                if status['missing']:
                    confirm = input(f"\nDownload {len(status['missing'])} missing dependencies? (y/N): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        download_dependencies(dep_manager, logger, status['missing'], force=False)
                else:
                    logger.info("No missing dependencies to download")
                    
            elif choice == '3':
                # Force redownload all
                filtered_deps = filter_dependencies(dep_manager.dependencies, args)
                confirm = input(f"\nForce redownload {len(filtered_deps)} dependencies? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    download_dependencies(dep_manager, logger, filtered_deps, force=True)
                    
            elif choice == '4':
                # Show summary
                summary = dep_manager.get_dependency_summary()
                print_summary(summary, logger)
                
            elif choice == '5':
                # List presets
                presets = dep_manager.get_available_presets()
                logger.info("\nAvailable presets:")
                for name, desc in presets.items():
                    logger.info(f"  {name}: {desc}")
                    
            elif choice == '6':
                # Change preset
                presets = dep_manager.get_available_presets()
                logger.info("\nAvailable presets:")
                for name, desc in presets.items():
                    logger.info(f"  {name}: {desc}")
                
                new_preset = input(f"\nEnter preset name (current: {args.preset}): ").strip()
                if new_preset in presets:
                    args.preset = new_preset
                    if dep_manager.load_dependencies(new_preset):
                        logger.info(f"Switched to preset: {new_preset}")
                    else:
                        logger.error("Failed to load new preset")
                else:
                    logger.warning("Invalid preset name")
                    
            elif choice == '7':
                logger.info("Exiting...")
                break
                
            else:
                print("Invalid choice. Please select 1-7.")
                
        except KeyboardInterrupt:
            logger.info("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error: {e}")


def print_summary(summary: Dict[str, Any], logger: Logger) -> None:
    """Print dependency summary in a formatted way."""
    logger.info("\nDependency Summary:")
    logger.info("=" * 40)
    
    if 'error' in summary:
        logger.error(f"Error: {summary['error']}")
        return
    
    logger.info(f"Total dependencies: {summary.get('total_dependencies', 0)}")
    logger.info(f"Format: {summary.get('format', 'unknown')}")
    logger.info(f"Estimated size: {summary.get('estimated_size_mb', 0)} MB")
    
    # Categories
    categories = summary.get('categories', {})
    if categories:
        logger.info("\nBy Category:")
        for category, count in categories.items():
            logger.info(f"  {category}: {count}")
    
    # Priorities
    priorities = summary.get('priorities', {})
    if priorities:
        logger.info("\nBy Priority:")
        for priority, count in priorities.items():
            logger.info(f"  {priority}: {count}")
    
    # Types
    types = summary.get('types', {})
    if types:
        logger.info("\nBy Type:")
        for dep_type, count in types.items():
            logger.info(f"  {dep_type}: {count}")


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Default preset
    if not args.preset:
        args.preset = os.getenv('DEPENDENCY_PRESET', 'standard')
    
    # Set up logging
    logger = setup_logger(args)
    
    logger.info("🔧 ComfyUI Dependency Redeployment Script")
    logger.info("=" * 50)
    logger.info(f"Workspace: {args.workspace}")
    logger.info(f"Dependencies file: {args.dependencies_file}")
    logger.info(f"Preset: {args.preset}")
    
    # Change to workspace directory
    try:
        os.chdir(args.workspace)
        logger.info(f"Changed to workspace: {os.getcwd()}")
    except Exception as e:
        logger.error(f"Failed to change to workspace: {e}")
        return 1
    
    # Initialize dependency manager
    dep_manager = DependencyManager(args.dependencies_file, logger)
    
    # Load dependencies
    if not dep_manager.load_dependencies(args.preset):
        logger.error("Failed to load dependencies")
        return 1
    
    # Validate dependency structure
    errors = dep_manager.validate_dependency_structure()
    if errors:
        logger.warning("Dependency validation errors:")
        for error in errors:
            logger.warning(f"  {error}")
    
    # Filter dependencies if specified
    filtered_deps = filter_dependencies(dep_manager.dependencies, args)
    if len(filtered_deps) != len(dep_manager.dependencies):
        logger.info(f"Filtered to {len(filtered_deps)} dependencies based on criteria")
    
    # Execute requested action
    try:
        if args.list_presets:
            presets = dep_manager.get_available_presets()
            logger.info("\nAvailable dependency presets:")
            for name, desc in presets.items():
                logger.info(f"  {name}: {desc}")
                
        elif args.summary:
            summary = dep_manager.get_dependency_summary()
            print_summary(summary, logger)
            
        elif args.check:
            check_dependencies(dep_manager, logger, filtered_deps)
            
        elif args.download:
            status = check_dependencies(dep_manager, logger, filtered_deps)
            
            if args.force:
                logger.info(f"Force downloading {len(filtered_deps)} dependencies...")
                download_dependencies(dep_manager, logger, filtered_deps, force=True)
            elif status['missing']:
                logger.info(f"Downloading {len(status['missing'])} missing dependencies...")
                download_dependencies(dep_manager, logger, status['missing'], force=False)
            else:
                logger.info("No missing dependencies to download")
                
        elif args.interactive:
            interactive_mode(dep_manager, logger, args)
            
        else:
            # Default action: check dependencies
            logger.info("No action specified, performing dependency check...")
            check_dependencies(dep_manager, logger, filtered_deps)
        
        logger.info("✅ Script completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Script failed with error: {e}")
        logger.debug("Full traceback:", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main()) 