"""Entry point for orchestrate-auto-dev executor."""

import sys
import subprocess
import shutil
from pathlib import Path


def ensure_config_exists():
    """Copy default config to project if it doesn't exist yet."""
    # Get project root (4 levels up from this file)
    skill_dir = Path(__file__).parent.parent
    project_root = skill_dir.parent.parent.parent

    # Paths
    default_config = skill_dir / "default.config.yaml"
    project_config = project_root / "docs" / "orchestrate-auto-dev.config.yaml"

    # If project config already exists, nothing to do
    if project_config.exists():
        return

    # If default config doesn't exist, warn and skip
    if not default_config.exists():
        print(f"⚠️  Warning: Default config not found at {default_config}")
        return

    # Ensure docs folder exists
    try:
        project_config.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"⚠️  Warning: Could not create docs folder: {e}")
        return

    # Copy default to project
    try:
        shutil.copy(default_config, project_config)
        print(f"📋 Created configuration file: {project_config.relative_to(project_root)}")
        print(f"   You can customize this file for your project.")
        print()
    except Exception as e:
        print(f"⚠️  Warning: Could not copy default config: {e}")


def check_and_install_dependencies():
    """Check if required packages are installed, install if missing."""
    skill_dir = Path(__file__).parent.parent
    requirements_file = skill_dir / "requirements.txt"

    if not requirements_file.exists():
        return  # No requirements file, skip

    # Read requirements
    try:
        with open(requirements_file) as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"Warning: Could not read requirements.txt: {e}")
        return

    if not requirements:
        return  # Empty requirements

    # Check if packages are installed
    missing_packages = []
    for req in requirements:
        # Parse package name (before >=, ==, etc.)
        package_name = req.split('>=')[0].split('==')[0].split('<')[0].strip()

        try:
            __import__(package_name.replace('-', '_'))  # Python imports use underscores
        except ImportError:
            missing_packages.append(req)

    # Install missing packages
    if missing_packages:
        print(f"\n🔧 Installing missing dependencies...")
        for pkg in missing_packages:
            print(f"   - {pkg}")

        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "--quiet"
            ] + missing_packages)
            print(f"✅ Dependencies installed successfully\n")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            print(f"   Please run: pip install {' '.join(missing_packages)}")
            sys.exit(1)


if __name__ == "__main__":
    # Ensure config file exists in project (copy from default if needed)
    ensure_config_exists()

    # Check and install dependencies before running
    check_and_install_dependencies()

    from .cli import main
    main()
