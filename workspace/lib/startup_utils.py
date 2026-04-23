"""
Startup utilities for ComfyUI with Flux.
Provides modular functions for service initialization and management.
"""

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .common import Logger, CommandRunner, PathValidator, EnvironmentValidator


class AuthenticationManager:
    """Handles model authentication setup."""
    
    def __init__(self, logger: Optional = None):
        self.logger = logger or Logger.get_logger("AuthManager")
        self.runner = CommandRunner(self.logger)
    
    def validate_huggingface_token(self, token: str) -> bool:
        """Validate HuggingFace token format."""
        return bool(re.match(r'^hf_[A-Za-z0-9]{34}$', token))
    
    def validate_civitai_token(self, token: str) -> bool:
        """Validate CivitAI token format."""
        return bool(re.match(r'^[a-fA-F0-9]{32}$', token))
    
    def setup_huggingface_auth(self, token: str, auto_login: bool = True) -> bool:
        """Set up HuggingFace authentication."""
        if not token:
            self.logger.info("No HuggingFace token provided - skipping HF authentication")
            return True
        
        self.logger.info("Setting up HuggingFace authentication...")
        
        if not self.validate_huggingface_token(token):
            self.logger.warning("HuggingFace token format appears invalid")
            if not auto_login:
                return False
        
        # Set up cache directory
        hf_home = os.environ.get('HF_HOME', '/workspace/.cache/huggingface')
        Path(hf_home).mkdir(parents=True, exist_ok=True)
        os.environ['HF_HOME'] = hf_home
        
        # Try to login using huggingface-cli
        result = self.runner.run_safe(['which', 'huggingface-cli'])
        if result and result.returncode == 0:
            login_result = self.runner.run_safe(
                ['huggingface-cli', 'login', '--token', token],
                timeout=30
            )
            if login_result and login_result.returncode == 0:
                self.logger.info("✓ HuggingFace authentication successful")
                os.environ['HUGGINGFACE_HUB_TOKEN'] = token
                return True
            else:
                self.logger.warning("HuggingFace authentication failed")
                if not auto_login:
                    return False
        else:
            self.logger.warning("huggingface-cli not found - setting token as environment variable")
        
        os.environ['HUGGINGFACE_HUB_TOKEN'] = token
        return True
    
    def setup_civitai_auth(self, token: str, auto_login: bool = True) -> bool:
        """Set up CivitAI authentication."""
        if not token:
            self.logger.info("No CivitAI token provided - public access only")
            return True
        
        self.logger.info("Setting up CivitAI authentication...")
        
        if not self.validate_civitai_token(token):
            self.logger.warning("CivitAI token format appears invalid")
            if not auto_login:
                return False
        
        os.environ['CIVITAI_TOKEN'] = token
        self.logger.info("✓ CivitAI token configured")
        return True
    
    def setup_model_authentication(self, hf_token: str = "", civitai_token: str = "", 
                                 auto_login: bool = True, model_cache_dir: str = "/workspace/models") -> bool:
        """Set up all model authentication."""
        self.logger.info("=== Setting up model authentication ===")
        
        # Create model cache directory
        Path(model_cache_dir).mkdir(parents=True, exist_ok=True)
        
        # Set up authentication
        hf_success = self.setup_huggingface_auth(hf_token, auto_login)
        civitai_success = self.setup_civitai_auth(civitai_token, auto_login)
        
        if hf_success and civitai_success:
            self.logger.info("✓ Model authentication setup completed")
            return True
        else:
            self.logger.warning("Model authentication setup completed with warnings")
            return True  # Don't fail startup for auth issues


