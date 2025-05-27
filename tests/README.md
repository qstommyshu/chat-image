# Tests

This directory contains unit tests for the application modules.

## Running Tests

### Session Module Tests

To run the session module tests specifically:

```bash
# Using the custom test runner (recommended)
python run_tests.py

# Or directly with pytest
source venv/bin/activate
python -m pytest tests/test_session.py -v
```

### All Tests

To run all tests in the project:

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

## Test Coverage

The session module tests provide comprehensive coverage for:

### CrawlSession Class

- ✅ Initialization with correct default values
- ✅ Message queuing functionality (add_message)
- ✅ Message ordering preservation (FIFO)
- ✅ Attribute modification after initialization

### SessionManager Class

- ✅ Initialization with empty state
- ✅ Configuration default values from Config class
- ✅ Session creation success scenarios
- ✅ Concurrent crawl limit enforcement
- ✅ Session retrieval (existing and non-existent)
- ✅ Namespace management (set/get operations)
- ✅ Thread-safe concurrent session creation
- ✅ Active vs inactive session status handling
- ✅ Namespace operations with reused session IDs

### Integration Tests

- ✅ Realistic crawl workflow simulation
- ✅ Error handling workflow
- ✅ Session lifecycle management

### Parameterized Tests

- ✅ Various active statuses counting toward limits
- ✅ Various inactive statuses not counting toward limits
- ✅ Session creation with different crawl limits

## Test Structure

```
tests/
├── __init__.py          # Makes tests a Python package
├── test_session.py      # Session module comprehensive tests
└── README.md           # This file
```

## Test Features

- **Threading Safety**: Tests verify that session management is thread-safe
- **Concurrency Control**: Tests ensure concurrent crawl limits are enforced properly
- **Edge Cases**: Tests cover error conditions and boundary cases
- **Mock Usage**: Tests use mocks to isolate dependencies (e.g., Config class)
- **Fixtures**: Pytest fixtures for clean test setup
- **Parameterized Tests**: Tests multiple scenarios with different inputs

## Dependencies

The test suite requires:

- `pytest` - Testing framework
- `pytest-mock` - Mocking utilities
- `pytest-asyncio` - Async testing support
- `pytest-cov` - Coverage reporting

Install with:

```bash
pip install pytest pytest-mock pytest-asyncio pytest-cov
```

## Configuration

Tests are configured via `pytest.ini` in the project root:

- Test discovery patterns
- Coverage reporting settings
- Output formatting options
- Custom markers for test categorization

## Current Test Metrics

- **28 tests** in the session module
- **100% pass rate**
- Covers all public methods and key scenarios
- Tests both success and failure paths
- Validates thread safety and concurrency controls
