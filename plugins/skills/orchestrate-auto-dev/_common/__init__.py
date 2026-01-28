"""Common orchestration utilities library.

This package contains shared utilities used by all orchestration skills.
Each utility is in its own file for clarity and maintainability.
"""

__version__ = "1.0.0"

# Phase 1: Core Infrastructure
from .spawner import (
    ClaudeSpawner,
    TaskResult,
    BackgroundTask,
    TaskStatus,
    CriticalError,
    ErrorSeverity,
    EscalationAction,
)

from .config_loader import (
    ConfigLoader,
    StageConfig,
    RetryConfig,
    KnowledgeBaseConfig,
    BaseConfig,
    load_yaml,
    save_yaml,
    merge_configs,
)

from .logger import (
    Logger,
    LogLevel,
    log,
)

from .status_manager import (
    StatusManager,
    PipelineStatus,
    StageStatus,
    PipelineState,
    StageInfo,
)

# Phase 2: Learning & Reliability
from .knowledge_base import (
    KnowledgeBase,
    Lesson,
    classify_error,
    extract_error_pattern,
    extract_module_name,
    extract_import_statement,
    get_dependency_files,
    ERROR_PATTERNS,
)

from .retry_handler import (
    RetryHandler,
    RetryConfig as RetryHandlerConfig,
    BackoffStrategy,
    with_retry,
    retry_on_failure,
)

from .file_utils import (
    safe_read,
    safe_write,
    ensure_dir,
    cleanup_temp,
    get_relative_path,
    copy_file,
    find_files,
)

from .validators import (
    validate_story_id,
    validate_file_exists,
    validate_directory_exists,
    validate_config,
    validate_stage_config,
    validate_timeout,
    validate_prompt,
    validate_or_raise,
)

# Phase 3: Task Management & Git Operations
from .task_tracker import (
    TaskTrackerManager,
    SubTask,
)

from .task_decomposer import (
    parse_story_tasks,
    should_decompose,
    get_incomplete_tasks,
    format_task_for_agent,
)

from .git_utils import (
    get_changed_files,
    get_current_branch,
    is_repo_clean,
    get_diff,
    commit_changes,
    get_remote_url,
    is_git_repo,
    get_last_commit_info,
    create_branch,
    push_to_remote,
)

from .health_checker import (
    HealthChecker,
    HealthStatus,
    HealthReport,
    detect_critical_errors,
    is_process_active,
)

# Phase 4: Test Utilities (Optional)
# Commented out - test_checker module does not exist yet
# from .test_checker import (
#     extract_story_type,
#     should_skip_tests,
#     check_test_requirement,
# )
extract_story_type = None
should_skip_tests = None
check_test_requirement = None

from .deployer import (
    Deployer,
    DeploymentResult,
)

from .framework_installer import (
    FrameworkDetector,
    FrameworkInstaller,
    TestFramework,
    FrameworkType,
    FrameworkInfo,
    InstallationResult,
    detect_and_install_framework,
)

# Commented out - test_runner has import issues (imports non-existent .config)
# from .test_runner import (
#     TestRunner,
#     TestResult,
# )
TestRunner = None
TestResult = None

__all__ = [
    # Phase 1: Core Infrastructure
    "ClaudeSpawner",
    "TaskResult",
    "BackgroundTask",
    "TaskStatus",
    "CriticalError",
    "ErrorSeverity",
    "EscalationAction",
    "ConfigLoader",
    "StageConfig",
    "RetryConfig",
    "KnowledgeBaseConfig",
    "BaseConfig",
    "load_yaml",
    "save_yaml",
    "merge_configs",
    "Logger",
    "LogLevel",
    "log",
    "StatusManager",
    "PipelineStatus",
    "StageStatus",
    "PipelineState",
    "StageInfo",
    # Phase 2: Learning & Reliability
    "KnowledgeBase",
    "Lesson",
    "classify_error",
    "extract_error_pattern",
    "extract_module_name",
    "extract_import_statement",
    "get_dependency_files",
    "ERROR_PATTERNS",
    "RetryHandler",
    "RetryHandlerConfig",
    "BackoffStrategy",
    "with_retry",
    "retry_on_failure",
    "safe_read",
    "safe_write",
    "ensure_dir",
    "cleanup_temp",
    "get_relative_path",
    "copy_file",
    "find_files",
    "validate_story_id",
    "validate_file_exists",
    "validate_directory_exists",
    "validate_config",
    "validate_stage_config",
    "validate_timeout",
    "validate_prompt",
    "validate_or_raise",
    # Phase 3: Task Management & Git Operations
    "TaskTrackerManager",
    "SubTask",
    "parse_story_tasks",
    "should_decompose",
    "get_incomplete_tasks",
    "format_task_for_agent",
    "get_changed_files",
    "get_current_branch",
    "is_repo_clean",
    "get_diff",
    "commit_changes",
    "get_remote_url",
    "is_git_repo",
    "get_last_commit_info",
    "create_branch",
    "push_to_remote",
    "HealthChecker",
    "HealthStatus",
    "HealthReport",
    "detect_critical_errors",
    "is_process_active",
    # Phase 4: Test Utilities (Optional)
    "extract_story_type",
    "should_skip_tests",
    "check_test_requirement",
    "Deployer",
    "DeploymentResult",
    "FrameworkDetector",
    "FrameworkInstaller",
    "TestFramework",
    "FrameworkType",
    "FrameworkInfo",
    "InstallationResult",
    "detect_and_install_framework",
    # "TestRunner",  # Commented out - has import issues
    # "TestResult",
]
