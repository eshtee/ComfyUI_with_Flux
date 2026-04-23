#!/usr/bin/env python3
"""
Tests for dependency download functionality.
"""

import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.dependency_manager import DependencyManager
from lib.common import Logger


class TestDependencyDownloads(unittest.TestCase):
    """Test dependency download functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test dependencies file
        self.deps_file = self.temp_path / 'test_dependencies.yaml'
        self.create_test_dependencies_file()
        
        # Create dependency manager
        self.logger = Logger.get_logger("TestDependencyDownloads")
        self.dep_manager = DependencyManager(str(self.deps_file), self.logger)
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def create_test_dependencies_file(self):
        """Create a test dependencies YAML file."""
        deps_content = f"""
presets:
  minimal:
    description: "Minimal dependencies for testing"
    includes:
      - core:
          - test_git_repo
      - essential_models:
          - test_model_file

download_config:
  max_concurrent: 1
  retry_attempts: 2
  timeout_seconds: 30

core:
  test_git_repo:
    type: git
    url: https://github.com/octocat/Hello-World.git
    destination: {self.temp_dir}/test_git_repo
    description: Test git repository
    priority: high
    size_mb: 1

essential_models:
  test_model_file:
    type: file
    url: https://httpbin.org/bytes/1024
    destination: {self.temp_dir}/test_model.bin
    description: Test model file
    priority: medium
    size_mb: 1
"""
        
        with open(self.deps_file, 'w') as f:
            f.write(deps_content)
    
    def test_load_dependencies_for_download(self):
        """Test loading dependencies for download."""
        success = self.dep_manager.load_dependencies(preset='minimal')
        self.assertTrue(success)
        self.assertEqual(len(self.dep_manager.dependencies), 2)
        
        # Check git dependency
        git_dep = next((d for d in self.dep_manager.dependencies if d['type'] == 'git'), None)
        self.assertIsNotNone(git_dep)
        self.assertEqual(git_dep['url'], 'https://github.com/octocat/Hello-World.git')
        
        # Check file dependency
        file_dep = next((d for d in self.dep_manager.dependencies if d['type'] == 'file'), None)
        self.assertIsNotNone(file_dep)
        self.assertEqual(file_dep['url'], 'https://httpbin.org/bytes/1024')
    
    @patch('subprocess.run')
    def test_download_git_dependency_mock(self, mock_subprocess):
        """Test git dependency download with mocking."""
        # Mock successful git clone
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        self.dep_manager.load_dependencies(preset='minimal')
        
        # Test download
        success = self.dep_manager.download_dependencies()
        self.assertTrue(success)
    
    def test_check_missing_dependencies(self):
        """Test checking for missing dependencies."""
        self.dep_manager.load_dependencies(preset='minimal')
        
        # All should be missing initially
        summary = self.dep_manager.check_all_dependencies()
        self.assertEqual(summary['missing'], 2)
        self.assertEqual(summary['existing'], 0)


if __name__ == '__main__':
    unittest.main() 