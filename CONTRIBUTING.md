# Contributing to Replane Python SDK

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

### Prerequisites

- **Python**: Version 3.10 or greater

### Clone the Repository

```sh
git clone https://github.com/replane-dev/replane-python.git
cd replane-python
```

### Set Up Development Environment

Create and activate a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install the package in development mode with dev dependencies:

```sh
pip install -e ".[dev]"
```

## Development

### Run Tests

```sh
pytest
```

With coverage:

```sh
pytest --cov=replane
```

### Lint

```sh
ruff check .
```

### Type Check

```sh
mypy replane
```

### Format

```sh
black .
isort .
```

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Ensure tests pass: `pytest`
5. Ensure linting passes: `ruff check .`
6. Ensure type checking passes: `mypy replane`
7. Commit your changes with a descriptive message
8. Push to your fork and submit a pull request

## Reporting Issues

Found a bug or have a feature request? Please [open an issue](https://github.com/replane-dev/replane-python/issues) on GitHub.

## Community

Have questions or want to discuss Replane? Join the conversation in [GitHub Discussions](https://github.com/orgs/replane-dev/discussions).

## License

By contributing to Replane Python SDK, you agree that your contributions will be licensed under the MIT License.
