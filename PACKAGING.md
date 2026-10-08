# Building and Publishing PUPRemote

## Local Installation

Install the package locally for development:

```bash
pip install -e .
```

Or from a built wheel:

```bash
pip install dist/pupremote-2.1.3-py3-none-any.whl
```

## Building Distributions

Build source and wheel distributions:

```bash
rm -rf dist/ && python -m build
```

## Publishing to PyPI

### Test PyPI (Recommended First)

```bash
python -m twine upload --repository testpypi dist/*
```

Then test installation:

```bash
pip install --index-url https://test.pypi.org/simple/ pupremote
```

### Production PyPI

```bash
python -m twine upload dist/*
```

## Package Contents

The PyPI package includes:

- `pupremote.py` - Main library (hub-side and sensor-side implementations)
- `lpf2.py` - LPF2 protocol implementation (dependency)

Users can then import:

```python
from pupremote import PUPRemote, PUPRemoteHub, PUPRemoteSensor
import lpf2
```

## Verifying the Package

Check wheel contents:

```bash
python -m zipfile -l dist/*.whl
```

Check metadata:

```bash
python -m twine check dist/*
```
