"""
Unit tests for structured dependencies functionality.
"""

import unittest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.dependency_manager import DependencyManager


class TestStructuredDependencies(unittest.TestCase):
    """Test structured dependencies functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.deps_file = Path(self.temp_dir) / "test_structured_deps.yaml"
        
        # Sample structured dependencies
        self.structured_deps = {
            'version': '2.0',
            'description': 'Test dependencies',
            'core_dependencies': {
                'test_core': {
                    'type': 'git',
                    'url': 'https://github.com/test/core.git',
                    'destination': 'test-core',
                    'description': 'Test core dependency',
                    'priority': 'high'
                }
            },
            'optional_models': {
                'test_model': {
                    'type': 'huggingface',
                    'repo_id': 'test/model',
                    'filename': 'model.safetensors',
                    'destination': 'models/test.safetensors',
                    'description': 'Test model',
                    'priority': 'medium',
                    'size_mb': 100,
                    'enabled': True
                },
                'disabled_model': {
                    'type': 'file',
                    'url': 'https://example.com/model.bin',
                    'destination': 'models/disabled.bin',
                    'description': 'Disabled model',
                    'priority': 'low',
                    'size_mb': 50,
                    'enabled': False
                }
            },
            'presets': {
                'minimal': {
                    'description': 'Minimal preset',
                    'includes': ['core_dependencies']
                },
                'standard': {
                    'description': 'Standard preset',
                    'includes': [
                        'core_dependencies',
                        {'optional_models': ['test_model']}
                    ]
                },
                'full': {
                    'description': 'Full preset',
                    'includes': [
                        'core_dependencies',
                        'optional_models'
                    ]
                }
            }
        }
        
        # Write structured dependencies file
        with open(self.deps_file, 'w') as f:
            yaml.dump(self.structured_deps, f)
    
    def test_load_structured_dependencies_minimal(self):
        """Test loading minimal preset."""
        dm = DependencyManager(str(self.deps_file))
        success = dm.load_dependencies('minimal')
        
        self.assertTrue(success)
        self.assertTrue(dm.is_structured)
        self.assertEqual(len(dm.dependencies), 1)
        
        dep = dm.dependencies[0]
        self.assertEqual(dep['name'], 'test_core')
        self.assertEqual(dep['type'], 'git')
        self.assertEqual(dep['category'], 'core_dependencies')
    
    def test_load_structured_dependencies_standard(self):
        """Test loading standard preset."""
        dm = DependencyManager(str(self.deps_file))
        success = dm.load_dependencies('standard')
        
        self.assertTrue(success)
        self.assertEqual(len(dm.dependencies), 2)
        
        # Check core dependency
        core_dep = next(d for d in dm.dependencies if d['name'] == 'test_core')
        self.assertEqual(core_dep['category'], 'core_dependencies')
        
        # Check optional model (enabled one)
        model_dep = next(d for d in dm.dependencies if d['name'] == 'test_model')
        self.assertEqual(model_dep['category'], 'optional_models')
        self.assertEqual(model_dep['size_mb'], 100)
    
    def test_load_structured_dependencies_full(self):
        """Test loading full preset."""
        dm = DependencyManager(str(self.deps_file))
        success = dm.load_dependencies('full')
        
        self.assertTrue(success)
        # Should include core + enabled optional (disabled_model has enabled: False)
        self.assertEqual(len(dm.dependencies), 2)
    
    def test_get_available_presets(self):
        """Test getting available presets."""
        dm = DependencyManager(str(self.deps_file))
        dm.load_dependencies('minimal')
        
        presets = dm.get_available_presets()
        
        self.assertIn('minimal', presets)
        self.assertIn('standard', presets)
        self.assertIn('full', presets)
        self.assertEqual(presets['minimal'], 'Minimal preset')
    
    def test_get_dependencies_by_category(self):
        """Test grouping dependencies by category."""
        dm = DependencyManager(str(self.deps_file))
        dm.load_dependencies('standard')
        
        categories = dm.get_dependencies_by_category()
        
        self.assertIn('core_dependencies', categories)
        self.assertIn('optional_models', categories)
        self.assertEqual(len(categories['core_dependencies']), 1)
        self.assertEqual(len(categories['optional_models']), 1)
    
    def test_get_dependencies_by_priority(self):
        """Test grouping dependencies by priority."""
        dm = DependencyManager(str(self.deps_file))
        dm.load_dependencies('standard')
        
        priorities = dm.get_dependencies_by_priority()
        
        self.assertEqual(len(priorities['high']), 1)
        self.assertEqual(len(priorities['medium']), 1)
        self.assertEqual(len(priorities['low']), 0)
    
    def test_get_download_size_estimate(self):
        """Test size estimation."""
        dm = DependencyManager(str(self.deps_file))
        dm.load_dependencies('standard')
        
        sizes = dm.get_download_size_estimate()
        
        self.assertEqual(sizes['core_dependencies'], 0)  # No size specified
        self.assertEqual(sizes['optional_models'], 100)  # test_model size
    
    def test_get_dependency_summary(self):
        """Test dependency summary."""
        dm = DependencyManager(str(self.deps_file))
        dm.load_dependencies('standard')
        
        summary = dm.get_dependency_summary()
        
        self.assertEqual(summary['total_dependencies'], 2)
        self.assertEqual(summary['format'], 'structured')
        self.assertEqual(summary['categories']['core_dependencies'], 1)
        self.assertEqual(summary['categories']['optional_models'], 1)
        self.assertEqual(summary['estimated_size_mb'], 100)
    
    def test_fallback_to_minimal_preset(self):
        """Test fallback to minimal when invalid preset requested."""
        dm = DependencyManager(str(self.deps_file))
        
        with patch.object(dm.logger, 'warning') as mock_warning:
            success = dm.load_dependencies('nonexistent')
            
            self.assertTrue(success)
            mock_warning.assert_called_with("Preset 'nonexistent' not found, using minimal")
            self.assertEqual(len(dm.dependencies), 1)  # Only core dependencies
    
    def test_legacy_format_detection(self):
        """Test detection of legacy format."""
        # Create legacy format file
        legacy_file = Path(self.temp_dir) / "legacy_deps.yaml"
        legacy_deps = {
            'dependencies': [
                {
                    'type': 'git',
                    'url': 'https://github.com/test/repo.git',
                    'destination': 'test-repo'
                }
            ]
        }
        
        with open(legacy_file, 'w') as f:
            yaml.dump(legacy_deps, f)
        
        dm = DependencyManager(str(legacy_file))
        success = dm.load_dependencies()
        
        self.assertTrue(success)
        self.assertFalse(dm.is_structured)
        self.assertEqual(len(dm.dependencies), 1)
        
        presets = dm.get_available_presets()
        self.assertEqual(presets, {"default": "Legacy format - all dependencies"})


if __name__ == '__main__':
    unittest.main() 