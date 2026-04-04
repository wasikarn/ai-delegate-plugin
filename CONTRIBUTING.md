# Contributing to AI Delegate Plugin

Thank you for your interest in contributing to the AI Delegate Plugin! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- pip or uv package manager

### Installation

1. Fork the repository
2. Clone your fork:

   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-delegate-plugin.git
   cd ai-delegate-plugin
   ```

3. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

4. Install development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=ai_delegate

# Run specific test file
pytest tests/test_complexity.py -v
```

## Code Style

This project uses:

- **Ruff** for linting and formatting
- **MyPy** for type checking
- **pytest** for testing

### Before Submitting

1. Run linting:

   ```bash
   ruff check ai_delegate/
   ruff format ai_delegate/
   ```

2. Run type checking:

   ```bash
   mypy ai_delegate/
   ```

3. Ensure tests pass:

   ```bash
   pytest tests/ -v
   ```

## Pull Request Process

1. Create a feature branch from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the code style

3. Add tests for new functionality

4. Update documentation if needed

5. Commit with conventional commit messages:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `test:` for tests
   - `refactor:` for refactoring

6. Push to your fork and create a pull request

## Adding New Domain Experts

To add a new domain expert agent:

1. Create `agents/your-expert.md` following the pattern in existing agents
2. Add expert configuration to `ai_delegate/config.py`
3. Update `ai_delegate/constants.py` with any new constants
4. Add tests for the new expert

## Adding New CLI Commands

To add a new CLI command:

1. Add command logic to `ai_delegate/cli.py`
2. Update router if needed in `ai_delegate/router.py`
3. Add tests for the new command
4. Update documentation

## Project Structure

```
ai-delegate-plugin/
├── ai_delegate/          # Core Python package
│   ├── cli.py            # CLI entry point
│   ├── router.py         # Smart router
│   ├── supervisor.py     # Supervisor+Worker pattern
│   ├── constants.py      # Centralized constants
│   └── debate/           # Debate orchestration
├── agents/               # Agent definitions
├── skills/               # Skill definitions
├── hooks/                # Hook scripts
├── tests/                # Test files
└── docs/                 # Documentation
```

## Questions?

Open an issue for:

- Bug reports
- Feature requests
- Questions about contributing

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