class ServiceManager:
    """Manages ComfyUI services (JupyterLab, ComfyUI, Flux Train UI)."""
    
    def __init__(self, workspace: str = "/workspace", logger: Optional = None):
        self.workspace = Path(workspace)
        self.logger = logger or Logger.get_logger("ServiceManager")
        self.runner = CommandRunner(self.logger)
        self.validator = EnvironmentValidator(self.logger)
    
    def detect_cuda(self) -> bool:
        """Detect CUDA availability."""
        self.logger.info("Detecting CUDA availability...")
        
        # Check nvidia-smi
        nvidia_result = self.runner.run_safe(['which', 'nvidia-smi'])
        if not nvidia_result or nvidia_result.returncode != 0:
            self.logger.info("nvidia-smi not found - CUDA not available")
            return False
        
        # Check PyTorch CUDA support
        cuda_check = self.runner.run_safe([
            'python3', '-c', 
            'import torch; print("CUDA available:", torch.cuda.is_available()); print("CUDA devices:", torch.cuda.device_count())'
        ])
        
        if cuda_check and cuda_check.returncode == 0 and "CUDA available: True" in cuda_check.stdout:
            self.logger.info("CUDA detected and available for PyTorch")
            return True
        else:
            self.logger.info("CUDA drivers found but PyTorch CUDA support not available")
            return False
    
    def create_jupyter_config(self):
        """Create JupyterLab configuration with terminal support."""
        self.logger.info("Creating JupyterLab configuration...")
        
        config_dir = Path(self.workspace) / '.jupyter' / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # JupyterLab configuration
        lab_config_file = config_dir / 'jupyter_lab_config.py'
        lab_config = '''
# JupyterLab Configuration for Terminal Support
c = get_config()

# Enable terminals - these are the correct settings for modern JupyterLab
c.ServerApp.terminals_enabled = True
c.TerminalManager.cull_inactive_timeout = 3600
c.TerminalManager.cull_interval = 300

# Allow root user (for Docker containers)
c.ServerApp.allow_root = True

# Terminal settings
c.TerminalManager.shell_command = ['/bin/bash']

# Security settings
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True
c.ServerApp.disable_check_xsrf = True

    # Token/password settings (updated for JupyterLab 4.x)
    c.IdentityProvider.token = ''
    c.ServerApp.password = ''

# IP and port binding
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.open_browser = False
'''
        
        with open(lab_config_file, 'w') as f:
            f.write(lab_config)
        
        self.logger.info(f"✓ JupyterLab config created at: {lab_config_file}")
        
        # Also create server configuration
        server_config_file = config_dir / 'jupyter_server_config.py'
        server_config = '''
# Jupyter Server Configuration
c = get_config()

# Enable terminals explicitly
c.ServerApp.terminals_enabled = True
c.TerminalManager.cull_inactive_timeout = 3600
c.TerminalManager.cull_interval = 300

# Allow root
c.ServerApp.allow_root = True

# Terminal shell settings
c.TerminalManager.shell_command = ['/bin/bash']

# Network settings
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True
c.ServerApp.disable_check_xsrf = True

    # Authentication (updated for JupyterLab 4.x)
    c.IdentityProvider.token = ''
    c.ServerApp.password = ''
'''
        
        with open(server_config_file, 'w') as f:
            f.write(server_config)
        
        self.logger.info(f"✓ Jupyter Server config created at: {server_config_file}")
        return config_dir

    def install_terminal_dependencies(self):
        """Install terminal-related dependencies."""
        self.logger.info("Installing terminal dependencies...")
        
        # First, uninstall conflicting packages
        conflicting_packages = ['notebook-shim', 'notebook']
        for package in conflicting_packages:
            result = self.runner.run_safe(
                ['pip', 'uninstall', '-y', package]
            )
            if result and result.returncode == 0:
                self.logger.info(f"✓ Removed conflicting package: {package}")
            else:
                self.logger.info(f"ℹ Package {package} not installed or removal failed")
        
        # Install/upgrade terminal-related dependencies in correct order
        packages = [
            'traitlets>=5.9.0',
            'terminado>=0.15.0',
            'jupyter-server-terminals>=0.4.4',
            'jupyterlab-server>=2.22.0',
            'jupyterlab>=4.0.0'
        ]
        
        for package in packages:
            result = self.runner.run_safe(
                ['pip', 'install', '--upgrade', '--force-reinstall', package]
            )
            if result and result.returncode == 0:
                self.logger.info(f"✓ {package} installed/updated")
            else:
                self.logger.info(f"⚠ Failed to install {package}")

    def start_jupyter_with_terminal(self, port=8888):
        """Start JupyterLab with terminal support."""
        self.logger.info("Starting JupyterLab with terminal support...")
        
        config_dir = Path(self.workspace) / '.jupyter' / 'config'
        config_file = config_dir / 'jupyter_lab_config.py'
        
        # Ensure config exists
        if not config_file.exists():
            self.create_jupyter_config()
        
        # Set all necessary Jupyter environment variables
        jupyter_env = {
            'JUPYTER_CONFIG_DIR': str(config_dir),
            'JUPYTER_DATA_DIR': str(Path(self.workspace) / '.jupyter' / 'data'),
            'JUPYTER_RUNTIME_DIR': str(Path(self.workspace) / '.jupyter' / 'runtime'),
            'SHELL': '/bin/bash',
            'TERM': 'xterm-color'
        }
        
        for key, value in jupyter_env.items():
            os.environ[key] = value
            # Create directories if they don't exist
            if 'DIR' in key:
                dir_path = Path(value)
                dir_path.mkdir(parents=True, exist_ok=True)
                # Set proper permissions for runtime directory
                if 'RUNTIME' in key:
                    try:
                        import stat
                        dir_path.chmod(stat.S_IRWXU)  # 0o700 - only owner can read/write/execute
                        self.logger.info(f"✓ Set secure permissions for {dir_path}")
                    except Exception as e:
                        self.logger.warning(f"Could not set permissions for {dir_path}: {e}")
        
        self.logger.info(f"✓ Set Jupyter environment variables")
        
        # Start JupyterLab with minimal, compatible configuration
        # Note: Many settings are handled in the config file to avoid duplication
        cmd = [
            'jupyter', 'lab',
            '--ip=0.0.0.0',
            f'--port={port}',
            '--no-browser',
            '--allow-root',
            f'--notebook-dir={self.workspace}',
            '--ServerApp.allow_origin=*',
            '--ServerApp.allow_remote_access=True',
            '--ServerApp.terminals_enabled=True',
            '--IdentityProvider.token=',
            '--ServerApp.password='
            # Note: disable_check_xsrf is set in config file to avoid duplication
        ]
        
        log_file = Path(self.workspace) / 'jupyter_startup.log'
        self.logger.info(f"Starting JupyterLab (logs: {log_file})...")
        
        try:
            with open(log_file, 'w') as f:
                process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
            
            self.logger.info(f"✓ JupyterLab started with PID: {process.pid}")
            self.logger.info(f"✓ JupyterLab accessible at: http://localhost:{port}/lab")
            self.logger.info("✓ Terminal should now be available in JupyterLab")
            
            # Wait a moment and check if the process is still running
            import time
            time.sleep(3)
            poll_result = process.poll()
            if poll_result is None:
                self.logger.info("✓ JupyterLab process is running successfully")
                self.logger.info("✓ To access terminal: File > New > Terminal (or use Launcher)")
            else:
                self.logger.info(f"⚠ JupyterLab process exited with code: {poll_result}")
                self.logger.info("Check the log file for details")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"✗ Failed to start JupyterLab: {e}")
            return False
    
    def start_flux_train_ui(self, port: int = 7860) -> bool:
        """Start Flux Train UI service."""
        self.logger.info("Starting Flux Train UI...")
        
        flux_train_dir = self.workspace / 'ai-toolkit'
        flux_train_script = flux_train_dir / 'flux_train_ui.py'
        
        if not flux_train_dir.exists():
            self.logger.warning(f"AI Toolkit directory not found: {flux_train_dir}")
            return True  # Not an error, just skip
        
        if not flux_train_script.exists():
            self.logger.warning(f"Flux Train UI script not found: {flux_train_script}")
            return True  # Not an error, just skip
        
        # Create modified script with correct launch parameters
        modified_script = self.workspace / 'flux_train_ui_server.py'
        try:
            with open(flux_train_script, 'r') as src, open(modified_script, 'w') as dst:
                content = src.read()
                # Replace launch parameters
                content = content.replace(
                    'demo.launch(share=True, show_error=True)',
                    f'demo.launch(server_name="0.0.0.0", server_port={port}, share=False, show_error=True)'
                )
                dst.write(content)
        except Exception as e:
            self.logger.error(f"Failed to create modified Flux Train UI script: {e}")
            return False
        
        # Start Flux Train UI
        cmd = ['python3', str(modified_script)]
        log_file = self.workspace / 'flux_train_ui.log'
        
        try:
            with open(log_file, 'w') as f:
                process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(self.workspace))
            
            self.logger.info(f"Flux Train UI started with PID: {process.pid}")
            self.logger.info(f"Flux Train UI accessible at: http://localhost:{port}")
            
            time.sleep(2)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Flux Train UI: {e}")
            return False
    
    def start_comfyui(self, port: int = 8188) -> bool:
        """Start ComfyUI service (this will exec and replace the process)."""
        self.logger.info("Starting ComfyUI...")
        
        comfyui_dir = self.workspace / 'ComfyUI'
        main_script = comfyui_dir / 'main.py'
        
        if not comfyui_dir.exists():
            self.logger.error(f"ComfyUI directory not found: {comfyui_dir}")
            return False
        
        if not main_script.exists():
            self.logger.error(f"ComfyUI main.py not found: {main_script}")
            return False
        
        # Build ComfyUI command
        cmd = ['python3', 'main.py', '--listen', f'--port={port}']
        
        if self.detect_cuda():
            self.logger.info("Starting ComfyUI with GPU support...")
        else:
            self.logger.info("Starting ComfyUI in CPU-only mode...")
            cmd.append('--cpu')
        
        self.logger.info(f"ComfyUI will be accessible at: http://localhost:{port}")
        self.logger.info(f"Executing: {' '.join(cmd)}")
        
        # Change to ComfyUI directory and exec
        os.chdir(str(comfyui_dir))
        os.execvp('python3', cmd)


