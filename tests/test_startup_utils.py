"""
Unit tests for lib.startup_utils module.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.startup_utils import (
    AuthenticationManager, ServiceManager, SetupManager, CleanupManager
)


class TestAuthenticationManager(unittest.TestCase):
    """Test AuthenticationManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.auth_manager = AuthenticationManager()
    
    def test_validate_huggingface_token_valid(self):
        """Test HuggingFace token validation with valid token."""
        valid_token = "hf_" + "A" * 34
        self.assertTrue(self.auth_manager.validate_huggingface_token(valid_token))
    
    def test_validate_huggingface_token_invalid(self):
        """Test HuggingFace token validation with invalid token."""
        invalid_tokens = [
            "invalid_token",
            "hf_short",
            "wrong_prefix_" + "A" * 34,
            ""
        ]
        for token in invalid_tokens:
            self.assertFalse(self.auth_manager.validate_huggingface_token(token))
    
    def test_validate_civitai_token_valid(self):
        """Test CivitAI token validation with valid token."""
        valid_token = "a" * 32
        self.assertTrue(self.auth_manager.validate_civitai_token(valid_token))
    
    def test_validate_civitai_token_invalid(self):
        """Test CivitAI token validation with invalid token."""
        invalid_tokens = [
            "short",
            "g" * 32,  # Contains invalid character
            "A" * 31,  # Too short
            "A" * 33,  # Too long
            ""
        ]
        for token in invalid_tokens:
            self.assertFalse(self.auth_manager.validate_civitai_token(token))
    
    @patch.dict(os.environ, {}, clear=True)
    def test_setup_huggingface_auth_no_token(self):
        """Test HuggingFace auth setup with no token."""
        result = self.auth_manager.setup_huggingface_auth("")
        self.assertTrue(result)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_setup_civitai_auth_no_token(self):
        """Test CivitAI auth setup with no token."""
        result = self.auth_manager.setup_civitai_auth("")
        self.assertTrue(result)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_setup_model_authentication(self):
        """Test complete model authentication setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.auth_manager.setup_model_authentication(
                model_cache_dir=temp_dir
            )
            self.assertTrue(result)
            self.assertTrue(Path(temp_dir).exists())


class TestServiceManager(unittest.TestCase):
    """Test ServiceManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.service_manager = ServiceManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('lib.startup_utils.subprocess.Popen')
    def test_start_jupyter_success(self, mock_popen):
        """Test successful JupyterLab startup."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = self.service_manager.start_jupyter(port=8888)
        self.assertTrue(result)
        mock_popen.assert_called_once()
    
    @patch('lib.startup_utils.subprocess.Popen')
    def test_start_jupyter_failure(self, mock_popen):
        """Test JupyterLab startup failure."""
        mock_popen.side_effect = Exception("Failed to start")
        
        result = self.service_manager.start_jupyter(port=8888)
        self.assertFalse(result)
    
    def test_start_flux_train_ui_no_directory(self):
        """Test Flux Train UI startup when directory doesn't exist."""
        result = self.service_manager.start_flux_train_ui()
        self.assertTrue(result)  # Should succeed (skip) when directory doesn't exist
    
    def test_start_comfyui_no_directory(self):
        """Test ComfyUI startup when directory doesn't exist."""
        result = self.service_manager.start_comfyui()
        self.assertFalse(result)  # Should fail when ComfyUI directory doesn't exist


class TestSetupManager(unittest.TestCase):
    """Test SetupManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.setup_manager = SetupManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_workflows_no_source(self):
        """Test workflow setup when source directory doesn't exist."""
        result = self.setup_manager.setup_workflows()
        self.assertTrue(result)  # Should succeed when no source workflows
    
    @patch('lib.startup_utils.Path')
    def test_setup_workflows_with_files(self, mock_path_class):
        """Test workflow setup with existing files."""
        # Create ComfyUI directory structure in temp dir
        comfyui_dir = Path(self.temp_dir) / 'ComfyUI' / 'user' / 'default' / 'workflows'
        comfyui_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock source directory and files
        source_dir = Path(self.temp_dir) / 'opt' / 'app' / 'workflows'
        source_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock workflow files
        workflow1 = source_dir / 'workflow1.json'
        workflow2 = source_dir / 'workflow2.json'
        workflow1.write_text('{"test": "workflow1"}')
        workflow2.write_text('{"test": "workflow2"}')
        
        # Configure mock to return our source directory when '/opt/app/workflows' is requested
        def mock_path_side_effect(path_str):
            if str(path_str) == '/opt/app/workflows':
                return source_dir
            else:
                return Path(path_str)
        
        mock_path_class.side_effect = mock_path_side_effect
        
        # Mock the workspace path to return our temp directory
        original_workspace = self.setup_manager.workspace
        self.setup_manager.workspace = Path(self.temp_dir)
        
        try:
            result = self.setup_manager.setup_workflows()
            self.assertTrue(result)
            
            # Verify files were copied
            copied_file1 = comfyui_dir / 'workflow1.json'
            copied_file2 = comfyui_dir / 'workflow2.json'
            self.assertTrue(copied_file1.exists())
            self.assertTrue(copied_file2.exists())
        finally:
            # Restore original workspace
            self.setup_manager.workspace = original_workspace
    
    def test_marker_file_creation(self):
        """Test marker file creation."""
        self.assertFalse(self.setup_manager.marker_file.exists())
        
        # Simulate first run
        self.setup_manager.marker_file.touch()
        self.assertTrue(self.setup_manager.marker_file.exists())


class TestCleanupManager(unittest.TestCase):
    """Test CleanupManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cleanup_manager = CleanupManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cleanup_workspace(self):
        """Test workspace cleanup."""
        # Create some test files
        test_file = Path(self.temp_dir) / 'test.tmp'
        test_file.touch()
        
        result = self.cleanup_manager.cleanup_workspace()
        self.assertTrue(result)
    
    def test_cleanup_build_artifacts(self):
        """Test build artifacts cleanup."""
        # Create some test files
        pyc_file = Path(self.temp_dir) / 'test.pyc'
        pyc_file.touch()
        
        result = self.cleanup_manager.cleanup_build_artifacts()
        self.assertTrue(result)
        self.assertFalse(pyc_file.exists())
    
    def test_cleanup_logs(self):
        """Test log file management."""
        # Create a large log file
        log_file = Path(self.temp_dir) / 'test.log'
        with open(log_file, 'w') as f:
            for i in range(2000):
                f.write(f"Log line {i}\n")
        
        result = self.cleanup_manager.cleanup_logs()
        self.assertTrue(result)
    
    def test_cleanup_aggressive(self):
        """Test aggressive cleanup."""
        # Create some test files that should be removed
        readme_file = Path(self.temp_dir) / 'README.md'
        readme_file.touch()
        
        result = self.cleanup_manager.cleanup_aggressive()
        self.assertTrue(result)
        self.assertFalse(readme_file.exists())
    
    def test_perform_startup_cleanup_disabled(self):
        """Test cleanup when disabled."""
        result = self.cleanup_manager.perform_startup_cleanup(enable_cleanup=False)
        self.assertTrue(result)
    
    def test_perform_startup_cleanup_enabled(self):
        """Test cleanup when enabled."""
        result = self.cleanup_manager.perform_startup_cleanup(enable_cleanup=True)
        self.assertTrue(result)
    
    def test_perform_startup_cleanup_aggressive(self):
        """Test aggressive cleanup mode."""
        result = self.cleanup_manager.perform_startup_cleanup(
            enable_cleanup=True, aggressive=True
        )
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main() 