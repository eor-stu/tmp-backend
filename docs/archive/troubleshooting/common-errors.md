---
name: 常见错误处理指南
category: reference
field: code
description: DSPy、LLM、Python、JSON 等常见错误的诊断与解决
date: 2026-05-26
---
# Common Errors Guide

This guide covers common errors in `ufc-2026-backend` and how to resolve them.

## DSPy Errors

### InvalidSignatureError

**Error:**
```
dspy.exceptions.InvalidSignatureError
```

**Cause:** Signature missing required fields or malformed definition.

**Fix:**
```python
# Check all fields have proper annotations
class MySignature(dspy.Signature):
    input_field: str = dspy.InputField(desc="description")  # Type + Field
    output_field: str = dspy.OutputField(desc="description")

# Check collector receives all inputs
result = collector(input_field=value)  # All inputs must be passed
```

### FieldNotFoundError

**Error:**
```
AttributeError: 'X' object has no attribute 'field_name'
```

**Cause:** Trying to access output field that wasn't in OutputField definition.

**Fix:**
```python
class MySignature(dspy.Signature):
    # ... input fields ...
    output_field: str = dspy.OutputField(desc="description")

result = collector(...)
print(result.output_field)  # Access correct field name
```

## LLM Errors

### ModelNotFoundError

**Error:**
```
FileNotFoundError: Model file not found
```

**Fix:**
1. Verify model file in `model/` directory
2. Check config filenames match:
   - `model_name.gguf`
   - `model_name.llm.json`
   - `model_name.infer.json`

### ContextLengthExceeded

**Error:**
```
llama_cpp.LlamaRuntimeError: context length exceeded
```

**Fix:**
```json
// In .infer.json, reduce n_ctx
{
    "n_ctx": 8192
}
```

### CUDANotAvailable

**Error:**
```
AssertionError: llama.cpp compiled without CUDA support
```

**Fix:**
1. Check GPU: `nvidia-smi`
2. Check CUDA: `nvcc --version`
3. Install with CUDA support:
```bash
CMAKE_ARGS="-DGGML_CUDA=ON" pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python-cu12/
```

## Python Errors

### ModuleNotFoundError

**Error:**
```
ModuleNotFoundError: No module named 'src'
```

**Fix:**
```bash
# Run from project root
cd /path/to/ufc-2026-backend
pytest

# Or ensure PYTHONPATH is set
export PYTHONPATH=/path/to/ufc-2026-backend
```

### ImportError (Circular)

**Error:**
```
ImportError: cannot import name 'X' from 'Y'
```

**Cause:** Circular import between modules.

**Fix:** Restructure imports - move shared utilities to separate module.

## JSON Errors

### JSONDecodeError

**Error:**
```
json.JSONDecodeError: Expecting value
```

**In route_patcher/requirement_collector:** Model output may have formatting issues.

**Fix:** Code includes fallback parsing:
```python
try:
    data = json.loads(result.requirements)
except json.JSONDecodeError:
    # Try with single quotes replaced
    data = json.loads(result.requirements.replace("'", '"'))
```

### InvalidJSONFormat

**Cause:** DSPy model returns text that isn't valid JSON.

**Fix:** Improve instructions in Signature:
```python
collector = dspy.ChainOfThought(Signature)

result = collector(
    instructions="Output valid JSON only, no markdown fences",
    ...
)
```

## Type Errors

### MissingTypeAnnotation

**Error:**
```
TypeError: Missing type annotation
```

**Fix:** Add type annotations to all function signatures:
```python
# Bad
def function(param):
    ...

# Good
def function(param: str) -> Result:
    ...
```

## Path Errors

### PathNotFound

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory
```

**Fix:** Use `ROOT_DIR` from `src/utils.py`:
```python
from src.utils import ROOT_DIR

model_path = ROOT_DIR / "model" / "file.gguf"
if not model_path.exists():
    raise FileNotFoundError(f"Model not found: {model_path}")
```

## FastAPI Errors (if using)

### ValidationError

**Error:**
```
pydantic.ValidationError
```

**Cause:** Request data doesn't match expected format.

**Fix:**
```python
from pydantic import BaseModel

class RequestModel(BaseModel):
    field: str

@app.post("/endpoint")
async def handler(data: RequestModel):
    ...
```

## Debugging Workflow

1. **Read the full error traceback** - shows exact line and call stack
2. **Check error type** - matches list above for quick fixes
3. **Enable debug logging**:
   ```python
   logger.setLevel(logging.DEBUG)
   ```
4. **Run single test** to isolate:
   ```bash
   pytest test/test_file.py::test_name -vv -s
   ```

## Getting Help

When stuck:
1. Review DSPy signature design ADR: [changelog/005_dspy_signature_design.md](../../changelog/005_dspy_signature_design.md)
2. Check FastAPI docs at [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
3. Review existing tests in `test/` for patterns
4. Check the [NODE_CREATE.md](../../../src/NODE_CREATE.md) developer guide for module creation patterns
