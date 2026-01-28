"""Deployment handler for orchestrate-dev-test.

Handles local and cloud deployment for test execution.
"""

import subprocess
import time
import json
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from .logger import Logger

logger = Logger("deployer")


@dataclass
class DeploymentResult:
    """Result of a deployment attempt."""
    success: bool
    method: str
    url: str
    status: str  # "healthy", "unhealthy", "failed"
    error: Optional[str] = None


class Deployer:
    """Handle application deployment for test execution."""

    def __init__(self, project_root: Path, enabled: bool = True):
        self.project_root = Path(project_root)
        self.enabled = enabled
        logger.debug(f"Deployer initialized for {project_root}")

    def deploy(self, story_id: Optional[str] = None) -> DeploymentResult:
        """
        Deploy the application for testing.

        Tries deployment methods in order until one succeeds.
        """
        logger.info(f"Starting deployment{' for story ' + story_id if story_id else ''}")

        if not self.enabled:
            logger.info("Deployment disabled, skipping")
            return DeploymentResult(
                success=True,
                method="none",
                url="http://localhost:3000",  # Default
                status="skipped",
            )

        # Try to detect the best deployment method
        method, command = self._detect_deployment_method()

        if not method:
            logger.error("No suitable deployment method found")
            return DeploymentResult(
                success=False,
                method="none",
                url="",
                status="failed",
                error="No suitable deployment method found",
            )

        logger.info(f"Using deployment method: {method}")
        logger.debug(f"Deployment command: {command}")

        # Execute deployment
        try:
            logger.info(f"Executing deployment command: {command}")
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for deployment
            )

            if result.returncode != 0:
                logger.error(f"Deployment failed: {result.stderr}")
                return DeploymentResult(
                    success=False,
                    method=method,
                    url="",
                    status="failed",
                    error=f"Deployment failed: {result.stderr}",
                )

            # Detect the URL
            url = self._detect_url(result.stdout)
            logger.info(f"Deployment URL detected: {url}")

            # Wait for health check
            logger.debug(f"Waiting for application health check at {url}")
            health_status = self._wait_for_health(url)
            logger.info(f"Health check result: {health_status}")

            # Write deployment info
            self._write_deployment_info(story_id, method, url, health_status)

            if health_status == "healthy":
                logger.info(f"Deployment successful: {method} at {url}")
            else:
                logger.warning(f"Deployment completed but health check failed: {health_status}")

            return DeploymentResult(
                success=health_status == "healthy",
                method=method,
                url=url,
                status=health_status,
            )

        except subprocess.TimeoutExpired:
            logger.error("Deployment timed out after 5 minutes")
            return DeploymentResult(
                success=False,
                method=method,
                url="",
                status="timeout",
                error="Deployment timed out",
            )
        except Exception as e:
            logger.error(f"Deployment error: {e}")
            return DeploymentResult(
                success=False,
                method=method,
                url="",
                status="failed",
                error=str(e),
            )

    def _detect_deployment_method(self) -> tuple[Optional[str], Optional[str]]:
        """Detect the best deployment method for this project."""
        logger.debug("Detecting deployment method")

        # Check for docker-compose
        if (self.project_root / "docker-compose.yml").exists():
            logger.info("Found docker-compose.yml, using Docker Compose")
            return "docker-compose", "docker-compose up -d"

        if (self.project_root / "docker-compose.yaml").exists():
            logger.info("Found docker-compose.yaml, using Docker Compose")
            return "docker-compose", "docker-compose up -d"

        # Check for Makefile
        makefile = self.project_root / "Makefile"
        if makefile.exists():
            logger.debug("Found Makefile, checking for run/start targets")
            content = makefile.read_text()
            if "run:" in content or "start:" in content:
                logger.info("Found Makefile with run/start targets, using make")
                return "make", "make run || make start"

        # Check package.json for scripts
        package_json = self.project_root / "package.json"
        if package_json.exists():
            logger.debug("Found package.json, checking for dev/start scripts")
            try:
                data = json.loads(package_json.read_text())
                scripts = data.get("scripts", {})

                if "dev" in scripts:
                    logger.info("Found 'dev' script in package.json, using npm run dev")
                    return "npm-dev", "npm run dev &"
                if "start" in scripts:
                    logger.info("Found 'start' script in package.json, using npm run start")
                    return "npm-start", "npm run start &"

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse package.json: {e}")

        logger.warning("No deployment method detected")
        return None, None

    def _detect_url(self, output: str) -> str:
        """Detect the application URL from deployment output."""
        import re

        # Common URL patterns in deployment output
        patterns = [
            r'http://localhost:(\d+)',
            r'http://127\.0\.0\.1:(\d+)',
            r'Running on.*http://[^:]+:(\d+)',
            r'Local:\s*http://localhost:(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                port = match.group(1)
                return f"http://localhost:{port}"

        # Default to common ports
        return "http://localhost:3000"

    def _wait_for_health(self, url: str) -> str:
        """Wait for application to be healthy."""
        import urllib.request
        import urllib.error

        timeout = self.config.deployment.health_check_timeout
        start_time = time.time()

        # Try health endpoint first, then root
        health_urls = [
            f"{url}/health",
            f"{url}/api/health",
            url,
        ]

        while time.time() - start_time < timeout:
            for health_url in health_urls:
                try:
                    req = urllib.request.Request(health_url, method='GET')
                    with urllib.request.urlopen(req, timeout=5) as response:
                        if response.status == 200:
                            print(f"[deployer] Health check passed: {health_url}")
                            return "healthy"
                except urllib.error.URLError:
                    pass
                except Exception:
                    pass

            time.sleep(2)

        print(f"[deployer] Health check failed after {timeout}s")
        return "unhealthy"

    def _write_deployment_info(
        self,
        story_id: str,
        method: str,
        url: str,
        status: str
    ) -> None:
        """Write deployment info to status file."""
        try:
            env_dir = self.project_root / self.config.output.test_env_dir
            env_dir.mkdir(parents=True, exist_ok=True)

            info_file = env_dir / f"{story_id}.json"
            info = {
                "story_id": story_id,
                "deployment": {
                    "method": method,
                    "url": url,
                    "status": status,
                    "deployed_at": datetime.utcnow().isoformat() + "Z",
                },
            }

            with open(info_file, 'w') as f:
                json.dump(info, f, indent=2)

            print(f"[deployer] Deployment info written to: {info_file}")

        except Exception as e:
            print(f"[deployer] Warning: Could not write deployment info: {e}")
