#!/usr/bin/env python3
"""
Validate stage_logger usage in runner.py

This script ensures:
1. All stage methods (_run_*_stage) have stage_logger initialized
2. No helper methods use stage_logger (they should use self.logger)
"""

import sys
from pathlib import Path

def validate_stage_logger():
    runner_file = Path(__file__).parent / "runner.py"
    
    with open(runner_file) as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find all stage methods with stage_logger initialized
    stage_methods_with_logger = []
    for i, line in enumerate(lines):
        if 'stage_logger = self._get_stage_logger(' in line:
            for j in range(i, -1, -1):
                if lines[j].strip().startswith('def '):
                    method_name = lines[j].strip().split('(')[0].replace('def ', '')
                    stage_methods_with_logger.append(method_name)
                    break
    
    # Find all stage methods (_run_*_stage)
    # Exclude _run_stage (it's a router, not an executor)
    all_stage_methods = []
    for i, line in enumerate(lines):
        if line.strip().startswith('def _run_') and '_stage' in line:
            method_name = line.strip().split('(')[0].replace('def ', '')
            # Exclude _run_stage - it's a router that delegates to other methods
            if method_name != '_run_stage':
                all_stage_methods.append(method_name)
    
    # Find helper methods using stage_logger
    helper_methods_with_stage_logger = {}
    current_method = None
    for i, line in enumerate(lines, start=1):
        if line.strip().startswith('def _'):
            current_method = line.strip().split('(')[0].replace('def ', '')
        
        if 'stage_logger.' in line:
            if '= self._get_stage_logger' not in line and 'stage_logger = ' not in line:
                if current_method and current_method not in stage_methods_with_logger:
                    if current_method not in helper_methods_with_stage_logger:
                        helper_methods_with_stage_logger[current_method] = []
                    helper_methods_with_stage_logger[current_method].append(i)
    
    # Report results
    errors = []
    
    print("=" * 60)
    print("Stage Logger Validation Report")
    print("=" * 60)
    
    # Check 1: All stage methods have stage_logger
    print(f"\n✅ Stage methods found: {len(all_stage_methods)}")
    print(f"✅ Stage methods with stage_logger: {len(stage_methods_with_logger)}")
    
    missing_logger = set(all_stage_methods) - set(stage_methods_with_logger)
    if missing_logger:
        errors.append(f"Stage methods missing stage_logger: {missing_logger}")
        print(f"\n❌ ERROR: {errors[-1]}")
    else:
        print("✅ All stage methods have stage_logger initialized")
    
    # Check 2: No helper methods use stage_logger
    if helper_methods_with_stage_logger:
        errors.append(f"Helper methods using stage_logger: {list(helper_methods_with_stage_logger.keys())}")
        print(f"\n❌ ERROR: {len(helper_methods_with_stage_logger)} helper methods using stage_logger:")
        for method, line_nums in helper_methods_with_stage_logger.items():
            print(f"   - {method}: lines {line_nums[:5]}")
    else:
        print("✅ No helper methods using stage_logger")
    
    # Summary
    print("\n" + "=" * 60)
    if errors:
        print("❌ VALIDATION FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("✅ VALIDATION PASSED")
        print("\nAll stage methods have stage_logger initialized.")
        print("No helper methods incorrectly use stage_logger.")
        return 0

if __name__ == "__main__":
    sys.exit(validate_stage_logger())
