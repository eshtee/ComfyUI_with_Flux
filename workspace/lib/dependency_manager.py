"""
Enhanced dependency management utilities for ComfyUI build and runtime.
Supports both legacy and new structured dependency formats.
"""

import os
import yaml
import subprocess
import requests
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from .common import Logger, PathValidator, CommandRunner


class DependencyManager:
    """Enhanced dependency manager with preset and category support."""
    
    def __init__(self, dependencies_file: str = "dependencies.yaml", logger: Optional = None):
        self.dependencies_file = Path(dependencies_file)
        self.logger = logger or Logger.get_logger("DependencyManager")
        self.runner = CommandRunner(self.logger)
        self.raw_data: Dict[str, Any] = {}
        self.dependencies: List[Dict[str, Any]] = []
        self.is_structured = False
    
    def load_dependencies(self, preset: str = "minimal") -> bool:
        """Load dependencies from YAML file with preset support."""
        if not self.dependencies_file.exists():
            self.logger.error(f"Dependencies file not found: {self.dependencies_file}")
            return False
        
        try:
            with open(self.dependencies_file, 'r') as f:
                self.raw_data = yaml.safe_load(f)
            
            # Detect format
            if 'dependencies' in self.raw_data:
                # Legacy format
                self.is_structured = False
                self.dependencies = self.raw_data['dependencies']
                self.logger.info(f"Loaded {len(self.dependencies)} dependencies (legacy format)")
            else:
                # New structured format
                self.is_structured = True
                self.dependencies = self._parse_structured_dependencies(preset)
                self.logger.info(f"Loaded {len(self.dependencies)} dependencies (structured format, preset: {preset})")
            
            return True
            
        except yaml.YAMLError as e:
            self.logger.error(f"YAML parsing error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error loading dependencies: {e}")
            return False
    
    def _parse_structured_dependencies(self, preset: str) -> List[Dict[str, Any]]:
        """Parse structured dependencies based on preset."""
        dependencies = []
        
        # Get preset configuration
        presets = self.raw_data.get('presets', {})
        if preset not in presets:
            self.logger.warning(f"Preset '{preset}' not found, using minimal")
            preset = 'minimal'
        
        preset_config = presets.get(preset, {})
        includes = preset_config.get('includes', [])
        
        # Process each include
        for include in includes:
            if isinstance(include, str):
                # Simple category include
                category_deps = self._get_category_dependencies(include)
                dependencies.extend(category_deps)
            elif isinstance(include, dict):
                # Category with specific items
                for category, items in include.items():
                    if isinstance(items, list):
                        category_deps = self._get_category_dependencies(category, items)
                        dependencies.extend(category_deps)
        
        return dependencies
    
    def _get_category_dependencies(self, category: str, specific_items: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get dependencies from a specific category."""
        dependencies = []
        category_data = self.raw_data.get(category, {})
        
        for item_name, item_config in category_data.items():
            # Skip if specific items requested and this isn't one
            if specific_items and item_name not in specific_items:
                continue
            
            # Skip if disabled (for optional items)
            if not item_config.get('enabled', True) and category.startswith('optional_'):
                continue
            
            # Convert to legacy format for compatibility
            dependency = {
                'type': item_config.get('type'),
                'destination': item_config.get('destination'),
                'description': item_config.get('description', ''),
                'priority': item_config.get('priority', 'medium'),
                'category': category,
                'name': item_name,
                'size_mb': item_config.get('size_mb', 0)
            }
            
            # Add type-specific fields
            if item_config.get('type') == 'git':
                dependency['url'] = item_config.get('url')
            elif item_config.get('type') == 'file':
                dependency['url'] = item_config.get('url')
            elif item_config.get('type') == 'huggingface':
                dependency['repo_id'] = item_config.get('repo_id')
                dependency['filename'] = item_config.get('filename')
            
            dependencies.append(dependency)
        
        return dependencies
    
    def get_available_presets(self) -> Dict[str, str]:
        """Get available presets and their descriptions."""
        if not self.is_structured:
            return {"default": "Legacy format - all dependencies"}
        
        presets = self.raw_data.get('presets', {})
        return {name: config.get('description', '') for name, config in presets.items()}
    
    def get_dependencies_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group dependencies by category."""
        categories = {}
        for dep in self.dependencies:
            category = dep.get('category', 'uncategorized')
            if category not in categories:
                categories[category] = []
            categories[category].append(dep)
        return categories
    
    def get_dependencies_by_priority(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group dependencies by priority."""
        priorities = {'high': [], 'medium': [], 'low': []}
        for dep in self.dependencies:
            priority = dep.get('priority', 'medium')
            if priority in priorities:
                priorities[priority].append(dep)
        return priorities
    
    def get_download_size_estimate(self) -> Dict[str, int]:
        """Get estimated download sizes by category."""
        sizes = {}
        for dep in self.dependencies:
            category = dep.get('category', 'uncategorized')
            size_mb = dep.get('size_mb', 0)
            if category not in sizes:
                sizes[category] = 0
            sizes[category] += size_mb
        return sizes
    
    def validate_dependency_structure(self) -> List[str]:
        """Validate dependency structure and return errors."""
        errors = []
        
        for i, dep in enumerate(self.dependencies):
            # Check required fields
            if 'type' not in dep:
                errors.append(f"Dependency {i}: Missing 'type' field")
                continue
            
            if 'destination' not in dep:
                errors.append(f"Dependency {i}: Missing 'destination' field")
            
            dep_type = dep['type']
            
            # Type-specific validation
            if dep_type == 'git':
                if 'url' not in dep:
                    errors.append(f"Dependency {i}: Git type missing 'url' field")
            elif dep_type == 'file':
                if 'url' not in dep:
                    errors.append(f"Dependency {i}: File type missing 'url' field")
            elif dep_type == 'huggingface':
                if 'repo_id' not in dep:
                    errors.append(f"Dependency {i}: HuggingFace type missing 'repo_id' field")
                if 'filename' not in dep:
                    errors.append(f"Dependency {i}: HuggingFace type missing 'filename' field")
            else:
                errors.append(f"Dependency {i}: Unknown type '{dep_type}'")
        
        return errors
    
    def check_all_dependencies(self) -> Dict[str, Any]:
        """Check all dependencies and return summary."""
        if not self.dependencies:
            return {"success": False, "error": "No dependencies loaded"}
        
        self.logger.info("Checking existing dependencies...")
        
        existing_count = 0
        missing_count = 0
        
        for dep in self.dependencies:
            if self._check_dependency_exists(dep):
                existing_count += 1
            else:
                missing_count += 1
        
        total = len(self.dependencies)
        completion_rate = (existing_count / total) * 100 if total > 0 else 0
        
        self.logger.info("Dependency check complete:")
        self.logger.info(f"  ✅ Existing: {existing_count}/{total}")
        self.logger.info(f"  ❌ Missing:  {missing_count}/{total}")
        self.logger.info(f"  📊 Complete: {completion_rate:.1f}%")
        
        if missing_count > 0:
            self.logger.info("Missing dependencies will be downloaded during container startup")
        
        return {
            "success": True,
            "total": total,
            "existing": existing_count,
            "missing": missing_count,
            "completion_rate": completion_rate
        }
    
    def _check_dependency_exists(self, dep: Dict[str, Any]) -> bool:
        """Check if a dependency exists."""
        destination = dep.get('destination', '')
        if not destination:
            return False
        
        dest_path = Path(destination)
        
        if dep.get('type') == 'git':
            # Check if git repo exists (we remove .git after clone, so just check directory)
            return dest_path.exists() and dest_path.is_dir()
        else:
            # Check if file exists
            self.logger.info(f"  Checking if file exists: {dest_path}:{dest_path.exists()}:{dest_path.is_file()}")
            return dest_path.exists() and dest_path.is_file()
    
    def get_dependency_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of dependencies."""
        if not self.dependencies:
            return {"error": "No dependencies loaded"}
        
        summary = {
            "total_dependencies": len(self.dependencies),
            "format": "structured" if self.is_structured else "legacy",
            "categories": {},
            "priorities": {},
            "types": {},
            "estimated_size_mb": 0
        }
        
        # Count by category, priority, and type
        for dep in self.dependencies:
            # Category
            category = dep.get('category', 'uncategorized')
            summary["categories"][category] = summary["categories"].get(category, 0) + 1
            
            # Priority
            priority = dep.get('priority', 'medium')
            summary["priorities"][priority] = summary["priorities"].get(priority, 0) + 1
            
            # Type
            dep_type = dep.get('type', 'unknown')
            summary["types"][dep_type] = summary["types"].get(dep_type, 0) + 1
            
            # Size
            size_mb = dep.get('size_mb', 0)
            summary["estimated_size_mb"] += size_mb
        
        return summary
    
    def download_dependencies(self, force_download: bool = False) -> bool:
        """Download all loaded dependencies that are missing."""
        if not self.dependencies:
            self.logger.error("No dependencies loaded")
            return False
        
        self.logger.info("Starting dependency download process...")
        
        # Get download configuration
        download_config = self.raw_data.get('download_config', {})
        max_concurrent = download_config.get('max_concurrent', 3)
        retry_attempts = download_config.get('retry_attempts', 3)
        timeout_seconds = download_config.get('timeout_seconds', 300)
        
        total_deps = len(self.dependencies)
        downloaded = 0
        skipped = 0
        failed = 0
        
        for i, dep in enumerate(self.dependencies):
            self.logger.info(f"Processing dependency {i+1}/{total_deps}: {dep.get('name', 'unnamed')}")
            
            # Check if already exists
            if not force_download and self._check_dependency_exists(dep):
                self.logger.info(f"  ✓ Already exists, skipping")
                skipped += 1
                continue
            
            # Download dependency
            success = self._download_single_dependency(dep, retry_attempts, timeout_seconds)
            if success:
                downloaded += 1
                self.logger.info(f"  ✓ Downloaded successfully")
            else:
                failed += 1
                self.logger.error(f"  ✗ Download failed")
        
        self.logger.info(f"Dependency download completed:")
        self.logger.info(f"  ✅ Downloaded: {downloaded}")
        self.logger.info(f"  ⏭️  Skipped:    {skipped}")
        self.logger.info(f"  ❌ Failed:     {failed}")
        
        return failed == 0
    
    def _download_single_dependency(self, dep: Dict[str, Any], retry_attempts: int = 3, timeout: int = 300) -> bool:
        """Download a single dependency with retry logic."""
        dep_type = dep.get('type')
        destination = dep.get('destination', '')
        
        if not destination:
            self.logger.error("Dependency missing destination")
            return False
        
        dest_path = Path(destination)
        
        # Create parent directory
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        for attempt in range(retry_attempts):
            try:
                if attempt > 0:
                    self.logger.info(f"  Retry attempt {attempt + 1}/{retry_attempts}")
                
                if dep_type == 'git':
                    return self._download_git_dependency(dep, dest_path)
                elif dep_type == 'file':
                    return self._download_file_dependency(dep, dest_path, timeout)
                elif dep_type == 'huggingface':
                    return self._download_huggingface_dependency(dep, dest_path, timeout)
                else:
                    self.logger.error(f"Unknown dependency type: {dep_type}")
                    return False
                    
            except Exception as e:
                self.logger.warning(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < retry_attempts - 1:
                    continue
                else:
                    self.logger.error(f"  All {retry_attempts} attempts failed")
                    return False
        
        return False
    
    def _download_git_dependency(self, dep: Dict[str, Any], dest_path: Path) -> bool:
        """Download a git repository."""
        url = dep.get('url')
        if not url:
            self.logger.error("Git dependency missing URL")
            return False
        
        # Remove existing directory if it exists
        if dest_path.exists():
            shutil.rmtree(dest_path)
        
        # Clone repository
        cmd = ['git', 'clone', url, str(dest_path)]
        result = self.runner.run_safe(cmd, timeout=300)
        
        if result and result.returncode == 0:
            # Remove .git directory to save space
            git_dir = dest_path / '.git'
            if git_dir.exists():
                shutil.rmtree(git_dir)
            return True
        else:
            self.logger.error(f"Git clone failed: {result.stderr if result else 'Unknown error'}")
            return False
    
    def _download_file_dependency(self, dep: Dict[str, Any], dest_path: Path, timeout: int = 300) -> bool:
        """Download a file from URL."""
        url = dep.get('url')
        if not url:
            self.logger.error("File dependency missing URL")
            return False
        
        # Add CivitAI token if downloading from CivitAI
        if 'civitai' in url.lower():
            civitai_token = os.getenv('CIVITAI_TOKEN')
            if civitai_token:
                # Parse URL to add token parameter
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                query_params['token'] = [civitai_token]
                new_query = urlencode(query_params, doseq=True)
                url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
                self.logger.info("  Added CivitAI authentication token")
            else:
                self.logger.warning("  CivitAI URL detected but CIVITAI_TOKEN not set")
        
        try:
            self.logger.info(f"  Downloading from: {url}")
            
            # Download with requests
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()
            
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            with open(dest_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Progress logging for large files
                        if total_size > 0 and downloaded % (1024 * 1024 * 50) == 0:  # Every 50MB
                            progress = (downloaded / total_size) * 100
                            self.logger.info(f"  Progress: {progress:.1f}% ({downloaded // (1024*1024)}MB)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"File download failed: {e}")
            # Clean up partial download
            if dest_path.exists():
                dest_path.unlink()
            return False
    
    def _download_huggingface_dependency(self, dep: Dict[str, Any], dest_path: Path, timeout: int = 300) -> bool:
        """Download a file from HuggingFace Hub."""
        repo_id = dep.get('repo_id')
        filename = dep.get('filename')
        
        if not repo_id or not filename:
            self.logger.error("HuggingFace dependency missing repo_id or filename")
            return False
        
        try:
            # Try using huggingface_hub if available
            try:
                from huggingface_hub import hf_hub_download
                self.logger.info(f"  Downloading from HuggingFace: {repo_id}/{filename}")
                
                downloaded_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=dest_path.parent,
                    force_download=True
                )
                
                self.logger.info(f"  File downloaded to: {downloaded_path}")
                # self.logger.info(f"  Copying to: {dest_path}")
                # Move to final destination
                # shutil.move(downloaded_path, dest_path)
                return True
                
            except ImportError:
                # Fallback to direct URL download
                self.logger.info("huggingface_hub not available, using direct download")
                
                # Construct HuggingFace URL
                hf_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
                
                # Update dependency for file download
                file_dep = dep.copy()
                file_dep['url'] = hf_url
                file_dep['type'] = 'file'
                
                return self._download_file_dependency(file_dep, dest_path, timeout)
                
        except Exception as e:
            self.logger.error(f"HuggingFace download failed: {e}")
            return False 