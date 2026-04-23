#!/usr/bin/env python3
"""
JupyterLab Terminal Fix Script

This script fixes common JupyterLab terminal issues by:
1. Installing missing terminal dependencies
2. Configuring JupyterLab for terminal support
3. Restarting JupyterLab with proper configuration
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def log(message):
    """Simple logging function."""
    print(f"[JUPYTER-FIX] {message}")


def run_command(cmd, description="", check=True):
    """Run a command and return result."""
    log(f"Running: {description or ' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if check and result.returncode != 0:
            log(f"ERROR: Command failed with exit code {result.returncode}")
            log(f"STDERR: {result.stderr}")
            return False
        return result
    except Exception as e:
        log(f"ERROR: Command failed with exception: {e}")
        return False


def check_jupyter_installed():
    """Check if JupyterLab is installed."""
    log("Checking JupyterLab installation...")
    result = run_command(['jupyter', '--version'], "Checking Jupyter version")
    if result:
        log("✓ JupyterLab is installed")
        return True
    else:
        log("✗ JupyterLab is not installed or not accessible")
        return False


def install_terminal_dependencies():
    """Install terminal-related dependencies."""
    log("Installing terminal dependencies...")
    
    # First, uninstall conflicting packages
    conflicting_packages = ['notebook-shim']
    for package in conflicting_packages:
        result = run_command(
            ['pip', 'uninstall', '-y', package],
            f"Removing conflicting package {package}",
            check=False
        )
        if result and result.returncode == 0:
            log(f"✓ Removed conflicting package: {package}")
    
    # Install/upgrade terminal-related dependencies in correct order
    packages = [
        'traitlets>=5.9.0',
        'terminado>=0.15.0',
        'jupyter-server-terminals>=0.4.4',
        'jupyterlab-server>=2.22.0',
        'jupyterlab>=4.0.0'
    ]
    
    for package in packages:
        result = run_command(
            ['pip', 'install', '--upgrade', '--force-reinstall', package],
            f"Installing {package}",
            check=False
        )
        if result and result.returncode == 0:
            log(f"✓ {package} installed/updated")
        else:
            log(f"⚠ Failed to install {package}")


def create_jupyter_config(workspace="/workspace"):
    """Create JupyterLab configuration with terminal support."""
    log("Creating JupyterLab configuration...")
    
    config_dir = Path(workspace) / '.jupyter' / 'config'
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

# Token/password settings
c.ServerApp.token = ''
c.ServerApp.password = ''

# IP and port binding
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.open_browser = False
'''
    
    with open(lab_config_file, 'w') as f:
        f.write(lab_config)
    
    log(f"✓ JupyterLab config created at: {lab_config_file}")
    
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

# Authentication
c.ServerApp.token = ''
c.ServerApp.password = ''
'''
    
    with open(server_config_file, 'w') as f:
        f.write(server_config)
    
    log(f"✓ Jupyter Server config created at: {server_config_file}")
    return config_dir


def clean_jupyter_environment():
    """Clean up problematic JupyterLab configurations and extensions."""
    log("Cleaning JupyterLab environment...")
    
    # Clean lab workspace and settings
    workspace = os.getenv('WORKSPACE', '/workspace')
    jupyter_dirs = [
        Path(workspace) / '.jupyter',
        Path.home() / '.jupyter',
        Path('/root/.jupyter') if os.path.exists('/root') else None
    ]
    
    for jupyter_dir in jupyter_dirs:
        if jupyter_dir and jupyter_dir.exists():
            # Remove problematic cached files
            problematic_files = [
                jupyter_dir / 'lab' / 'workspaces',
                jupyter_dir / 'lab' / 'settings',
                jupyter_dir / 'runtime'
            ]
            
            for file_path in problematic_files:
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            import shutil
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        log(f"✓ Cleaned: {file_path}")
                    except Exception as e:
                        log(f"⚠ Could not clean {file_path}: {e}")


def check_terminal_availability():
    """Check if terminal is available in JupyterLab."""
    log("Checking terminal availability...")
    
    # Check if terminado is available
    try:
        import terminado
        log(f"✓ terminado version: {terminado.__version__}")
    except ImportError:
        log("✗ terminado is not installed")
        return False
    
    # Check if bash is available
    result = run_command(['which', 'bash'], "Checking bash availability")
    if result and result.returncode == 0:
        log(f"✓ bash available at: {result.stdout.strip()}")
    else:
        log("✗ bash is not available")
        return False
    
    return True


def stop_existing_jupyter():
    """Stop any existing JupyterLab processes."""
    log("Stopping existing JupyterLab processes...")
    
    # Try to find and kill jupyter processes
    result = run_command(['pkill', '-f', 'jupyter'], "Stopping Jupyter processes", check=False)
    if result and result.returncode == 0:
        log("✓ Stopped existing Jupyter processes")
    else:
        log("ℹ No existing Jupyter processes found")


def start_jupyter_with_terminal(workspace="/workspace", port=8888):
    """Start JupyterLab with terminal support."""
    log("Starting JupyterLab with terminal support...")
    
    config_dir = Path(workspace) / '.jupyter' / 'config'
    config_file = config_dir / 'jupyter_lab_config.py'
    
    # Ensure config exists
    if not config_file.exists():
        create_jupyter_config(workspace)
    
    # Set all necessary Jupyter environment variables
    jupyter_env = {
        'JUPYTER_CONFIG_DIR': str(config_dir),
        'JUPYTER_DATA_DIR': str(Path(workspace) / '.jupyter' / 'data'),
        'JUPYTER_RUNTIME_DIR': str(Path(workspace) / '.jupyter' / 'runtime'),
        'SHELL': '/bin/bash',
        'TERM': 'xterm-color'
    }
    
    for key, value in jupyter_env.items():
        os.environ[key] = value
        # Create directories if they don't exist
        if 'DIR' in key:
            Path(value).mkdir(parents=True, exist_ok=True)
    
    log(f"✓ Set Jupyter environment variables")
    
    # Start JupyterLab with minimal, compatible configuration
    cmd = [
        'jupyter', 'lab',
        '--ip=0.0.0.0',
        f'--port={port}',
        '--no-browser',
        '--allow-root',
        f'--notebook-dir={workspace}',
        '--ServerApp.allow_origin=*',
        '--ServerApp.allow_remote_access=True',
        '--ServerApp.terminals_enabled=True',
        '--ServerApp.token=',
        '--ServerApp.password=',
        '--ServerApp.disable_check_xsrf=True'
    ]
    
    log_file = Path(workspace) / 'jupyter_terminal_fix.log'
    log(f"Starting JupyterLab (logs: {log_file})...")
    
    try:
        with open(log_file, 'w') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        
        log(f"✓ JupyterLab started with PID: {process.pid}")
        log(f"✓ JupyterLab accessible at: http://localhost:{port}/lab")
        log("✓ Terminal should now be available in JupyterLab")
        
        # Wait a moment and check if the process is still running
        import time
        time.sleep(3)
        poll_result = process.poll()
        if poll_result is None:
            log("✓ JupyterLab process is running successfully")
            log("✓ To access terminal: File > New > Terminal (or use Launcher)")
        else:
            log(f"⚠ JupyterLab process exited with code: {poll_result}")
            log("Check the log file for details")
            return False
        
        return True
        
    except Exception as e:
        log(f"✗ Failed to start JupyterLab: {e}")
        return False


def troubleshoot_terminal_issues():
    """Provide troubleshooting information for terminal issues."""
    log("🔍 Terminal Troubleshooting Information:")
    log("-" * 30)
    
    # Check if we're in a container
    if os.path.exists('/.dockerenv'):
        log("✓ Running in Docker container")
    else:
        log("ℹ Not running in Docker container")
    
    # Check shell availability
    shells = ['/bin/bash', '/bin/sh', '/usr/bin/bash']
    for shell in shells:
        if os.path.exists(shell):
            log(f"✓ Shell available: {shell}")
        else:
            log(f"✗ Shell not found: {shell}")
    
    # Check Python packages
    packages_to_check = ['terminado', 'jupyter_server', 'jupyterlab']
    for package in packages_to_check:
        try:
            result = run_command(['pip', 'show', package], f"Checking {package}", check=False)
            if result and result.returncode == 0:
                lines = result.stdout.split('\n')
                version_line = next((line for line in lines if line.startswith('Version:')), None)
                if version_line:
                    version = version_line.split(':', 1)[1].strip()
                    log(f"✓ {package}: {version}")
            else:
                log(f"✗ {package}: Not installed")
        except Exception:
            log(f"✗ {package}: Check failed")


def main():
    """Main entry point."""
    log("🔧 JupyterLab Terminal Fix Script")
    log("=" * 50)
    
    workspace = os.getenv('WORKSPACE', '/workspace')
    port = int(os.getenv('JUPYTER_PORT', '8888'))
    
    log(f"Workspace: {workspace}")
    log(f"Port: {port}")
    
    # Change to workspace
    try:
        os.chdir(workspace)
        log(f"Changed to workspace: {os.getcwd()}")
    except Exception as e:
        log(f"Warning: Could not change to workspace: {e}")
    
    # Step 0: Show troubleshooting info
    troubleshoot_terminal_issues()
    
    # Step 1: Check JupyterLab installation
    if not check_jupyter_installed():
        log("Please install JupyterLab first")
        return 1
    
    # Step 2: Stop existing JupyterLab processes
    stop_existing_jupyter()
    
    # Step 3: Clean environment
    clean_jupyter_environment()
    
    # Step 4: Install terminal dependencies
    install_terminal_dependencies()
    
    # Step 5: Check terminal availability
    check_terminal_availability()
    
    # Step 6: Create clean configuration
    create_jupyter_config(workspace)
    
    # Step 7: Start JupyterLab with terminal support
    if start_jupyter_with_terminal(workspace, port):
        log("✅ JupyterLab terminal fix completed successfully!")
        log(f"   Access JupyterLab at: http://localhost:{port}/lab")
        log("   Terminal should be available in the Launcher or File menu")
        return 0
    else:
        log("❌ Failed to start JupyterLab with terminal support")
        return 1


if __name__ == '__main__':
    sys.exit(main()) 