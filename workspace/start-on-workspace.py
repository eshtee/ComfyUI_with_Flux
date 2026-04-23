#!/usr/bin/env python3
"""
Simplified ComfyUI Startup Script

This script replaces the complex bash startup script with a structured Python implementation.
It provides modular startup management with proper error handling and logging.
"""

import os
import sys
import argparse
from pathlib import Path

# Add lib directory to path
lib_path = str(Path(__file__).parent.parent / 'lib')
sys.path.insert(0, lib_path)

# Import the lib package
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import Logger
from lib.startup_utils import (
    AuthenticationManager, 
    ServiceManager, 
    SetupManager, 
    CleanupManager
)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ComfyUI Startup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  HF_TOKEN                HuggingFace token for model access
  CIVITAI_TOKEN          CivitAI token for model access
  DEPENDENCY_PRESET      Dependency preset to use (minimal, standard, full)
  JUPYTER_PORT           JupyterLab port (default: 8888)
  JUPYTER_TOKEN          JupyterLab token
  JUPYTER_PASSWORD       JupyterLab password
  FLUX_TRAIN_UI_PORT     Flux Train UI port (default: 7860)
  COMFYUI_PORT           ComfyUI port (default: 8188)
  ENABLE_CLEANUP         Enable workspace cleanup (default: true)
  AGGRESSIVE_CLEANUP     Enable aggressive cleanup (default: false)
  MODEL_CACHE_DIR        Model cache directory (default: /workspace/models)