class SetupManager:
    """Manages ComfyUI setup and initialization."""
    
    def __init__(self, workspace: str = "/workspace", logger: Optional = None):
        self.workspace = Path(workspace)
        self.logger = logger or Logger.get_logger("SetupManager")
        self.runner = CommandRunner(self.logger)
        self.marker_file = self.workspace / '.initialized'
    
    def setup_workflows(self) -> bool:
        """Set up ComfyUI workflow templates."""
        self.logger.info("Setting up ComfyUI workflow templates...")
        
        workflows_target = self.workspace / 'ComfyUI' / 'user' / 'default' / 'workflows'
        workflows_source = Path('/opt/app/workflows')
        
        # Create target directory
        workflows_target.mkdir(parents=True, exist_ok=True)
        
        if not workflows_source.exists():
            self.logger.warning(f"Workflow templates not found: {workflows_source}")
            return True
        
        # Copy workflow JSON files
        json_files = list(workflows_source.glob('*.json'))
        if json_files:
            self.logger.info(f"Copying {len(json_files)} workflow templates...")
            for json_file in json_files:
                try:
                    import shutil
                    shutil.copy2(json_file, workflows_target)
                except Exception as e:
                    self.logger.error(f"Failed to copy {json_file}: {e}")
                    return False
            
            self.logger.info(f"✓ Successfully copied {len(json_files)} workflow templates")
        else:
            self.logger.warning("No workflow JSON files found")
        
        return True
    
    def setup_comfyui(self, timeout: int = 300) -> bool:
        """Set up ComfyUI environment."""
        first_run = not self.marker_file.exists()
        
        if first_run:
            self.logger.info("First run - setting up ComfyUI environment...")
            
            # Copy application files
            copy_result = self.runner.run_safe(
                ['cp', '-r', '/opt/app/.', str(self.workspace)],
                timeout=timeout
            )
            
            if copy_result is None or copy_result.returncode != 0:
                error_msg = copy_result.stderr if copy_result and copy_result.stderr else "Unknown error"
                self.logger.error(f"Failed to copy application files: {error_msg}")
                return False
            
            self.logger.info("Application files copied successfully")
        else:
            self.logger.info("ComfyUI already initialized")
        
        # Always check and download dependencies
        self.logger.info("Checking and installing dependencies...")
        os.chdir(str(self.workspace))
        
        # Use the new dependency manager
        from .dependency_manager import DependencyManager
        dep_manager = DependencyManager()
        
        # Determine preset based on environment
        preset = os.getenv('DEPENDENCY_PRESET', 'standard')
        self.logger.info(f"Using dependency preset: {preset}")
        
        if not dep_manager.load_dependencies(preset=preset):
            self.logger.error("Failed to load dependencies")
            return False
        
        # Download missing dependencies
        self.logger.info("Downloading missing dependencies...")
        if not dep_manager.download_dependencies():
            self.logger.warning("Some dependencies failed to download, but continuing...")
        else:
            self.logger.info("✓ All dependencies downloaded successfully")
        
        # Set up workflows
        if not self.setup_workflows():
            self.logger.error("Failed to set up workflows")
            return False
        
        # Create marker file on first run
        if first_run:
            self.marker_file.touch()
            self.logger.info("Setup completed - marker file created")
        
        return True


