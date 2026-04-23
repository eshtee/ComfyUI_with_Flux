"""
Unit tests for the simplified build script.
"""

import unittest
import tempfile
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.build_docker import SimplifiedBuildScript, create_parser


class TestSimplifiedBuildScript(unittest.TestCase):
    """Test SimplifiedBuildScript class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.script = SimplifiedBuildScript()
    
    def test_init(self):
        """Test script initialization."""
        self.assertIsNotNone(self.script.logger)
        self.assertIsNotNone(self.script.start_time)
        self.assertIn("basic", self.script.presets)
        self.assertIn("cpu", self.script.presets)
        self.assertIn("runpod", self.script.presets)
    
    def test_presets_structure(self):
        """Test preset structure."""
        for preset_name, preset in self.script.presets.items():
            self.assertIn("torch_variant", preset)
            self.assertIn("platforms", preset)
            self.assertIn("description", preset)
            self.assertIsInstance(preset["platforms"], list)
            self.assertGreater(len(preset["platforms"]), 0)
    
    @patch('scripts.build_docker.DependencyManager')
    def test_check_dependencies_success(self, mock_dep_manager):
        """Test successful dependency checking."""
        # Mock dependency manager
        mock_manager = MagicMock()
        mock_manager.check_all_dependencies.return_value = {"success": True}
        mock_manager.validate_dependency_structure.return_value = []
        mock_dep_manager.return_value = mock_manager
        
        result = self.script.check_dependencies()
        self.assertTrue(result)
        mock_manager.check_all_dependencies.assert_called_once()
        mock_manager.validate_dependency_structure.assert_called_once()
    
    @patch('scripts.build_docker.DependencyManager')
    def test_check_dependencies_failure(self, mock_dep_manager):
        """Test dependency checking failure."""
        # Mock dependency manager failure
        mock_manager = MagicMock()
        mock_manager.check_all_dependencies.return_value = {"success": False}
        mock_dep_manager.return_value = mock_manager
        
        result = self.script.check_dependencies()
        self.assertFalse(result)
    
    @patch('scripts.build_docker.DependencyManager')
    def test_check_dependencies_with_errors(self, mock_dep_manager):
        """Test dependency checking with validation errors."""
        # Mock dependency manager with errors
        mock_manager = MagicMock()
        mock_manager.check_all_dependencies.return_value = {"success": True}
        mock_manager.validate_dependency_structure.return_value = [
            "Error 1", "Error 2", "Error 3", "Error 4"
        ]
        mock_dep_manager.return_value = mock_manager
        
        result = self.script.check_dependencies()
        self.assertTrue(result)  # Should still succeed, just warn
    
    def test_generate_image_name_basic(self):
        """Test image name generation for basic build."""
        args = argparse.Namespace(
            username="testuser",
            image_name="test-image",
            tag="v1.0",
            runpod=False,
            torch_variant="cu121"
        )
        
        image_name = self.script._generate_image_name(args)
        self.assertEqual(image_name, "testuser/test-image:v1.0")
    
    def test_generate_image_name_cpu(self):
        """Test image name generation for CPU build."""
        args = argparse.Namespace(
            username="testuser",
            image_name="test-image",
            tag="latest",
            runpod=False,
            torch_variant="cpu"
        )
        
        image_name = self.script._generate_image_name(args)
        self.assertEqual(image_name, "testuser/test-image:latest-cpu")
    
    def test_generate_image_name_runpod(self):
        """Test image name generation for RunPod build."""
        args = argparse.Namespace(
            username="testuser",
            image_name="test-image",
            tag="latest",
            runpod=True,
            torch_variant="cu121"
        )
        
        image_name = self.script._generate_image_name(args)
        self.assertEqual(image_name, "testuser/test-image:runpod")
    
    def test_list_presets(self):
        """Test preset listing."""
        # This should not raise any exceptions
        self.script.list_presets()
    
    @patch('scripts.build_docker.DockerBuilder')
    def test_clean_cache(self, mock_builder_class):
        """Test cache cleaning."""
        mock_builder = MagicMock()
        mock_builder.clean_build_cache.return_value = True
        mock_builder_class.return_value = mock_builder
        
        result = self.script.clean_cache()
        self.assertTrue(result)
        mock_builder.clean_build_cache.assert_called_once()
    
    @patch('scripts.build_docker.DockerBuilder')
    @patch('scripts.build_docker.DependencyManager')
    @patch('scripts.build_docker.get_git_commit')
    def test_build_image_basic(self, mock_git_commit, mock_dep_manager, mock_builder_class):
        """Test basic image building."""
        # Mock dependencies
        mock_manager = MagicMock()
        mock_manager.check_all_dependencies.return_value = {"success": True}
        mock_manager.validate_dependency_structure.return_value = []
        mock_dep_manager.return_value = mock_manager
        
        # Mock git commit
        mock_git_commit.return_value = "abc123"
        
        # Mock builder
        mock_builder = MagicMock()
        mock_builder.build_image.return_value = True
        mock_builder_class.return_value = mock_builder
        
        # Create args
        args = argparse.Namespace(
            username="testuser",
            image_name="test-image",
            tag="latest",
            runpod=False,
            torch_variant="cu121",
            python_version="3.11",
            dockerfile="Dockerfile",
            build_context=".",
            no_cache=False,
            push=False,
            additional_tags=None
        )
        
        result = self.script.build_image(args)
        self.assertTrue(result)
        mock_builder.build_image.assert_called_once()
    
    @patch('scripts.build_docker.DependencyManager')
    def test_build_image_dependency_failure(self, mock_dep_manager):
        """Test build failure due to dependency issues."""
        # Mock dependency failure
        mock_manager = MagicMock()
        mock_manager.check_all_dependencies.return_value = {"success": False}
        mock_dep_manager.return_value = mock_manager
        
        args = argparse.Namespace(
            username="testuser",
            image_name="test-image",
            tag="latest",
            runpod=False,
            torch_variant="cu121"
        )
        
        result = self.script.build_image(args)
        self.assertFalse(result)


class TestArgumentParser(unittest.TestCase):
    """Test argument parser functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = create_parser()
    
    def test_parser_creation(self):
        """Test parser creation."""
        self.assertIsInstance(self.parser, argparse.ArgumentParser)
    
    def test_basic_arguments(self):
        """Test basic argument parsing."""
        args = self.parser.parse_args([
            "--username", "testuser",
            "--tag", "v1.0",
            "--torch-variant", "cu121"
        ])
        
        self.assertEqual(args.username, "testuser")
        self.assertEqual(args.tag, "v1.0")
        self.assertEqual(args.torch_variant, "cu121")
    
    def test_utility_arguments(self):
        """Test utility argument parsing."""
        # Test check dependencies
        args = self.parser.parse_args(["--check-dependencies"])
        self.assertTrue(args.check_dependencies)
        
        # Test list presets
        args = self.parser.parse_args(["--list-presets"])
        self.assertTrue(args.list_presets)
        
        # Test clean cache
        args = self.parser.parse_args(["--clean-cache"])
        self.assertTrue(args.clean_cache)
    
    def test_runpod_preset(self):
        """Test RunPod preset argument."""
        args = self.parser.parse_args([
            "--runpod",
            "--username", "testuser"
        ])
        
        self.assertTrue(args.runpod)
        self.assertEqual(args.username, "testuser")
    
    def test_logging_arguments(self):
        """Test logging argument parsing."""
        # Test verbose
        args = self.parser.parse_args(["--verbose", "--username", "test"])
        self.assertTrue(args.verbose)
        
        # Test quiet
        args = self.parser.parse_args(["--quiet", "--username", "test"])
        self.assertTrue(args.quiet)
    
    def test_default_values(self):
        """Test default argument values."""
        args = self.parser.parse_args(["--username", "test"])
        
        self.assertEqual(args.tag, "latest")
        self.assertEqual(args.image_name, "comfyui-flux")
        self.assertEqual(args.python_version, "3.11")
        self.assertEqual(args.dockerfile, "Dockerfile")
        self.assertEqual(args.build_context, ".")
        self.assertFalse(args.push)
        self.assertFalse(args.no_cache)
        self.assertFalse(args.runpod)


if __name__ == '__main__':
    unittest.main() 