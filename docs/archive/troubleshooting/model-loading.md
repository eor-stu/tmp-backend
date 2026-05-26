---
name: GGUF 模型加载故障排除
category: reference
field: code
description: 模型文件不存在、CUDA 版本、GPU 内存等问题的诊断与解决
date: 2026-05-26
---
# Model Loading Troubleshooting

This guide covers common issues with GGUF model loading in `ufc-2026-backend`.

## Common Issues

### 1. Model File Not Found

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'model/xxx.gguf'
```

**Diagnosis:**
```python
from pathlib import Path
model_path = Path("model")
print(f"Model dir exists: {model_path.exists()}")
print(f"Contents: {list(model_path.glob('*.gguf'))}")
```

**Solutions:**
1. Verify model file exists in `model/` directory
2. Check filename matches config (`.llm.json`, `.infer.json`)
3. Ensure `.gguf` extension is correct

### 2. Wrong CUDA Version

**Symptom:**
```
AssertionError: llama.cpp compiled without CUDA support
```

**Diagnosis:**
```bash
nvcc --version  # Check CUDA version
nvidia-smi       # Check GPU driver
```

**Solutions:**
1. Reinstall llama-cpp-python with CUDA:
```bash
CMAKE_ARGS="-DGGML_CUDA=ON" pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python-cu12/
```

2. Or use CPU fallback (slow):
```python
# In .llm.json, set n_gpu_layers to 0
{
    "n_gpu_layers": 0
}
```

### 3. Insufficient GPU Memory

**Symptom:**
```
CUDA out of memory. Tried to allocate...
```

**Solutions:**
1. Use a smaller/quantized model (Q4_K_M instead of Q8)
2. Reduce context size in `.infer.json`:
```json
{
    "n_ctx": 8192  // Reduce from 32768
}
```
3. Close other GPU applications
4. Use CPU inference temporarily

### 4. Invalid Model Format

**Symptom:**
```
llama_model_loader: failed to load model
```

**Diagnosis:**
```bash
# Check model file integrity
file model/xxx.gguf
ls -lh model/xxx.gguf
```

**Solutions:**
1. Re-download the model
2. Verify model is valid GGUF format
3. Check file isn't corrupted (md5sum)

### 5. Config File Issues

**Symptom:**
```
KeyError: 'n_gpu_layers'
```

**Diagnosis:**
Check both `.llm.json` and `.infer.json` exist and are valid JSON:
```bash
cat model/xxx.llm.json
cat model/xxx.infer.json
```

**Solutions:**
1. Ensure both config files exist
2. Valid JSON syntax (no trailing commas)
3. Check required keys are present

## Verification Steps

### 1. Check Environment

```python
from src.utils import ROOT_DIR
print(f"Project root: {ROOT_DIR}")
print(f"Model dir: {ROOT_DIR / 'model'}")

import os
print(f"CUDA available: {os.environ.get('CUDA_VISIBLE_DEVICES')}")
```

### 2. Test Model Loading

```python
from src.llm.llama import load_model, get_model_and_cfg

# Load model
result = load_model("test", "LFM2.5-1.2B-Instruct-Q4_K_M")
print(f"Load result: {result}")

# Get model
result = get_model_and_cfg("test")
if result.success:
    model, config = result.value
    print(f"Model loaded: {model}")
    print(f"Config: {config}")
```

### 3. Test Inference

```python
from src.llm.llama import get_model_and_cfg

result = get_model_and_cfg("test")
if result.success:
    model, config = result.value
    response = model.create_chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        **config
    )
    print(f"Response: {response}")
```

## Model Configuration Reference

### .llm.json (llama.cpp parameters)

```json
{
    "n_gpu_layers": 0,        // GPU layers (0 for CPU)
    "seed": "default",        // Random seed
    "n_ctx": 32768,           // Context size
    "n_threads": 4,           // CPU threads
    "flash_attn": true,        // Flash attention
    "chat_format": "chatml",  // Chat format
    "verbose": false           // Verbose output
}
```

### .infer.json (generation parameters)

```json
{
    "temperature": 0.1,       // Creativity (0.0-1.0)
    "top_k": 50,              // Top-k sampling
    "logit_bias": {}          // Logit bias overrides
}
```

## Getting Help

If issues persist:

1. Check whisper.cpp docs: `whisper_cpp_deploy_wsl2_cuda.md`
2. Check llama-cpp-python documentation
3. Verify GPU compatibility with CUDA version
4. Try CPU fallback for debugging
