"""Git operations utility for orchestrators.

Provides safe, convenient wrappers around git commands commonly used
in orchestration workflows.
"""

import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from .logger import Logger

logger = Logger("git_utils")


def get_changed_files(
    project_root: Path,
    base_branch: str = "HEAD",
    limit: Optional[int] = None,
    exclude_large: bool = True,
    max_size_kb: int = 100,
) -> List[str]:
    """
    Get list of changed files from git diff.

    Args:
        project_root: Project root directory
        base_branch: Base branch/ref to compare against (default: HEAD)
        limit: Maximum number of files to return (None = unlimited)
        exclude_large: Exclude files larger than max_size_kb
        max_size_kb: Maximum file size in KB (default: 100)

    Returns:
        List of changed file paths (relative to project root)
    """
    logger.debug(f"Getting changed files from {base_branch} in {project_root}")
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', base_branch],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.warning(f"Git diff failed: {result.stderr}")
            return []

        files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        logger.debug(f"Found {len(files)} changed files (unfiltered)")

        # Filter files
        filtered_files = []
        for file_path in files:
            full_path = project_root / file_path

            # Skip if file doesn't exist
            if not full_path.exists():
                continue

            # Skip large files
            if exclude_large:
                try:
                    size_kb = full_path.stat().st_size / 1024
                    if size_kb > max_size_kb:
                        continue
                except (OSError, PermissionError):
                    continue

            # Skip binary files
            if file_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf',
                                   '.zip', '.tar', '.gz', '.bz2', '.7z',
                                   '.exe', '.dll', '.so', '.dylib')):
                continue

            filtered_files.append(file_path)

            # Apply limit
            if limit and len(filtered_files) >= limit:
                break

        logger.info(f"Returning {len(filtered_files)} changed files (after filtering)")
        return filtered_files

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
        logger.error(f"Error getting changed files: {e}")
        return []


def get_current_branch(project_root: Path) -> Optional[str]:
    """
    Get current git branch name.

    Args:
        project_root: Project root directory

    Returns:
        Current branch name or None if not in a git repo
    """
    logger.debug(f"Getting current branch from {project_root}")
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            branch = result.stdout.strip() or None
            logger.info(f"Current branch: {branch}")
            return branch

        logger.warning(f"Failed to get current branch: {result.stderr}")
        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
        logger.error(f"Error getting current branch: {e}")
        return None


def is_repo_clean(project_root: Path) -> bool:
    """
    Check if working tree is clean (no uncommitted changes).

    Args:
        project_root: Project root directory

    Returns:
        True if clean, False if there are uncommitted changes
    """
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return len(result.stdout.strip()) == 0

        return False

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return False


def get_diff(
    project_root: Path,
    base_branch: str = "HEAD",
    stat: bool = False,
) -> str:
    """
    Get git diff output.

    Args:
        project_root: Project root directory
        base_branch: Base branch/ref to compare against
        stat: If True, return --stat output instead of full diff

    Returns:
        Diff output as string (empty string on error)
    """
    try:
        cmd = ['git', 'diff']
        if stat:
            cmd.append('--stat')
        cmd.append(base_branch)

        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            return result.stdout

        return ""

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return ""


def commit_changes(
    project_root: Path,
    message: str,
    files: Optional[List[str]] = None,
    add_all: bool = False,
) -> Tuple[bool, str]:
    """
    Create a git commit.

    Args:
        project_root: Project root directory
        message: Commit message
        files: List of files to stage (None = use already staged files)
        add_all: If True, stage all changes (git add -A)

    Returns:
        Tuple of (success: bool, commit_hash or error: str)
    """
    logger.info(f"Creating commit: {message[:50]}...")
    try:
        # Stage files if requested
        if add_all:
            logger.debug("Staging all changes (git add -A)")
            result = subprocess.run(
                ['git', 'add', '-A'],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to stage all files: {result.stderr}")
                return False, f"Failed to stage files: {result.stderr}"

        elif files:
            logger.debug(f"Staging {len(files)} specific files")
            result = subprocess.run(
                ['git', 'add'] + files,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to stage files: {result.stderr}")
                return False, f"Failed to stage files: {result.stderr}"

        # Create commit
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error(f"Failed to create commit: {result.stderr}")
            return False, f"Failed to commit: {result.stderr}"

        # Get commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            logger.info(f"Created commit {commit_hash[:8]}: {message[:50]}")
            return True, commit_hash
        else:
            logger.warning("Commit created but failed to get hash")
            return True, "unknown"

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
        logger.error(f"Error creating commit: {e}")
        return False, str(e)


def get_remote_url(project_root: Path, remote: str = "origin") -> Optional[str]:
    """
    Get remote repository URL.

    Args:
        project_root: Project root directory
        remote: Remote name (default: origin)

    Returns:
        Remote URL or None if not found
    """
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', remote],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            return result.stdout.strip()

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return None


def is_git_repo(project_root: Path) -> bool:
    """
    Check if directory is a git repository.

    Args:
        project_root: Directory to check

    Returns:
        True if it's a git repo, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        return result.returncode == 0

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return False


def get_last_commit_info(project_root: Path) -> Optional[dict]:
    """
    Get information about the last commit.

    Args:
        project_root: Project root directory

    Returns:
        Dict with commit info (hash, author, message, date) or None
    """
    try:
        # Format: hash|author|date|message
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=format:%H|%an|%ai|%s'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout:
            parts = result.stdout.split('|', 3)
            if len(parts) == 4:
                return {
                    'hash': parts[0],
                    'author': parts[1],
                    'date': parts[2],
                    'message': parts[3],
                }

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception):
        return None


def create_branch(
    project_root: Path,
    branch_name: str,
    checkout: bool = True,
) -> Tuple[bool, str]:
    """
    Create a new git branch.

    Args:
        project_root: Project root directory
        branch_name: Name of the branch to create
        checkout: If True, checkout the new branch

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger.info(f"Creating branch '{branch_name}'" + (" and checking out" if checkout else ""))
    try:
        cmd = ['git', 'branch', branch_name]
        if checkout:
            cmd = ['git', 'checkout', '-b', branch_name]

        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info(f"Successfully created branch '{branch_name}'")
            return True, f"Branch '{branch_name}' created"
        else:
            logger.error(f"Failed to create branch: {result.stderr}")
            return False, result.stderr

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
        logger.error(f"Error creating branch: {e}")
        return False, str(e)


def push_to_remote(
    project_root: Path,
    remote: str = "origin",
    branch: Optional[str] = None,
    set_upstream: bool = False,
) -> Tuple[bool, str]:
    """
    Push changes to remote repository.

    Args:
        project_root: Project root directory
        remote: Remote name (default: origin)
        branch: Branch to push (None = current branch)
        set_upstream: If True, set upstream tracking

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger.info(f"Pushing to {remote}/{branch or 'current branch'}" + (" (set upstream)" if set_upstream else ""))
    try:
        cmd = ['git', 'push']

        if set_upstream:
            cmd.append('-u')

        cmd.append(remote)

        if branch:
            cmd.append(branch)

        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            logger.info(f"Successfully pushed to {remote}")
            return True, "Pushed successfully"
        else:
            logger.error(f"Failed to push: {result.stderr}")
            return False, result.stderr

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, Exception) as e:
        logger.error(f"Error pushing to remote: {e}")
        return False, str(e)
