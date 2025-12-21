# Basic Synchronous Example

This example demonstrates the basic usage of the Replane Python SDK with the synchronous client.

## Prerequisites

- Python 3.10 or higher
- A running Replane server
- An SDK key from your Replane dashboard

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Update configuration in `main.py`:

```python
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "your_sdk_key_here"
```

## Run

```bash
python main.py
```

## What This Example Shows

- Using the `Replane` with context manager
- Reading boolean feature flags
- Reading numeric configuration values
- Passing context for override evaluation
- Using default values for missing configs
- Manual client lifecycle management
- Non-blocking connection pattern
