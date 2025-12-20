# Replane Python SDK Examples

This directory contains example projects demonstrating how to use the Replane Python SDK for feature flags and remote configuration.

## Examples

| Example | Description |
|---------|-------------|
| [basic-sync](./basic-sync) | Basic usage with the synchronous client |
| [basic-async](./basic-async) | Basic usage with the asynchronous client |
| [flask-integration](./flask-integration) | Integration with Flask web framework |
| [fastapi-integration](./fastapi-integration) | Integration with FastAPI framework |
| [django-integration](./django-integration) | Integration with Django framework |
| [testing](./testing) | How to test code that uses Replane |
| [feature-flags](./feature-flags) | Various feature flag patterns and use cases |

## Quick Start

Each example is a standalone project that can be copied and used as a starting point. To run any example:

1. Navigate to the example directory:
   ```bash
   cd examples/basic-sync
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Update the configuration (BASE_URL and SDK_KEY) in the main file

5. Run the example:
   ```bash
   python main.py  # or app.py for web examples
   ```

## Example Descriptions

### basic-sync

Demonstrates the fundamental usage of `SyncReplaneClient`:
- Context manager usage
- Reading feature flags and configs
- Passing context for override evaluation
- Default values
- Manual lifecycle management

### basic-async

Demonstrates the asynchronous `AsyncReplaneClient`:
- Async context manager usage
- Real-time update subscriptions
- Async callbacks
- Integration with asyncio applications

### flask-integration

Shows how to integrate Replane with a Flask application:
- Application startup/shutdown lifecycle
- Building context from request headers
- Feature flags in route handlers
- Dynamic rate limits and upload sizes

### fastapi-integration

Shows how to integrate Replane with FastAPI:
- Lifespan handler for async client
- Dependency injection
- Pydantic response models
- Middleware for maintenance mode
- Health check endpoints

### django-integration

Shows how to integrate Replane with Django:
- App initialization in `AppConfig.ready()`
- Singleton client pattern
- Custom middleware for maintenance mode
- Class-based views with feature flags
- Health check endpoints

### testing

Demonstrates testing patterns using `InMemoryReplaneClient`:
- Simple test configurations
- Override rules in tests
- Pytest fixtures
- Testing services with dependency injection
- Subscription testing

### feature-flags

Comprehensive examples of feature flag patterns:
- Basic on/off toggles
- User targeting
- Plan-based limits
- Regional features
- Gradual rollouts
- Environment configs
- Complex conditions
- Real-time updates

## Requirements

- Python 3.10 or higher
- A Replane server (for non-testing examples)
- An SDK key from your Replane dashboard

## Getting Help

- [Replane Python SDK Documentation](https://github.com/replane-dev/replane-python)
- [Report Issues](https://github.com/replane-dev/replane-python/issues)