class CleanupManager:
    """Manages cleanup activities during startup."""
    
    def __init__(self, workspace: str = "/workspace", logger: Optional = None):
        self.workspace = Path(workspace)
        self.logger = logger or Logger.get_logger("CleanupManager")
    
    def cleanup_workspace(self) -> bool:
        """Clean up workspace files."""
        self.logger.info("Performing workspace cleanup...")
        
        cleanup_items = [
            '/opt/app/workflows',
            self.workspace / 'workflows',
            self.workspace / 'models'
        ]
        
        cleanup_patterns = [
            self.workspace / '__pycache__',
            self.workspace / '*' / '__pycache__',
            self.workspace / '*' / '*' / '__pycache__'
        ]
        
        # Remove specific items
        for item in cleanup_items:
            item_path = Path(item)
            if item_path.exists():
                self.logger.info(f"Removing: {item}")
                try:
                    if item_path.is_dir():
                        import shutil
                        shutil.rmtree(item_path)
                    else:
                        item_path.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to remove {item}: {e}")
        
        self.logger.info("✓ Workspace cleanup completed")
        return True
    
    def cleanup_build_artifacts(self) -> bool:
        """Clean up build artifacts."""
        self.logger.info("Cleaning up build artifacts...")
        
        # Remove pip cache
        pip_cache = Path.home() / '.cache' / 'pip'
        if pip_cache.exists():
            try:
                import shutil
                shutil.rmtree(pip_cache)
                self.logger.info("Removed pip cache")
            except Exception as e:
                self.logger.warning(f"Failed to remove pip cache: {e}")
        
        # Clean up various file types
        patterns = ['*.pyc', '*.pyo', '*~', '.DS_Store']
        for pattern in patterns:
            for file_path in self.workspace.rglob(pattern):
                try:
                    file_path.unlink()
                except Exception:
                    pass
        
        # Remove .git directories
        for git_dir in self.workspace.rglob('.git'):
            if git_dir.is_dir():
                try:
                    import shutil
                    shutil.rmtree(git_dir)
                except Exception:
                    pass
        
        self.logger.info("✓ Build artifacts cleanup completed")
        return True
    
    def cleanup_logs(self) -> bool:
        """Manage log files."""
        self.logger.info("Managing log files...")
        
        log_files = [
            self.workspace / 'startup.log',
            self.workspace / 'jupyter.log',
            self.workspace / 'flux_train_ui.log'
        ]
        
        for log_file in log_files:
            if log_file.exists():
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    
                    if len(lines) > 1000:
                        self.logger.info(f"Truncating large log file: {log_file}")
                        with open(log_file, 'w') as f:
                            f.writelines(lines[-1000:])
                except Exception as e:
                    self.logger.warning(f"Failed to manage log file {log_file}: {e}")
        
        self.logger.info("✓ Log management completed")
        return True
    
    def cleanup_aggressive(self) -> bool:
        """Perform aggressive cleanup."""
        self.logger.info("Performing aggressive cleanup...")
        
        # Patterns to remove
        patterns = [
            'readme*', '*.md', 'license*', 'changelog*',
            'test*', '*.test', 'examples', 'docs',
            '*.c', '*.cpp', '*.h', '*.hpp', 'Makefile*',
            'setup.py', 'setup.cfg', 'requirements*.txt',
            'pyproject.toml', 'poetry.lock', 'Pipfile*'
        ]
        
        for pattern in patterns:
            for file_path in self.workspace.rglob(pattern):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
                elif file_path.is_dir():
                    try:
                        import shutil
                        shutil.rmtree(file_path)
                    except Exception:
                        pass
        
        self.logger.info("✓ Aggressive cleanup completed")
        return True
    
    def perform_startup_cleanup(self, enable_cleanup: bool = True, aggressive: bool = False) -> bool:
        """Perform all startup cleanup activities."""
        if not enable_cleanup:
            self.logger.info("Cleanup disabled")
            return True
        
        self.logger.info("=== Performing startup cleanup ===")
        self.logger.info(f"Cleanup mode: {'Aggressive' if aggressive else 'Standard'}")
        
        # Run cleanup functions
        self.cleanup_workspace()
        self.cleanup_build_artifacts()
        # self.cleanup_logs()
        
        if aggressive:
            self.cleanup_aggressive()
        
        # Report disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(str(self.workspace))
            free_gb = free // (1024**3)
            self.logger.info(f"Available disk space after cleanup: {free_gb}GB")
        except Exception:
            pass
        
        self.logger.info("=== Startup cleanup completed ===")
        return True 