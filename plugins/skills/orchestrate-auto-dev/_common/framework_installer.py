"""Test framework detection and installation utilities.

Provides automatic detection and installation of test frameworks
(Playwright, Jest, Pytest) with retry logic for reliability.
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum

from .logger import Logger
from .retry_handler import RetryHandler, RetryConfig, BackoffStrategy

logger = Logger("framework_installer")


class TestFramework(str, Enum):
    """Supported test frameworks."""
    PLAYWRIGHT = "playwright"
    JEST = "jest"
    PYTEST = "pytest"
    CYPRESS = "cypress"
    NONE = "none"


class FrameworkType(str, Enum):
    """Type of testing the framework is for."""
    E2E_UI = "e2e_ui"           # End-to-end / UI testing
    UNIT = "unit"               # Unit testing
    API = "api"                 # API testing
    INTEGRATION = "integration"  # Integration testing


@dataclass
class FrameworkInfo:
    """Information about detected framework."""
    framework: TestFramework
    version: Optional[str] = None
    config_file: Optional[str] = None
    installed: bool = False
    configured: bool = False


@dataclass
class InstallationResult:
    """Result of framework installation."""
    success: bool
    framework: TestFramework
    version: Optional[str] = None
    attempts: int = 1
    error_message: Optional[str] = None
    installed_packages: List[str] = None


class FrameworkDetector:
    """
    Detect installed test frameworks.

    Checks:
    - package.json dependencies
    - Config files
    - Executable availability
    """

    def __init__(self, project_root: str):
        """
        Initialize detector.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)
        logger.debug(f"Initialized FrameworkDetector for {project_root}")

    def detect(self) -> FrameworkInfo:
        """
        Detect installed framework.

        Returns:
            FrameworkInfo with detection results
        """
        logger.info("Detecting test framework...")

        # Check for JavaScript/TypeScript frameworks
        if (self.project_root / "package.json").exists():
            framework_info = self._detect_js_framework()
            if framework_info.framework != TestFramework.NONE:
                logger.info(f"Detected {framework_info.framework.value} framework")
                return framework_info

        # Check for Python frameworks
        if self._is_python_project():
            framework_info = self._detect_python_framework()
            if framework_info.framework != TestFramework.NONE:
                logger.info(f"Detected {framework_info.framework.value} framework")
                return framework_info

        logger.info("No test framework detected")
        return FrameworkInfo(framework=TestFramework.NONE)

    def _detect_js_framework(self) -> FrameworkInfo:
        """Detect JavaScript/TypeScript framework."""
        package_json_path = self.project_root / "package.json"

        try:
            with open(package_json_path) as f:
                package_data = json.load(f)

            deps = {
                **package_data.get("dependencies", {}),
                **package_data.get("devDependencies", {})
            }

            # Check Playwright
            if "@playwright/test" in deps or "playwright" in deps:
                version = deps.get("@playwright/test") or deps.get("playwright")
                config_file = self._find_config_file("playwright.config")
                installed = self._check_executable("playwright")

                return FrameworkInfo(
                    framework=TestFramework.PLAYWRIGHT,
                    version=version,
                    config_file=config_file,
                    installed=installed,
                    configured=config_file is not None
                )

            # Check Jest
            if "jest" in deps or "@types/jest" in deps:
                version = deps.get("jest")
                config_file = self._find_config_file("jest.config")
                installed = self._check_executable("jest")

                return FrameworkInfo(
                    framework=TestFramework.JEST,
                    version=version,
                    config_file=config_file,
                    installed=installed,
                    configured=config_file is not None
                )

            # Check Cypress
            if "cypress" in deps:
                version = deps.get("cypress")
                config_file = self._find_config_file("cypress.config")
                installed = self._check_executable("cypress")

                return FrameworkInfo(
                    framework=TestFramework.CYPRESS,
                    version=version,
                    config_file=config_file,
                    installed=installed,
                    configured=config_file is not None
                )

        except Exception as e:
            logger.warning(f"Error reading package.json: {e}")

        return FrameworkInfo(framework=TestFramework.NONE)

    def _detect_python_framework(self) -> FrameworkInfo:
        """Detect Python framework."""
        # Check pytest
        if self._check_python_package("pytest"):
            version = self._get_python_package_version("pytest")
            config_file = self._find_config_file("pytest.ini")

            return FrameworkInfo(
                framework=TestFramework.PYTEST,
                version=version,
                config_file=config_file,
                installed=True,
                configured=config_file is not None
            )

        return FrameworkInfo(framework=TestFramework.NONE)

    def _is_python_project(self) -> bool:
        """Check if project is Python project."""
        indicators = [
            "requirements.txt",
            "setup.py",
            "pyproject.toml",
            "Pipfile"
        ]
        return any((self.project_root / indicator).exists() for indicator in indicators)

    def _find_config_file(self, prefix: str) -> Optional[str]:
        """Find config file by prefix."""
        extensions = [".ts", ".js", ".json", ".ini", ""]
        for ext in extensions:
            config_file = self.project_root / f"{prefix}{ext}"
            if config_file.exists():
                logger.debug(f"Found config file: {config_file}")
                return str(config_file)
        return None

    def _check_executable(self, command: str) -> bool:
        """Check if executable is available."""
        try:
            result = subprocess.run(
                ["npx", command, "--version"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            is_available = result.returncode == 0
            if is_available:
                logger.debug(f"Executable '{command}' is available: {result.stdout.strip()}")
            return is_available
        except Exception as e:
            logger.debug(f"Executable '{command}' not available: {e}")
            return False

    def _check_python_package(self, package: str) -> bool:
        """Check if Python package is installed."""
        try:
            result = subprocess.run(
                ["python", "-c", f"import {package}"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            try:
                result = subprocess.run(
                    ["python3", "-c", f"import {package}"],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
            except Exception:
                return False

    def _get_python_package_version(self, package: str) -> Optional[str]:
        """Get Python package version."""
        try:
            result = subprocess.run(
                ["python", "-c", f"import {package}; print({package}.__version__)"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None


class FrameworkInstaller:
    """
    Install test frameworks with retry logic.

    Supports:
    - Playwright (with browser)
    - Jest (with TypeScript)
    - Pytest
    """

    def __init__(self, project_root: str):
        """
        Initialize installer.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root)

        # Configure retry with exponential backoff
        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay_seconds=10.0,
            max_delay_seconds=30.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0
        )
        self.retry_handler = RetryHandler(self.retry_config)

        logger.debug(f"Initialized FrameworkInstaller for {project_root}")

    def install_playwright(self) -> InstallationResult:
        """
        Install Playwright with retry logic.

        Returns:
            InstallationResult with installation outcome
        """
        logger.info("Installing Playwright...")

        try:
            # Install package with retry
            logger.info("Installing @playwright/test package...")
            self.retry_handler.retry(
                self._run_npm_install,
                ["@playwright/test@latest"]
            )

            # Install browser with retry
            logger.info("Installing Chromium browser...")
            self.retry_handler.retry(
                self._run_playwright_install,
                ["chromium"]
            )

            # Create config
            self._create_playwright_config()

            # Add scripts to package.json
            self._add_playwright_scripts()

            # Verify installation
            version = self._get_playwright_version()

            logger.info(f"Successfully installed Playwright {version}")

            return InstallationResult(
                success=True,
                framework=TestFramework.PLAYWRIGHT,
                version=version,
                attempts=self.retry_handler.get_stats().get('total_retries', 0) + 1,
                installed_packages=["@playwright/test", "chromium"]
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to install Playwright: {error_msg}")

            return InstallationResult(
                success=False,
                framework=TestFramework.PLAYWRIGHT,
                error_message=error_msg,
                attempts=self.retry_config.max_attempts
            )

    def install_jest(self) -> InstallationResult:
        """
        Install Jest with retry logic.

        Returns:
            InstallationResult with installation outcome
        """
        logger.info("Installing Jest...")

        try:
            # Install packages with retry
            logger.info("Installing Jest packages...")
            self.retry_handler.retry(
                self._run_npm_install,
                ["jest", "@types/jest", "ts-jest"]
            )

            # Initialize ts-jest
            self._init_ts_jest()

            # Create config if init failed
            if not (self.project_root / "jest.config.js").exists():
                self._create_jest_config()

            # Add scripts to package.json
            self._add_jest_scripts()

            # Verify installation
            version = self._get_jest_version()

            logger.info(f"Successfully installed Jest {version}")

            return InstallationResult(
                success=True,
                framework=TestFramework.JEST,
                version=version,
                attempts=self.retry_handler.get_stats().get('total_retries', 0) + 1,
                installed_packages=["jest", "@types/jest", "ts-jest"]
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to install Jest: {error_msg}")

            return InstallationResult(
                success=False,
                framework=TestFramework.JEST,
                error_message=error_msg,
                attempts=self.retry_config.max_attempts
            )

    def install_pytest(self) -> InstallationResult:
        """
        Install Pytest with retry logic.

        Returns:
            InstallationResult with installation outcome
        """
        logger.info("Installing Pytest...")

        try:
            # Install with retry
            logger.info("Installing pytest packages...")
            self.retry_handler.retry(
                self._run_pip_install,
                ["pytest", "pytest-asyncio"]
            )

            # Create config
            self._create_pytest_config()

            # Verify installation
            version = self._get_pytest_version()

            logger.info(f"Successfully installed Pytest {version}")

            return InstallationResult(
                success=True,
                framework=TestFramework.PYTEST,
                version=version,
                attempts=self.retry_handler.get_stats().get('total_retries', 0) + 1,
                installed_packages=["pytest", "pytest-asyncio"]
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to install Pytest: {error_msg}")

            return InstallationResult(
                success=False,
                framework=TestFramework.PYTEST,
                error_message=error_msg,
                attempts=self.retry_config.max_attempts
            )

    def _run_npm_install(self, packages: List[str]) -> None:
        """Run npm install with packages."""
        cmd = ["npm", "install", "-D"] + packages
        logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise RuntimeError(f"npm install failed: {result.stderr}")

        logger.debug(f"npm install succeeded: {result.stdout}")

    def _run_playwright_install(self, browsers: List[str]) -> None:
        """Run playwright install with browsers."""
        cmd = ["npx", "playwright", "install"] + browsers
        logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for large download
        )

        if result.returncode != 0:
            raise RuntimeError(f"playwright install failed: {result.stderr}")

        logger.debug(f"playwright install succeeded: {result.stdout}")

    def _run_pip_install(self, packages: List[str]) -> None:
        """Run pip install with packages."""
        # Try python3 first, then python
        for python_cmd in ["python3", "python"]:
            try:
                cmd = [python_cmd, "-m", "pip", "install"] + packages
                logger.debug(f"Running: {' '.join(cmd)}")

                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    logger.debug(f"pip install succeeded: {result.stdout}")
                    return
            except FileNotFoundError:
                continue

        raise RuntimeError("pip install failed: python/python3 not found")

    def _init_ts_jest(self) -> None:
        """Initialize ts-jest config."""
        try:
            result = subprocess.run(
                ["npx", "ts-jest", "config:init"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.debug("ts-jest initialized successfully")
        except Exception as e:
            logger.warning(f"ts-jest init failed, will create manual config: {e}")

    def _create_playwright_config(self) -> None:
        """Create Playwright config file."""
        config_path = self.project_root / "playwright.config.ts"

        if config_path.exists():
            logger.debug("Playwright config already exists, skipping")
            return

        config_content = '''import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
});
'''

        config_path.write_text(config_content)
        logger.info(f"Created Playwright config: {config_path}")

    def _create_jest_config(self) -> None:
        """Create Jest config file."""
        config_path = self.project_root / "jest.config.js"

        if config_path.exists():
            logger.debug("Jest config already exists, skipping")
            return

        config_content = '''module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: ['**/*.test.ts', '**/*.spec.ts'],
};
'''

        config_path.write_text(config_content)
        logger.info(f"Created Jest config: {config_path}")

    def _create_pytest_config(self) -> None:
        """Create Pytest config file."""
        config_path = self.project_root / "pytest.ini"

        if config_path.exists():
            logger.debug("Pytest config already exists, skipping")
            return

        config_content = '''[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    smoke: smoke tests
'''

        config_path.write_text(config_content)
        logger.info(f"Created Pytest config: {config_path}")

    def _add_playwright_scripts(self) -> None:
        """Add Playwright scripts to package.json."""
        self._add_npm_scripts({
            "test": "playwright test",
            "test:smoke": "playwright test --grep @smoke",
            "test:ui": "playwright test --ui"
        })

    def _add_jest_scripts(self) -> None:
        """Add Jest scripts to package.json."""
        self._add_npm_scripts({
            "test": "jest",
            "test:smoke": "jest --testPathPattern=smoke",
            "test:watch": "jest --watch"
        })

    def _add_npm_scripts(self, scripts: Dict[str, str]) -> None:
        """Add scripts to package.json if they don't exist."""
        package_json_path = self.project_root / "package.json"

        try:
            with open(package_json_path) as f:
                package_data = json.load(f)

            if "scripts" not in package_data:
                package_data["scripts"] = {}

            updated = False
            for script_name, script_cmd in scripts.items():
                if script_name not in package_data["scripts"]:
                    package_data["scripts"][script_name] = script_cmd
                    updated = True
                    logger.debug(f"Added script '{script_name}': {script_cmd}")

            if updated:
                with open(package_json_path, "w") as f:
                    json.dump(package_data, f, indent=2)
                logger.info("Updated package.json with test scripts")

        except Exception as e:
            logger.warning(f"Failed to update package.json: {e}")

    def _get_playwright_version(self) -> Optional[str]:
        """Get Playwright version."""
        try:
            result = subprocess.run(
                ["npx", "playwright", "--version"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_jest_version(self) -> Optional[str]:
        """Get Jest version."""
        try:
            result = subprocess.run(
                ["npx", "jest", "--version"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_pytest_version(self) -> Optional[str]:
        """Get Pytest version."""
        for python_cmd in ["python3", "python"]:
            try:
                result = subprocess.run(
                    [python_cmd, "-m", "pytest", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except Exception:
                continue
        return None


def detect_and_install_framework(
    project_root: str,
    preferred_framework: Optional[TestFramework] = None,
    framework_type: FrameworkType = FrameworkType.E2E_UI
) -> Tuple[FrameworkInfo, Optional[InstallationResult]]:
    """
    Detect existing framework or install new one.

    Args:
        project_root: Path to project root
        preferred_framework: Preferred framework to install if none found
        framework_type: Type of testing needed

    Returns:
        Tuple of (FrameworkInfo, InstallationResult)
        InstallationResult is None if framework already exists
    """
    logger.info("Starting framework detection and installation...")

    # Detect existing framework
    detector = FrameworkDetector(project_root)
    framework_info = detector.detect()

    # If framework exists and is properly installed, skip installation
    if framework_info.framework != TestFramework.NONE and framework_info.installed:
        logger.info(f"Framework {framework_info.framework.value} already installed, skipping")
        return framework_info, None

    # Determine which framework to install
    if preferred_framework:
        framework_to_install = preferred_framework
    else:
        # Auto-select based on type
        if framework_type == FrameworkType.E2E_UI:
            framework_to_install = TestFramework.PLAYWRIGHT
        elif framework_type == FrameworkType.UNIT:
            framework_to_install = TestFramework.JEST
        else:
            framework_to_install = TestFramework.JEST

    # Install framework
    installer = FrameworkInstaller(project_root)

    if framework_to_install == TestFramework.PLAYWRIGHT:
        install_result = installer.install_playwright()
    elif framework_to_install == TestFramework.JEST:
        install_result = installer.install_jest()
    elif framework_to_install == TestFramework.PYTEST:
        install_result = installer.install_pytest()
    else:
        raise ValueError(f"Unsupported framework: {framework_to_install}")

    # Update framework info
    if install_result.success:
        framework_info = FrameworkInfo(
            framework=install_result.framework,
            version=install_result.version,
            installed=True,
            configured=True
        )

    return framework_info, install_result
