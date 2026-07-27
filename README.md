# Home Assistant Custom Integrations

A repository for Home Assistant custom components.

## Local Setup

Requires Python 3.14 or higher.

Create the virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install development and testing dependencies:

```bash
pip install -e .[dev]
```

## Testing & Code Quality

Run these checks locally to validate changes before committing:

### 1. Type Checking

```bash
make type
```

### 2. Formatting & Import Sorting Check

```bash
make format
```