Examples:
  python3 start-on-workspace-new.py
  python3 start-on-workspace-new.py --skip-auth
  python3 start-on-workspace-new.py --skip-cleanup --verbose
  python3 start-on-workspace-new.py --dependency-preset minimal
        """
    )
    
    parser.add_argument(
        '--workspace', '-w',
        default='/workspace',
        help='Workspace directory (default: /workspace)'
    )
    
    parser.add_argument(
        '--dependency-preset',
        choices=['minimal', 'standard', 'full'],
        help='Dependency preset to use for downloads (default: from DEPENDENCY_PRESET env var or "standard")'
    )
    
    parser.add_argument(
        '--skip-auth',
        action='store_true',
        help='Skip authentication setup'
    )
    
    parser.add_argument(
        '--skip-cleanup',
        action='store_true',
        help='Skip workspace cleanup'
    )
    
    parser.add_argument(
        '--skip-services',
        action='store_true',
        help='Skip starting additional services (Jupyter, Flux Train UI)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--log-file',
        help='Log file path (default: workspace/startup.log)'
    )
    
    return parser.parse_args()


def setup_environment(args: argparse.Namespace) -> dict:
    """Set up environment configuration."""
    config = {
        'workspace': args.workspace,
        'skip_auth': args.skip_auth,
        'skip_cleanup': args.skip_cleanup,
        'skip_services': args.skip_services,
        'verbose': args.verbose,
        
        # Dependencies
        'dependency_preset': args.dependency_preset or os.getenv('DEPENDENCY_PRESET', 'standard'),
        
        # Authentication
        'hf_token': os.getenv('HF_TOKEN', ''),
        'civitai_token': os.getenv('CIVITAI_TOKEN', ''),
        
        # Service ports
        'jupyter_port': int(os.getenv('JUPYTER_PORT', '8888')),
        'jupyter_token': os.getenv('JUPYTER_TOKEN', ''),
        'jupyter_password': os.getenv('JUPYTER_PASSWORD', ''),
        'flux_train_ui_port': int(os.getenv('FLUX_TRAIN_UI_PORT', '7860')),
        'comfyui_port': int(os.getenv('COMFYUI_PORT', '8188')),
        
        # Cleanup options
        'enable_cleanup': os.getenv('ENABLE_CLEANUP', 'true').lower() == 'true',
        'aggressive_cleanup': os.getenv('AGGRESSIVE_CLEANUP', 'false').lower() == 'true',
        
        # Model cache
        'model_cache_dir': os.getenv('MODEL_CACHE_DIR', '/workspace/models'),
    }
    
    # Override cleanup if skipped
    if args.skip_cleanup:
        config['enable_cleanup'] = False
    
    # Set dependency preset as environment variable for SetupManager
    os.environ['DEPENDENCY_PRESET'] = config['dependency_preset']
    
    return config


def main():
    """Main startup sequence."""
    args = parse_arguments()
    config = setup_environment(args)
    
    # Set up logging
    log_level = "DEBUG" if config['verbose'] else "INFO"
    log_file = args.log_file or f"{config['workspace']}/startup.log"
    logger = Logger.get_logger("StartupScript", level=log_level, log_file=log_file)
    
    logger.info("=" * 60)
    logger.info("ComfyUI Startup Script - Simplified Python Version")
    logger.info("=" * 60)
    logger.info(f"Workspace: {config['workspace']}")
    logger.info(f"Dependency preset: {config['dependency_preset']}")
    logger.info(f"Log file: {log_file}")
    
    try:
        
        
        # Step 2: Authentication Setup
        if not config['skip_auth']:
            logger.info("Step 2/7: Setting up authentication...")
            auth_manager = AuthenticationManager(logger)
            if not auth_manager.setup_model_authentication(
                hf_token=config['hf_token'],
                civitai_token=config['civitai_token'],
                model_cache_dir=config['model_cache_dir']
            ):
                logger.error("Authentication setup failed")
                return 1
            logger.info("✓ Authentication setup completed")
        else:
            logger.info("Step 2/7: Skipping authentication setup")
        
        # Step 3: ComfyUI Environment Setup (includes dependency downloads)
        logger.info("Step 3/7: Setting up ComfyUI environment...")
        setup_manager = SetupManager(config['workspace'], logger)
        if not setup_manager.setup_comfyui():
            logger.error("ComfyUI setup failed")
            return 1
        logger.info("✓ ComfyUI environment setup completed")
        
        # Step 4: Service Manager Initialization
        logger.info("Step 4/7: Initializing service manager...")
        service_manager = ServiceManager(config['workspace'], logger)
        logger.info("✓ Service manager initialized")
        
        # Step 5: Start Additional Services
        if not config['skip_services']:
            logger.info("Step 5/7: Starting additional services...")
            service_manager.install_terminal_dependencies() 
            # Start JupyterLab
            if service_manager.start_jupyter_with_terminal(
                port=config['jupyter_port']
            ):
                logger.info(f"✓ JupyterLab started on port {config['jupyter_port']}")
            else:
                logger.warning("JupyterLab startup failed")
            
            # Start Flux Train UI
            if service_manager.start_flux_train_ui(port=config['flux_train_ui_port']):
                logger.info(f"✓ Flux Train UI started on port {config['flux_train_ui_port']}")
            else:
                logger.warning("Flux Train UI startup failed")
            
            logger.info("✓ Additional services startup completed")
        else:
            logger.info("Step 5/7: Skipping additional services")
        
        # Step 6: Environment Validation
        logger.info("Step 6/7: Validating environment...")
        cuda_available = service_manager.detect_cuda()
        if cuda_available:
            logger.info("✓ CUDA detected - GPU acceleration available")
        else:
            logger.info("! CUDA not detected - using CPU mode")
        logger.info("✓ Environment validation completed")
        
        # Step 7: Start ComfyUI (this will exec and replace the process)
        logger.info("Step 7/7: Starting ComfyUI...")
        logger.info("=" * 60)
        logger.info("Startup sequence completed successfully!")
        logger.info("=" * 60)
        
        # Step 1: Workspace Cleanup
        if config['enable_cleanup']:
            logger.info("Step 1/7: Performing workspace cleanup...")
            cleanup_manager = CleanupManager(config['workspace'], logger)
            if not cleanup_manager.perform_startup_cleanup(
                enable_cleanup=True, 
                aggressive=config['aggressive_cleanup']
            ):
                logger.error("Workspace cleanup failed")
                return 1
            logger.info("✓ Workspace cleanup completed")
        else:
            logger.info("Step 1/7: Skipping workspace cleanup")
            
        # This call will exec and replace the current process
        if not service_manager.start_comfyui(port=config['comfyui_port']):
            logger.error("ComfyUI startup failed")
            return 1
        
        # This line should never be reached due to exec
        logger.error("Unexpected return from ComfyUI startup")
        return 1
        
    except KeyboardInterrupt:
        logger.info("Startup interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Startup failed with error: {e}")
        logger.debug("Full traceback:", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main()) 