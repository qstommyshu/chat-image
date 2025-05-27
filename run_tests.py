#!/usr/bin/env python3
"""
Simple test runner for session module tests.

This script runs the tests for the session module specifically,
avoiding some of the complex dependency imports from the main app.
"""

import sys
import os
import subprocess

def run_session_tests():
    """Run the session module tests."""
    # Set up environment
    test_env = os.environ.copy()
    test_env['PYTHONPATH'] = os.path.abspath('.')
    
    # Run pytest specifically for session tests
    cmd = [
        sys.executable, '-m', 'pytest', 
        'tests/test_session.py',
        '-v',
        '--tb=short'
    ]
    
    print("Running session module tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    result = subprocess.run(cmd, env=test_env)
    
    if result.returncode == 0:
        print("\n✅ All session tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {result.returncode}")
    
    return result.returncode

if __name__ == "__main__":
    exit_code = run_session_tests()
    sys.exit(exit_code) 