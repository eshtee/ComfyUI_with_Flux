"""
Common utilities shared across ComfyUI build and runtime scripts.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class Logger:
    """Centralized logging configuration."""
    
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def get_logger(cls, name: str, level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
        """Get or create a logger with consistent formatting."""
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Could not create file handler for {log_file}: {e}")
        
        cls._loggers[name] = logger
        return logger


class PathValidator:
    """Path validation and manipulation utilities."""
    
    @staticmethod
    def ensure_dir(path: Path) -> bool:
        """Ensure directory exists, create if needed."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def is_valid_path(path: str) -> bool:
        """Check if path is valid and accessible."""
        try:
            Path(path).resolve()
            return True
        except (OSError, ValueError):
            return False
    
    @staticmethod
    def get_size_mb(path: Path) -> float:
        """Get file/directory size in MB."""
        if not path.exists():
            return 0.0
        
        if path.is_file():
            return path.stat().st_size / (1024 * 1024)
        
        # Directory size
        total_size = 0
        try:
            for item in path.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
        except (PermissionError, OSError):
            pass
        
        return total_size / (1024 * 1024)
    
    @staticmethod
    def safe_remove(path: Path) -> bool:
        """Safely remove file or directory."""
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                import shutil
                shutil.rmtree(path)
            return True
        except Exception:
            return False


class CommandRunner:
    """Execute system commands with consistent error handling."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or Logger.get_logger("CommandRunner")
    
    def run(
        self, 
        cmd: List[str], 
        cwd: Optional[Path] = None,
        capture_output: bool = True,
        check: bool = True,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """Run command with consistent logging and error handling."""
        
        cmd_str = ' '.join(cmd)
        self.logger.debug(f"Running command: {cmd_str}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=check,
                timeout=timeout
            )
            
            if result.returncode == 0:
                self.logger.debug(f"Command succeeded: {cmd_str}")
            else:
                self.logger.warning(f"Command failed with code {result.returncode}: {cmd_str}")
            
            return result
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {cmd_str}")
            self.logger.error(f"Exit code: {e.returncode}")
            if e.stdout:
                self.logger.error(f"Stdout: {e.stdout}")
            if e.stderr:
                self.logger.error(f"Stderr: {e.stderr}")
            raise
        
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Command timed out after {timeout}s: {cmd_str}")
            raise
        
        except FileNotFoundError as e:
            self.logger.error(f"Command not found: {cmd[0]}")
            raise
    
    def run_safe(self, cmd: List[str], **kwargs) -> Optional[subprocess.CompletedProcess]:
        """Run command without raising exceptions."""
        try:
            return self.run(cmd, check=False, **kwargs)
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            return None
    
    def run_streaming(
        self, 
        cmd: List[str], 
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """Run command with real-time output streaming."""
        
        cmd_str = ' '.join(cmd)
        self.logger.debug(f"Running streaming command: {cmd_str}")
        
        try:
            # Use subprocess.Popen for real-time output
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Stream output in real-time
            output_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())  # Print to terminal immediately
                    output_lines.append(output.strip())
            
            # Wait for process to complete
            return_code = process.wait(timeout=timeout)
            
            # Create a CompletedProcess-like object
            result = subprocess.CompletedProcess(
                cmd, return_code, 
                stdout='\n'.join(output_lines),
                stderr=None
            )
            
            if return_code == 0:
                self.logger.debug(f"Streaming command succeeded: {cmd_str}")
            else:
                self.logger.warning(f"Streaming command failed with code {return_code}: {cmd_str}")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            process.kill()
            self.logger.error(f"Streaming command timed out after {timeout}s: {cmd_str}")
            raise
        
        except FileNotFoundError as e:
            self.logger.error(f"Command not found: {cmd[0]}")
            raise
        
        except Exception as e:
            self.logger.error(f"Streaming command failed: {cmd_str}: {e}")
            raise


class EnvironmentValidator:
    """Validate system environment and dependencies."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or Logger.get_logger("EnvironmentValidator")
        self.runner = CommandRunner(self.logger)
    
    def check_command_available(self, command: str) -> bool:
        """Check if a command is available in PATH."""
        result = self.runner.run_safe([command, "--version"])
        return result is not None and result.returncode == 0
    
    def check_docker_available(self) -> Dict[str, Any]:
        """Check Docker availability and status."""
        status = {
            "docker_installed": False,
            "docker_running": False,
            "buildx_available": False,
            "version": None,
            "error": None
        }
        
        try:
            # Check Docker installation
            result = self.runner.run_safe(["docker", "--version"])
            if result and result.returncode == 0:
                status["docker_installed"] = True
                status["version"] = result.stdout.strip()
            
            # Check Docker daemon
            result = self.runner.run_safe(["docker", "info"])
            if result and result.returncode == 0:
                status["docker_running"] = True
            
            # Check buildx
            result = self.runner.run_safe(["docker", "buildx", "version"])
            if result and result.returncode == 0:
                status["buildx_available"] = True
                
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def check_python_version(self, min_version: str = "3.8") -> bool:
        """Check if Python version meets minimum requirements."""
        import sys
        from packaging import version
        
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        return version.parse(current) >= version.parse(min_version)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def get_git_commit() -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat() 