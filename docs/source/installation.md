# Installation

## Requirements

- Python 3.10 or higher
- No additional dependencies for sync client
- `httpx` for async client (optional)

## Installing with pip

The Replane Python SDK is available on [PyPI](https://pypi.org/project/replane/).

### Basic installation (sync client only)

```bash
pip install replane
```

This installs the SDK with zero dependencies. The synchronous client uses only Python's standard library.

### With async support

```bash
pip install replane[async]
```

This adds [httpx](https://www.python-httpx.org/) as a dependency, enabling the `AsyncReplane` client.

## Installing from source

To install from source, first clone the repository:

```bash
git clone https://github.com/replane-dev/replane-python.git
cd replane-python
```

Then install in development mode:

```bash
pip install -e ".[dev]"
```

This installs all development dependencies including test and documentation tools.

## Verifying installation

You can verify the installation by checking the version:

```python
import replane
print(replane.VERSION)
```

Or from the command line:

```bash
python -c "import replane; print(replane.VERSION)"
```
