#!/usr/bin/env python3
"""
Cache Test Runner

Simple script to run cache-specific unit tests with proper configuration.
"""

import subprocess
import sys
import os

def run_cache_tests():
    """Run cache unit tests with appropriate configuration."""
    print("🧪 Running Cache Service Unit Tests...")
    print("=" * 50)
    
    # Change to project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run pytest with cache-specific configuration
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_cache.py",
        "-v",
        "--tb=short",
        "--disable-warnings",
        "--no-cov"  # Disable coverage for simpler output
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ All cache tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Some cache tests failed (exit code: {e.returncode})")
        return e.returncode
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Error running tests: {e}")
        return 1

def run_specific_test(test_name):
    """Run a specific cache test."""
    print(f"🧪 Running specific cache test: {test_name}")
    print("=" * 50)
    
    cmd = [
        sys.executable, "-m", "pytest",
        f"tests/test_cache.py::{test_name}",
        "-v",
        "--tb=short",
        "--disable-warnings",
        "--no-cov"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ Test {test_name} passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Test {test_name} failed (exit code: {e.returncode})")
        return e.returncode

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        exit_code = run_specific_test(test_name)
    else:
        # Run all cache tests
        exit_code = run_cache_tests()
    
    sys.exit(exit_code) 