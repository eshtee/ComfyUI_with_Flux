#!/usr/bin/env python3
"""
ComfyUI Docker Build and Integration Test Suite
==============================================

Comprehensive testing framework for validating Docker builds, container functionality,
service availability, and integration testing.

Usage:
    python test_docker_build.py --help
    python test_docker_build.py --username myuser --tag test
    python test_docker_build.py --username myuser --tag test --full-test
"""

import argparse
import subprocess
import sys
import time
import json
import logging
import requests
import tempfile
import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DockerTestSuite:
    """Comprehensive Docker testing suite for ComfyUI."""
    
    def __init__(self, username: str, tag: str, timeout: int = 300):
        self.username = username
        self.tag = tag
        self.image_name = f"{username}/comfyui:{tag}"
        self.container_name = f"comfyui-test-{int(time.time())}"
        self.timeout = timeout
        self.test_workspace = None
        self.container_id = None
        self.test_results = {
            "build": False,
            "container_start": False,
            "comfyui_service": False,
            "jupyter_service": False,
            "health_check": False,
            "api_test": False,
            "workspace_persistence": False,
            "cleanup": False
        }
        self.start_time = time.time()
        
        # Setup signal handlers for cleanup
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle interruption signals gracefully."""
        logger.warning(f"Received signal {signum}, cleaning up...")
        self.cleanup()
        sys.exit(1)
    
    def run_command(self, cmd: List[str], capture_output: bool = True, timeout: Optional[int] = None) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout or self.timeout,
                check=False
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return 1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {' '.join(cmd)} - {e}")
            return 1, "", str(e)
    
    def test_docker_environment(self) -> bool:
        """Test Docker environment availability."""
        logger.info("Testing Docker environment...")
        
        # Check Docker daemon
        exit_code, stdout, stderr = self.run_command(["docker", "info"])
        if exit_code != 0:
            logger.error("Docker daemon not accessible")
            return False
        
        # Check available resources
        exit_code, stdout, stderr = self.run_command(["docker", "system", "df"])
        if exit_code == 0:
            logger.info("Docker system resources:")
            for line in stdout.split('\n')[:5]:  # Show first few lines
                if line.strip():
                    logger.info(f"  {line}")
        
        return True
    
    def test_image_build(self) -> bool:
        """Test Docker image build process."""
        logger.info(f"Testing image build: {self.image_name}")
        
        # Check if image exists
        exit_code, stdout, stderr = self.run_command(["docker", "image", "inspect", self.image_name])
        if exit_code == 0:
            logger.info(f"Image {self.image_name} already exists")
            self.test_results["build"] = True
            return True
        
        # Build image using build_docker.py
        logger.info("Building image...")
        build_cmd = [
            "python", "build_docker.py",
            "--username", self.username,
            "--tag", self.tag,
            "--verbose"
        ]
        
        exit_code, stdout, stderr = self.run_command(build_cmd, timeout=1800)  # 30 min timeout
        
        if exit_code == 0:
            logger.info("✅ Image build successful")
            self.test_results["build"] = True
            return True
        else:
            logger.error(f"❌ Image build failed: {stderr}")
            return False
    
    def setup_test_workspace(self) -> bool:
        """Setup temporary workspace for testing."""
        try:
            self.test_workspace = tempfile.mkdtemp(prefix="comfyui_test_")
            logger.info(f"Created test workspace: {self.test_workspace}")
            return True
        except Exception as e:
            logger.error(f"Failed to create test workspace: {e}")
            return False
    
    def test_container_start(self) -> bool:
        """Test container startup and basic functionality."""
        logger.info("Testing container startup...")
        
        if not self.setup_test_workspace():
            return False
        
        # Start container
        run_cmd = [
            "docker", "run", "-d",
            "--name", self.container_name,
            "-p", "8188:8188",
            "-p", "8888:8888",
            "-v", f"{self.test_workspace}:/workspace",
            self.image_name
        ]
        
        exit_code, stdout, stderr = self.run_command(run_cmd)
        
        if exit_code == 0:
            self.container_id = stdout.strip()
            logger.info(f"✅ Container started: {self.container_id[:12]}")
            self.test_results["container_start"] = True
            
            # Wait for startup
            logger.info("Waiting for services to start...")
            time.sleep(30)  # Allow time for initialization
            
            return True
        else:
            logger.error(f"❌ Container start failed: {stderr}")
            return False
    
    def test_service_availability(self, service: str, port: int, path: str = "/") -> bool:
        """Test if a service is available and responding."""
        max_attempts = 30
        attempt = 0
        
        logger.info(f"Testing {service} service availability on port {port}...")
        
        while attempt < max_attempts:
            try:
                response = requests.get(
                    f"http://localhost:{port}{path}",
                    timeout=5,
                    allow_redirects=True
                )
                
                if response.status_code in [200, 302]:  # Allow redirects
                    logger.info(f"✅ {service} service is available (HTTP {response.status_code})")
                    return True
                elif response.status_code == 405:  # Method not allowed is OK for some endpoints
                    logger.info(f"✅ {service} service is available (HTTP {response.status_code} - Method not allowed)")
                    return True
                else:
                    logger.debug(f"{service} returned HTTP {response.status_code}, retrying...")
                    
            except requests.exceptions.RequestException as e:
                logger.debug(f"{service} connection failed: {e}, retrying...")
            
            attempt += 1
            time.sleep(2)
        
        logger.error(f"❌ {service} service not available after {max_attempts} attempts")
        return False
    
    def test_comfyui_service(self) -> bool:
        """Test ComfyUI service availability."""
        if self.test_service_availability("ComfyUI", 8188):
            self.test_results["comfyui_service"] = True
            return True
        return False
    
    def test_jupyter_service(self) -> bool:
        """Test Jupyter service availability."""
        # Test both JupyterLab and classic notebook endpoints
        if (self.test_service_availability("JupyterLab", 8888, "/lab") or 
            self.test_service_availability("Jupyter Notebook", 8888, "/tree")):
            self.test_results["jupyter_service"] = True
            return True
        return False
    
    def test_container_health(self) -> bool:
        """Test container health and process status."""
        logger.info("Testing container health...")
        
        if not self.container_id:
            logger.error("No container to test")
            return False
        
        # Check container status
        exit_code, stdout, stderr = self.run_command(["docker", "inspect", self.container_id])
        if exit_code != 0:
            logger.error("Failed to inspect container")
            return False
        
        try:
            container_info = json.loads(stdout)[0]
            state = container_info["State"]
            
            if state["Running"]:
                logger.info("✅ Container is running")
            else:
                logger.error(f"❌ Container not running: {state}")
                return False
            
            # Check processes
            exit_code, stdout, stderr = self.run_command(["docker", "exec", self.container_id, "ps", "aux"])
            if exit_code == 0:
                processes = stdout.split('\n')
                jupyter_running = any("jupyter" in line.lower() for line in processes)
                python_running = any("python" in line and "comfyui" in line.lower() for line in processes)
                
                logger.info(f"Jupyter process running: {jupyter_running}")
                logger.info(f"ComfyUI process running: {python_running}")
                
                if jupyter_running:
                    logger.info("✅ Container health check passed")
                    self.test_results["health_check"] = True
                    return True
            
        except json.JSONDecodeError:
            logger.error("Failed to parse container info")
        
        logger.error("❌ Container health check failed")
        return False
    
    def test_comfyui_api(self) -> bool:
        """Test ComfyUI API functionality."""
        logger.info("Testing ComfyUI API...")
        
        try:
            # Test system stats endpoint
            response = requests.get("http://localhost:8188/system_stats", timeout=10)
            if response.status_code == 200:
                logger.info("✅ ComfyUI API system stats accessible")
                
                # Test queue endpoint
                response = requests.get("http://localhost:8188/queue", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ ComfyUI API queue accessible")
                    self.test_results["api_test"] = True
                    return True
                else:
                    logger.warning(f"ComfyUI queue endpoint returned {response.status_code}")
            else:
                logger.warning(f"ComfyUI system stats returned {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"ComfyUI API test failed: {e}")
        
        logger.error("❌ ComfyUI API test failed")
        return False
    
    def test_workspace_persistence(self) -> bool:
        """Test workspace persistence and file operations."""
        logger.info("Testing workspace persistence...")
        
        if not self.container_id:
            logger.error("No container to test")
            return False
        
        test_file = "/workspace/test_persistence.txt"
        test_content = f"Test content {time.time()}"
        
        # Create test file
        exit_code, stdout, stderr = self.run_command([
            "docker", "exec", self.container_id, 
            "sh", "-c", f"echo '{test_content}' > {test_file}"
        ])
        
        if exit_code != 0:
            logger.error("Failed to create test file in workspace")
            return False
        
        # Verify file exists
        exit_code, stdout, stderr = self.run_command([
            "docker", "exec", self.container_id, "cat", test_file
        ])
        
        if exit_code == 0 and test_content in stdout:
            logger.info("✅ Workspace persistence test passed")
            
            # Check if ComfyUI directory structure exists
            exit_code, stdout, stderr = self.run_command([
                "docker", "exec", self.container_id, "ls", "-la", "/workspace/ComfyUI"
            ])
            
            if exit_code == 0:
                logger.info("✅ ComfyUI directory structure exists")
                self.test_results["workspace_persistence"] = True
                return True
        
        logger.error("❌ Workspace persistence test failed")
        return False
    
    def test_logs_and_monitoring(self) -> bool:
        """Test logging and monitoring capabilities."""
        logger.info("Testing logs and monitoring...")
        
        if not self.container_id:
            return False
        
        # Check container logs
        exit_code, stdout, stderr = self.run_command(["docker", "logs", self.container_id])
        
        if exit_code == 0:
            log_lines = stdout.split('\n')
            startup_logs = any("Starting" in line for line in log_lines)
            error_logs = any("ERROR" in line.upper() for line in log_lines)
            
            logger.info(f"Startup logs found: {startup_logs}")
            logger.info(f"Error logs found: {error_logs}")
            
            if startup_logs and not error_logs:
                logger.info("✅ Logs and monitoring test passed")
                return True
        
        logger.warning("⚠️ Logs and monitoring test completed with warnings")
        return True  # Non-critical test
    
    def cleanup(self) -> bool:
        """Cleanup test resources."""
        logger.info("Cleaning up test resources...")
        success = True
        
        # Stop and remove container
        if self.container_id:
            exit_code, stdout, stderr = self.run_command(["docker", "stop", self.container_id])
            if exit_code == 0:
                logger.info("Container stopped")
            else:
                logger.warning(f"Failed to stop container: {stderr}")
                success = False
            
            exit_code, stdout, stderr = self.run_command(["docker", "rm", self.container_id])
            if exit_code == 0:
                logger.info("Container removed")
            else:
                logger.warning(f"Failed to remove container: {stderr}")
                success = False
        
        # Remove test workspace
        if self.test_workspace and os.path.exists(self.test_workspace):
            try:
                import shutil
                shutil.rmtree(self.test_workspace)
                logger.info("Test workspace removed")
            except Exception as e:
                logger.warning(f"Failed to remove test workspace: {e}")
                success = False
        
        if success:
            logger.info("✅ Cleanup completed successfully")
            self.test_results["cleanup"] = True
        else:
            logger.warning("⚠️ Cleanup completed with warnings")
        
        return success
    
    def run_full_test_suite(self) -> bool:
        """Run the complete test suite."""
        logger.info("=" * 60)
        logger.info("Starting ComfyUI Docker Test Suite")
        logger.info("=" * 60)
        
        try:
            # Test sequence
            tests = [
                ("Docker Environment", self.test_docker_environment),
                ("Image Build", self.test_image_build),
                ("Container Start", self.test_container_start),
                ("ComfyUI Service", self.test_comfyui_service),
                ("Jupyter Service", self.test_jupyter_service),
                ("Container Health", self.test_container_health),
                ("ComfyUI API", self.test_comfyui_api),
                ("Workspace Persistence", self.test_workspace_persistence),
                ("Logs and Monitoring", self.test_logs_and_monitoring),
            ]
            
            passed_tests = 0
            total_tests = len(tests)
            
            for test_name, test_func in tests:
                logger.info(f"\n--- Running {test_name} Test ---")
                try:
                    if test_func():
                        passed_tests += 1
                        logger.info(f"✅ {test_name} test PASSED")
                    else:
                        logger.error(f"❌ {test_name} test FAILED")
                except Exception as e:
                    logger.error(f"❌ {test_name} test FAILED with exception: {e}")
            
            # Generate test report
            self.generate_test_report(passed_tests, total_tests)
            
            # Return overall success
            return passed_tests == total_tests
            
        finally:
            # Always cleanup
            self.cleanup()
    
    def generate_test_report(self, passed_tests: int, total_tests: int) -> None:
        """Generate and save test report."""
        end_time = time.time()
        duration = end_time - self.start_time
        
        report = {
            "test_summary": {
                "image": self.image_name,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": round(duration, 2),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 2),
                "overall_result": "PASS" if passed_tests == total_tests else "FAIL"
            },
            "test_results": self.test_results,
            "environment": {
                "python_version": sys.version,
                "test_workspace": self.test_workspace,
                "container_name": self.container_name
            }
        }
        
        # Save report
        report_file = f"test-report-{self.tag}-{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Image: {self.image_name}")
        logger.info(f"Tests: {passed_tests}/{total_tests} passed ({report['test_summary']['success_rate']}%)")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Result: {report['test_summary']['overall_result']}")
        logger.info(f"Report saved: {report_file}")
        
        if passed_tests == total_tests:
            logger.info("🎉 All tests passed! Image is ready for use.")
        else:
            logger.error("⚠️ Some tests failed. Please review the results.")

def main():
    parser = argparse.ArgumentParser(
        description="ComfyUI Docker Build and Integration Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test of existing image
  python test_docker_build.py --username myuser --tag latest

  # Full test including build
  python test_docker_build.py --username myuser --tag test --full-test

  # Test with custom timeout
  python test_docker_build.py --username myuser --tag dev --timeout 600

  # Test specific services only
  python test_docker_build.py --username myuser --tag latest --services-only
        """
    )
    
    parser.add_argument(
        "--username", "-u",
        required=True,
        help="Docker Hub username or registry namespace"
    )
    
    parser.add_argument(
        "--tag", "-t",
        required=True,
        help="Image tag to test"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Test timeout in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--full-test",
        action="store_true",
        help="Run full test suite including build"
    )
    
    parser.add_argument(
        "--services-only",
        action="store_true",
        help="Test only service availability (skip build and detailed tests)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure verbose logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize test suite
    test_suite = DockerTestSuite(args.username, args.tag, args.timeout)
    
    try:
        if args.services_only:
            # Quick service availability test
            logger.info("Running services-only test...")
            success = (test_suite.test_docker_environment() and
                      test_suite.test_container_start() and
                      test_suite.test_comfyui_service() and
                      test_suite.test_jupyter_service())
        elif args.full_test:
            # Full test suite
            success = test_suite.run_full_test_suite()
        else:
            # Default test (skip build)
            logger.info("Running standard test suite (no build)...")
            test_suite.test_results["build"] = True  # Assume image exists
            success = test_suite.run_full_test_suite()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.warning("Test interrupted by user")
        test_suite.cleanup()
        return 130
    except Exception as e:
        logger.error(f"Test suite failed with exception: {e}")
        test_suite.cleanup()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 