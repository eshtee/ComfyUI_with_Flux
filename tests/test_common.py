"""
Unit tests for lib.common module.
"""

import unittest
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.common import (
    Logger, PathValidator, CommandRunner, EnvironmentValidator,
    format_size, format_duration, get_git_commit, get_timestamp
)


class TestLogger(unittest.TestCase):
    """Test Logger class."""
    
    def test_get_logger_creates_logger(self):
        """Test that get_logger creates a logger."""
        logger = Logger.get_logger("test_logger")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_logger")
    
    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns the same instance for same name."""
        logger1 = Logger.get_logger("test_logger2")
        logger2 = Logger.get_logger("test_logger2")
        self.assertIs(logger1, logger2)
    
    def test_get_logger_with_file(self):
        """Test logger with file output."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            logger = Logger.get_logger("test_file_logger", log_file=f.name)
            self.assertEqual(len(logger.handlers), 2)  # Console + File


class TestPathValidator(unittest.TestCase):
    """Test PathValidator class."""
    
    def test_ensure_dir_creates_directory(self):
        """Test that ensure_dir creates directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test_subdir"
            result = PathValidator.ensure_dir(test_path)
            self.assertTrue(result)
            self.assertTrue(test_path.exists())
    
    def test_is_valid_path_with_valid_path(self):
        """Test is_valid_path with valid path."""
        result = PathValidator.is_valid_path("/tmp")
        self.assertTrue(result)
    
    def test_is_valid_path_with_invalid_path(self):
        """Test is_valid_path with invalid path."""
        result = PathValidator.is_valid_path("\x00invalid")
        self.assertFalse(result)
    
    def test_get_size_mb_with_file(self):
        """Test get_size_mb with a file."""
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"x" * 1024)  # 1KB
            f.flush()
            size = PathValidator.get_size_mb(Path(f.name))
            self.assertAlmostEqual(size, 0.001, places=3)
    
    def test_get_size_mb_nonexistent_file(self):
        """Test get_size_mb with nonexistent file."""
        size = PathValidator.get_size_mb(Path("/nonexistent"))
        self.assertEqual(size, 0.0)
    
    def test_safe_remove_file(self):
        """Test safe_remove with file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = Path(f.name)
        
        self.assertTrue(file_path.exists())
        result = PathValidator.safe_remove(file_path)
        self.assertTrue(result)
        self.assertFalse(file_path.exists())


class TestCommandRunner(unittest.TestCase):
    """Test CommandRunner class."""
    
    def setUp(self):
        self.runner = CommandRunner()
    
    def test_run_successful_command(self):
        """Test running a successful command."""
        result = self.runner.run(["echo", "hello"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")
    
    def test_run_safe_with_failing_command(self):
        """Test run_safe with failing command."""
        result = self.runner.run_safe(["false"])
        self.assertIsNotNone(result)
        self.assertNotEqual(result.returncode, 0)
    
    @patch('subprocess.run')
    def test_run_with_timeout(self, mock_run):
        """Test run with timeout."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        self.runner.run(["sleep", "1"], timeout=5)
        
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs['timeout'], 5)


class TestEnvironmentValidator(unittest.TestCase):
    """Test EnvironmentValidator class."""
    
    def setUp(self):
        self.validator = EnvironmentValidator()
    
    def test_check_command_available_existing(self):
        """Test check_command_available with existing command."""
        result = self.validator.check_command_available("echo")
        self.assertTrue(result)
    
    def test_check_command_available_nonexistent(self):
        """Test check_command_available with non-existent command."""
        result = self.validator.check_command_available("nonexistent_command_12345")
        self.assertFalse(result)
    
    @patch('lib.common.CommandRunner.run_safe')
    def test_check_docker_available(self, mock_run_safe):
        """Test check_docker_available."""
        # Mock successful docker commands
        mock_run_safe.side_effect = [
            MagicMock(returncode=0, stdout="Docker version 20.10.0"),
            MagicMock(returncode=0, stdout=""),
            MagicMock(returncode=0, stdout="buildx version")
        ]
        
        status = self.validator.check_docker_available()
        
        self.assertTrue(status["docker_installed"])
        self.assertTrue(status["docker_running"])
        self.assertTrue(status["buildx_available"])
        self.assertIn("Docker version", status["version"])
    
    def test_check_python_version(self):
        """Test check_python_version."""
        result = self.validator.check_python_version("3.6")
        self.assertTrue(result)  # Should pass for current Python version


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_format_size(self):
        """Test format_size function."""
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1024 * 1024), "1.0 MB")
        self.assertEqual(format_size(1024 * 1024 * 1024), "1.0 GB")
    
    def test_format_duration(self):
        """Test format_duration function."""
        self.assertEqual(format_duration(30), "30.0s")
        self.assertEqual(format_duration(90), "1.5m")
        self.assertEqual(format_duration(3600), "1.0h")
    
    @patch('subprocess.run')
    def test_get_git_commit_success(self, mock_run):
        """Test get_git_commit with successful git command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123\n"
        )
        
        result = get_git_commit()
        self.assertEqual(result, "abc123")
    
    @patch('subprocess.run')
    def test_get_git_commit_failure(self, mock_run):
        """Test get_git_commit with failing git command."""
        mock_run.side_effect = FileNotFoundError()
        
        result = get_git_commit()
        self.assertIsNone(result)
    
    def test_get_timestamp(self):
        """Test get_timestamp function."""
        timestamp = get_timestamp()
        self.assertIsInstance(timestamp, str)
        self.assertIn("T", timestamp)  # ISO format contains T


if __name__ == '__main__':
    unittest.main() 