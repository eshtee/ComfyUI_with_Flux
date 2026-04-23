#!/usr/bin/env python3
"""
ComfyUI Container Health Check Script
===================================

Comprehensive health monitoring for ComfyUI containers in production.
Can be used as Docker HEALTHCHECK or standalone monitoring.

Usage:
    python health_check.py --help
    python health_check.py --check-all
    python health_check.py --service comfyui
    python health_check.py --format json
"""

import argparse
import sys
import json
import time
import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess

# Optional imports with fallbacks
try:
    import requests
except ImportError:
    print("Warning: requests module not available. HTTP checks will be disabled.")
    requests = None

try:
    import psutil
except ImportError:
    print("Warning: psutil module not available. System monitoring will be limited.")
    psutil = None

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Default to minimal logging for health checks
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class HealthChecker:
    """Comprehensive health checker for ComfyUI container."""
    
    def __init__(self, timeout: int = 10, verbose: bool = False):
        self.timeout = timeout
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.INFO)
        
        self.health_status = {
            "overall": "unknown",
            "timestamp": time.time(),
            "checks": {}
        }
    
    def check_service_http(self, service: str, url: str, expected_codes: List[int] = None) -> Dict[str, Any]:
        """Check HTTP service availability."""
        if requests is None:
            return {
                "status": "error",
                "http_code": None,
                "response_time_ms": None,
                "url": url,
                "error": "requests module not available"
            }
        
        if expected_codes is None:
            expected_codes = [200, 302, 405]  # Include common success/redirect codes
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=self.timeout, allow_redirects=True)
            response_time = time.time() - start_time
            
            status = "healthy" if response.status_code in expected_codes else "unhealthy"
            
            return {
                "status": status,
                "http_code": response.status_code,
                "response_time_ms": round(response_time * 1000, 2),
                "url": url,
                "error": None
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "status": "unhealthy",
                "http_code": None,
                "response_time_ms": None,
                "url": url,
                "error": str(e)
            }
    
    def check_comfyui(self) -> Dict[str, Any]:
        """Check ComfyUI service health."""
        logger.info("Checking ComfyUI service...")
        
        # Check main interface
        main_check = self.check_service_http("ComfyUI", "http://localhost:8188/")
        
        # Check API endpoints if main interface is healthy
        if main_check["status"] == "healthy":
            api_check = self.check_service_http(
                "ComfyUI API", 
                "http://localhost:8188/system_stats",
                [200]
            )
            
            if api_check["status"] == "healthy":
                # Try to get system stats
                try:
                    response = requests.get("http://localhost:8188/system_stats", timeout=self.timeout)
                    if response.status_code == 200:
                        stats = response.json()
                        return {
                            "status": "healthy",
                            "interface": main_check,
                            "api": api_check,
                            "system_stats": {
                                "gpu_available": stats.get("system", {}).get("cuda_available", False),
                                "memory_used": stats.get("system", {}).get("ram", {}).get("used", 0),
                                "memory_total": stats.get("system", {}).get("ram", {}).get("total", 0)
                            }
                        }
                except Exception as e:
                    logger.warning(f"Failed to get system stats: {e}")
            
            return {
                "status": "healthy" if main_check["status"] == "healthy" else "unhealthy",
                "interface": main_check,
                "api": api_check
            }
        
        return {
            "status": "unhealthy",
            "interface": main_check
        }
    
    def check_jupyter(self) -> Dict[str, Any]:
        """Check Jupyter service health."""
        logger.info("Checking Jupyter service...")
        
        # Check JupyterLab first, then fall back to classic notebook
        lab_check = self.check_service_http("JupyterLab", "http://localhost:8888/lab")
        
        if lab_check["status"] == "healthy":
            return {
                "status": "healthy",
                "interface": "jupyterlab",
                "check": lab_check
            }
        
        # Try classic notebook interface
        notebook_check = self.check_service_http("Jupyter Notebook", "http://localhost:8888/tree")
        
        return {
            "status": notebook_check["status"],
            "interface": "notebook" if notebook_check["status"] == "healthy" else "none",
            "lab_check": lab_check,
            "notebook_check": notebook_check
        }
    
    def check_processes(self) -> Dict[str, Any]:
        """Check required processes are running."""
        logger.info("Checking running processes...")
        
        if psutil is None:
            # Fallback to basic ps command
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    processes = result.stdout
                    jupyter_running = 'jupyter' in processes.lower()
                    comfyui_running = 'comfyui' in processes.lower() and 'python' in processes.lower()
                    
                    return {
                        "status": "healthy" if jupyter_running and comfyui_running else "unhealthy",
                        "required_processes": {
                            "jupyter": jupyter_running,
                            "comfyui": comfyui_running
                        },
                        "method": "ps_command",
                        "missing_processes": [
                            name for name, running in {
                                "jupyter": jupyter_running,
                                "comfyui": comfyui_running
                            }.items() if not running
                        ]
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"psutil not available and ps command failed: {e}"
                }
        
        required_processes = {
            "jupyter": False,
            "comfyui": False
        }
        
        process_details = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    
                    if 'jupyter' in cmdline.lower():
                        required_processes["jupyter"] = True
                        process_details.append({
                            "name": "jupyter",
                            "pid": proc.info['pid'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent']
                        })
                    
                    if 'comfyui' in cmdline.lower() and 'python' in cmdline.lower():
                        required_processes["comfyui"] = True
                        process_details.append({
                            "name": "comfyui",
                            "pid": proc.info['pid'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent']
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
        
        all_running = all(required_processes.values())
        
        return {
            "status": "healthy" if all_running else "unhealthy",
            "required_processes": required_processes,
            "process_details": process_details,
            "missing_processes": [name for name, running in required_processes.items() if not running]
        }
    
    def check_disk_space(self, threshold_percent: float = 90.0) -> Dict[str, Any]:
        """Check disk space availability."""
        logger.info("Checking disk space...")
        
        if psutil is None:
            # Fallback to df command
            try:
                result = subprocess.run(['df', '-h', '/workspace', '/'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    disk_info = {}
                    
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 6:
                            mount_point = parts[-1]
                            used_percent = float(parts[4].rstrip('%'))
                            
                            if mount_point == '/workspace':
                                disk_info['workspace'] = {"used_percent": used_percent}
                            elif mount_point == '/':
                                disk_info['root'] = {"used_percent": used_percent}
                    
                    max_usage = max(disk_info.get('workspace', {}).get('used_percent', 0),
                                  disk_info.get('root', {}).get('used_percent', 0))
                    
                    status = "healthy"
                    if max_usage > threshold_percent:
                        status = "warning" if max_usage < 95.0 else "critical"
                    
                    return {
                        "status": status,
                        "method": "df_command",
                        **disk_info,
                        "threshold_percent": threshold_percent
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"psutil not available and df command failed: {e}"
                }
        
        try:
            # Check workspace directory
            workspace_usage = psutil.disk_usage('/workspace')
            workspace_percent = (workspace_usage.used / workspace_usage.total) * 100
            
            # Check root filesystem
            root_usage = psutil.disk_usage('/')
            root_percent = (root_usage.used / root_usage.total) * 100
            
            status = "healthy"
            if workspace_percent > threshold_percent or root_percent > threshold_percent:
                status = "warning" if max(workspace_percent, root_percent) < 95.0 else "critical"
            
            return {
                "status": status,
                "workspace": {
                    "used_percent": round(workspace_percent, 2),
                    "used_gb": round(workspace_usage.used / (1024**3), 2),
                    "total_gb": round(workspace_usage.total / (1024**3), 2)
                },
                "root": {
                    "used_percent": round(root_percent, 2),
                    "used_gb": round(root_usage.used / (1024**3), 2),
                    "total_gb": round(root_usage.total / (1024**3), 2)
                },
                "threshold_percent": threshold_percent
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_memory(self, threshold_percent: float = 90.0) -> Dict[str, Any]:
        """Check memory usage."""
        logger.info("Checking memory usage...")
        
        if psutil is None:
            # Fallback to free command
            try:
                result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) >= 2:
                        mem_line = lines[1].split()
                        if len(mem_line) >= 3:
                            total_mb = float(mem_line[1])
                            used_mb = float(mem_line[2])
                            used_percent = (used_mb / total_mb) * 100
                            
                            status = "healthy"
                            if used_percent > threshold_percent:
                                status = "warning" if used_percent < 95.0 else "critical"
                            
                            return {
                                "status": status,
                                "used_percent": round(used_percent, 2),
                                "used_gb": round(used_mb / 1024, 2),
                                "total_gb": round(total_mb / 1024, 2),
                                "method": "free_command",
                                "threshold_percent": threshold_percent
                            }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"psutil not available and free command failed: {e}"
                }
        
        try:
            memory = psutil.virtual_memory()
            
            status = "healthy"
            if memory.percent > threshold_percent:
                status = "warning" if memory.percent < 95.0 else "critical"
            
            return {
                "status": status,
                "used_percent": memory.percent,
                "used_gb": round(memory.used / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "threshold_percent": threshold_percent
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_file_permissions(self) -> Dict[str, Any]:
        """Check critical file permissions."""
        logger.info("Checking file permissions...")
        
        critical_paths = [
            "/workspace",
            "/workspace/ComfyUI",
            "/workspace/jupyter.log"
        ]
        
        permission_issues = []
        
        for path in critical_paths:
            try:
                path_obj = Path(path)
                if path_obj.exists():
                    # Check if writable
                    if not os.access(path, os.W_OK):
                        permission_issues.append(f"Not writable: {path}")
                    
                    # Check if readable
                    if not os.access(path, os.R_OK):
                        permission_issues.append(f"Not readable: {path}")
                elif path == "/workspace":  # Workspace must exist
                    permission_issues.append(f"Missing critical path: {path}")
                    
            except Exception as e:
                permission_issues.append(f"Error checking {path}: {e}")
        
        return {
            "status": "healthy" if not permission_issues else "unhealthy",
            "issues": permission_issues,
            "checked_paths": critical_paths
        }
    
    def run_comprehensive_check(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        logger.info("Running comprehensive health check...")
        
        # Run all checks
        checks = {
            "comfyui": self.check_comfyui(),
            "jupyter": self.check_jupyter(),
            "processes": self.check_processes(),
            "disk_space": self.check_disk_space(),
            "memory": self.check_memory(),
            "file_permissions": self.check_file_permissions()
        }
        
        # Determine overall status
        critical_checks = ["comfyui", "jupyter", "processes"]
        warning_checks = ["disk_space", "memory", "file_permissions"]
        
        overall_status = "healthy"
        
        # Check critical services
        for check_name in critical_checks:
            if checks[check_name]["status"] in ["unhealthy", "error"]:
                overall_status = "unhealthy"
                break
        
        # Check warning services (only downgrade if still healthy)
        if overall_status == "healthy":
            for check_name in warning_checks:
                if checks[check_name]["status"] in ["warning", "critical", "error"]:
                    overall_status = "warning"
                    break
        
        self.health_status = {
            "overall": overall_status,
            "timestamp": time.time(),
            "checks": checks
        }
        
        return self.health_status
    
    def format_output(self, format_type: str = "text") -> str:
        """Format health check output."""
        if format_type == "json":
            return json.dumps(self.health_status, indent=2)
        
        elif format_type == "text":
            output = []
            output.append(f"Overall Status: {self.health_status['overall'].upper()}")
            output.append(f"Timestamp: {time.ctime(self.health_status['timestamp'])}")
            output.append("")
            
            for check_name, check_result in self.health_status['checks'].items():
                status = check_result.get('status', 'unknown')
                output.append(f"{check_name.replace('_', ' ').title()}: {status.upper()}")
                
                if self.verbose and status != "healthy":
                    if 'error' in check_result:
                        output.append(f"  Error: {check_result['error']}")
                    if 'issues' in check_result:
                        for issue in check_result['issues']:
                            output.append(f"  Issue: {issue}")
            
            return "\n".join(output)
        
        elif format_type == "prometheus":
            # Prometheus metrics format
            metrics = []
            
            # Overall health (1 = healthy, 0 = unhealthy)
            overall_value = 1 if self.health_status['overall'] in ['healthy', 'warning'] else 0
            metrics.append(f'comfyui_health_overall {overall_value}')
            
            # Individual check metrics
            for check_name, check_result in self.health_status['checks'].items():
                status = check_result.get('status', 'unknown')
                value = 1 if status in ['healthy', 'warning'] else 0
                metrics.append(f'comfyui_health_{check_name} {value}')
                
                # Add specific metrics
                if check_name == "memory" and "used_percent" in check_result:
                    metrics.append(f'comfyui_memory_usage_percent {check_result["used_percent"]}')
                
                if check_name == "disk_space":
                    if "workspace" in check_result:
                        metrics.append(f'comfyui_disk_usage_workspace_percent {check_result["workspace"]["used_percent"]}')
                    if "root" in check_result:
                        metrics.append(f'comfyui_disk_usage_root_percent {check_result["root"]["used_percent"]}')
            
            return "\n".join(metrics)
        
        else:
            return json.dumps(self.health_status, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="ComfyUI Container Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all checks with text output
  python health_check.py --check-all

  # Check specific service
  python health_check.py --service comfyui

  # Output in JSON format
  python health_check.py --check-all --format json

  # Use as Docker health check
  python health_check.py --check-all --quiet

  # Generate Prometheus metrics
  python health_check.py --check-all --format prometheus
        """
    )
    
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Run comprehensive health check"
    )
    
    parser.add_argument(
        "--service",
        choices=["comfyui", "jupyter", "processes", "disk", "memory", "permissions"],
        help="Check specific service only"
    )
    
    parser.add_argument(
        "--format",
        choices=["text", "json", "prometheus"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds (default: 10)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except errors"
    )
    
    args = parser.parse_args()
    
    # Configure logging based on flags
    if args.quiet:
        logger.setLevel(logging.ERROR)
    elif args.verbose:
        logger.setLevel(logging.INFO)
    
    # Initialize health checker
    health_checker = HealthChecker(timeout=args.timeout, verbose=args.verbose)
    
    try:
        if args.check_all:
            # Run comprehensive check
            health_status = health_checker.run_comprehensive_check()
            
        elif args.service:
            # Run specific service check
            if args.service == "comfyui":
                result = health_checker.check_comfyui()
            elif args.service == "jupyter":
                result = health_checker.check_jupyter()
            elif args.service == "processes":
                result = health_checker.check_processes()
            elif args.service == "disk":
                result = health_checker.check_disk_space()
            elif args.service == "memory":
                result = health_checker.check_memory()
            elif args.service == "permissions":
                result = health_checker.check_file_permissions()
            
            health_checker.health_status = {
                "overall": result["status"],
                "timestamp": time.time(),
                "checks": {args.service: result}
            }
            
        else:
            parser.print_help()
            return 1
        
        # Output results
        if not args.quiet:
            output = health_checker.format_output(args.format)
            print(output)
        
        # Return appropriate exit code
        overall_status = health_checker.health_status["overall"]
        if overall_status == "healthy":
            return 0
        elif overall_status == "warning":
            return 0  # Warning is still considered success for health checks
        else:
            return 1  # Unhealthy or error
            
    except KeyboardInterrupt:
        logger.error("Health check interrupted")
        return 130
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 1

if __name__ == "__main__":
    import os
    sys.exit(main()) 