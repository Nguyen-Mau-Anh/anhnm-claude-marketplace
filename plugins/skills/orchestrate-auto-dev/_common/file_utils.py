"""Safe file operations with error handling.

Provides atomic writes, safe reads, and temp file management.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, List

from .logger import Logger

logger = Logger("file_utils")


def safe_read(
    file_path: Path,
    encoding: str = "utf-8",
    default: Optional[str] = None
) -> str:
    """
    Safely read file with error handling.

    Args:
        file_path: Path to file
        encoding: File encoding (default: utf-8)
        default: Default value if file doesn't exist or read fails

    Returns:
        File contents or default value
    """
    try:
        if not file_path.exists():
            logger.debug(f"File not found: {file_path}")
            if default is not None:
                logger.debug(f"Returning default value for {file_path}")
                return default
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
            logger.debug(f"Read {len(content)} bytes from {file_path.name}")
            return content

    except UnicodeDecodeError:
        logger.warning(f"Encoding error with {encoding}, trying alternative encodings for {file_path.name}")
        # Try different encodings
        for alt_encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                with open(file_path, 'r', encoding=alt_encoding) as f:
                    content = f.read()
                    logger.info(f"Successfully read {file_path.name} with {alt_encoding} encoding")
                    return content
            except:
                continue

        # If all fail, return default or raise
        logger.error(f"All encodings failed for {file_path}")
        if default is not None:
            return default
        raise

    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        if default is not None:
            return default
        raise IOError(f"Failed to read {file_path}: {e}")


def safe_write(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    atomic: bool = True
) -> None:
    """
    Safely write file with atomic operation.

    Args:
        file_path: Path to file
        content: Content to write
        encoding: File encoding (default: utf-8)
        atomic: Use atomic write (temp + rename) for safety
    """
    file_path = Path(file_path)

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if atomic:
        logger.debug(f"Writing {len(content)} bytes to {file_path.name} (atomic)")
        # Atomic write: write to temp file, then rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp"
        )

        try:
            # Write to temp file
            with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            os.replace(temp_path, file_path)
            logger.debug(f"Successfully wrote {file_path.name}")

        except Exception as e:
            # Cleanup temp file on error
            logger.error(f"Failed to write {file_path}: {e}")
            try:
                os.unlink(temp_path)
            except:
                pass
            raise IOError(f"Failed to write {file_path}: {e}")

    else:
        logger.debug(f"Writing {len(content)} bytes to {file_path.name} (direct)")
        # Direct write
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
                f.flush()
            logger.debug(f"Successfully wrote {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to write {file_path}: {e}")
            raise IOError(f"Failed to write {file_path}: {e}")


def ensure_dir(directory: Path, mode: int = 0o755) -> Path:
    """
    Ensure directory exists, creating it if needed.

    Args:
        directory: Directory path
        mode: Directory permissions (Unix only)

    Returns:
        Path to directory
    """
    directory = Path(directory)
    if not directory.exists():
        logger.debug(f"Creating directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True, mode=mode)
    return directory


def cleanup_temp(
    temp_dir: Path,
    pattern: str = "*",
    older_than_seconds: Optional[int] = None
) -> int:
    """
    Clean up temporary files in directory.

    Args:
        temp_dir: Temporary directory
        pattern: Glob pattern for files to delete
        older_than_seconds: Only delete files older than N seconds

    Returns:
        Number of files deleted
    """
    import time

    if not temp_dir.exists():
        logger.debug(f"Temp directory doesn't exist: {temp_dir}")
        return 0

    logger.debug(f"Cleaning up temp files in {temp_dir} (pattern: {pattern})")
    deleted = 0
    current_time = time.time()

    for file_path in temp_dir.glob(pattern):
        if not file_path.is_file():
            continue

        # Check age if specified
        if older_than_seconds is not None:
            file_age = current_time - file_path.stat().st_mtime
            if file_age < older_than_seconds:
                continue

        try:
            file_path.unlink()
            deleted += 1
        except Exception:
            pass  # Ignore errors, best effort

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} temp files from {temp_dir}")
    else:
        logger.debug(f"No temp files to clean in {temp_dir}")

    return deleted


def get_relative_path(file_path: Path, base_path: Path) -> Path:
    """
    Get relative path from base to file.

    Args:
        file_path: Target file path
        base_path: Base directory path

    Returns:
        Relative path
    """
    try:
        return Path(file_path).resolve().relative_to(Path(base_path).resolve())
    except ValueError:
        # If not relative, return absolute path
        return Path(file_path).resolve()


def copy_file(src: Path, dst: Path, overwrite: bool = False) -> bool:
    """
    Copy file with safety checks.

    Args:
        src: Source file
        dst: Destination file
        overwrite: Allow overwriting existing file

    Returns:
        True if copied, False if skipped
    """
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        logger.error(f"Source file not found: {src}")
        raise FileNotFoundError(f"Source file not found: {src}")

    if dst.exists() and not overwrite:
        logger.debug(f"Skipping copy (destination exists): {src.name} → {dst}")
        return False

    # Ensure destination directory exists
    dst.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Copying file: {src.name} → {dst}")
    shutil.copy2(src, dst)
    logger.debug(f"Successfully copied {src.name}")
    return True


def find_files(
    directory: Path,
    pattern: str = "*",
    recursive: bool = True,
    exclude_dirs: Optional[List[str]] = None
) -> List[Path]:
    """
    Find files matching pattern.

    Args:
        directory: Directory to search
        pattern: Glob pattern
        recursive: Search recursively
        exclude_dirs: Directory names to exclude

    Returns:
        List of matching file paths
    """
    directory = Path(directory)
    exclude_dirs = exclude_dirs or ['.git', 'node_modules', '__pycache__', '.venv']

    if not directory.exists():
        logger.debug(f"Directory doesn't exist: {directory}")
        return []

    logger.debug(f"Finding files in {directory} (pattern: {pattern}, recursive: {recursive})")
    results = []
    glob_pattern = f"**/{pattern}" if recursive else pattern

    for path in directory.glob(glob_pattern):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue

        if path.is_file():
            results.append(path)

    logger.debug(f"Found {len(results)} files matching {pattern}")
    return sorted(results)
