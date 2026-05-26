---
name: 文档索引
category: infra-rule
field: global
description: 快速索引 docs/ 中的各类规则文档
date: 2026-05-26
---

# 文档索引

> 本索引提供 docs/ 目录中所有规则文档的快速定位，按用途分类。

---

## 1. General Rule（通用规则）

文档基础设施规则，定义文档元数据标准与 Memory Bank 管理原则。

### 1.1 文档基础设施

| 文件 | category | 用途 |
|------|----------|------|
| [RULE.md](./RULE.md) | `infra-rule` | 定义 frontmatter Schema、Category/Field 分类体系、修改同步要求 |
| [overview/project_overview.md](./overview/project_overview.md) | `concept` | AI 世界观基线，定义项目范围、技术栈、核心能力 |
| [PRINCIPLE.md](./PRINCIPLE.md) | `infra-rule` | 给 Agent 的忠言：Think Before Coding、Simplicity First、Surgical Changes、Goal-Driven Execution |

### 1.2 Memory Bank

| 文件 | category | 用途 |
|------|----------|------|
| [memory/RULE.md](./memory/RULE.md) | `infra-rule` | Memory Bank 修改约束：时效性检查、工作方向命名（名词+动词）、7 步更新流程 |
| [memory/memory.md](./memory/memory.md) | `concept` | 当前 AI 会话上下文快照：工作方向、具体任务、任务状态 |

---

## 2. Specific Rule（项目规则）

项目开发规范，定义代码风格、错误处理、安全策略。

### 2.1 安全策略

| 文件 | category | 核心要点 |
|------|----------|----------|
| [rule/SECURITY.md](./rule/SECURITY.md) | `policy` | 铁律：安全非审查而是防御；禁止日志中出现密码/Token/手机号/身份证；零信任输入；最小权限 |

### 2.2 代码规范

| 文件 | category | 核心要点 |
|------|----------|------|
| [rule/code/coding_style.md](./rule/code/coding_style.md) | `policy` | snake_case（文件/函数/变量）、PascalCase（类/类型）、UPPER_SNAKE_CASE（常量）；类型注解强制；函数≤50 行、文件≤800 行；禁止 print() 使用 logger |
| [rule/code/error_handling.md](./rule/code/error_handling.md) | `policy` | 铁律：使用 Result Type 而非异常处理业务失败；Result 字段：success（必填）、value、warn、error；DSPy 输出不包装为 Result |

### 2.3 TDD 工作流

| 文件 | category | 核心要点 |
|------|----------|------|
| [rule/TDD.md](./rule/TDD.md) | `guide` | 铁律：没有失败测试 = 没有生产代码；5 阶段循环：RED → VERIFY RED → GREEN → VERIFY GREEN → REFACTOR；80%+ 覆盖率要求；测试命名规范（动词+场景+预期）；AAA 结构（Arrange-Act-Assert） |
| [rule/calibration_runbook.md](./rule/calibration_runbook.md) | `guide` | Vision 巡线导航标定操作手册：7 步标定流程、脚本用法、参数对照、数据分析反馈模板 |

---

## 3. ADR（架构决策记录）

| 文件 | category | 决策内容 |
|------|----------|----------|
| [changelog/001_tts_solution.md](./changelog/001_tts_solution.md) | `adr` | 选用 Piper TTS 作为树莓派本地离线中文 TTS 方案 |
| [changelog/002_coral_tpu_tts_incompatible.md](./changelog/002_coral_tpu_tts_incompatible.md) | `adr` | Coral TPU 与 TTS 引擎不兼容，放弃该方案 |
| [changelog/003_result_type.md](./changelog/003_result_type.md) | `adr` | 采用 Result Type 模式进行错误传播 |
| [changelog/004_logging.md](./changelog/004_logging.md) | `adr` | 使用 `src/logger.py` ColoredFormatter 统一日志 |
| [changelog/005_dspy_signature_design.md](./changelog/005_dspy_signature_design.md) | `adr` | 任务类型相关的 Signature 描述优化策略 |
| [changelog/006_model_loading_troubleshooting.md](./changelog/006_model_loading_troubleshooting.md) | `adr` | 模型加载问题排查记录 |
| [changelog/007_common_errors.md](./changelog/007_common_errors.md) | `adr` | 常见错误处理记录 |
| [changelog/008_tts_research.md](./changelog/008_tts_research.md) | `adr` | TTS 研究进展 |
| [changelog/009_model_troubleshooting.md](./changelog/009_model_troubleshooting.md) | `adr` | 模型问题排查记录 |
| [changelog/010_stt_deployment.md](./changelog/010_stt_deployment.md) | `adr` | STT 部署方案 |
| [changelog/011_map_runtime_graph.md](./changelog/011_map_runtime_graph.md) | `adr` | Map 模块运行时图构建重构，消除 car/map 循环依赖 |
| [changelog/012_vision_navigation.md](./changelog/012_vision_navigation.md) | `adr` | Vision 视觉巡线导航系统设计：PID + 路口检测 + 状态机 + Mock 双模式 |
| [changelog/013_calibration_workflow.md](./changelog/013_calibration_workflow.md) | `adr` | Vision 标定工作流设计：三脚本 + Claude Code 数据分析闭环 |
| [changelog/014_get_commands_rewrite.md](./changelog/014_get_commands_rewrite.md) | `adr` | get_commands() 按路口定义重写，不再把每个 road 节点当路口 |
| [changelog/015_navigator_final_approach.md](./changelog/015_navigator_final_approach.md) | `adr` | Navigator 新增 final_approach 模式，路口过完后依靠终点检测判定到达 |

---

## 4. Archive（归档文档）

历史研究、故障排查文档。

### 4.1 研究

| 文件 | 描述 |
|------|------|
| [archive/research/finetune-prompt.md](./archive/research/finetune-prompt.md) | 微调提示词研究 |
| [archive/research/piper-tts-raspberry-pi.md](./archive/research/piper-tts-raspberry-pi.md) | Piper TTS 树莓派部署研究 |
| [archive/research/tts-solution-comparison.md](./archive/research/tts-solution-comparison.md) | TTS 方案对比 |

### 4.2 故障排查

| 文件 | 描述 |
|------|------|
| [archive/troubleshooting/common-errors.md](./archive/troubleshooting/common-errors.md) | 常见错误排查指南 |
| [archive/troubleshooting/model-loading.md](./archive/troubleshooting/model-loading.md) | 模型加载问题排查 |
| [archive/troubleshooting/test-debugging.md](./archive/troubleshooting/test-debugging.md) | 测试调试指南 |

### 4.4 测试脚本

| 文件 | 用途 |
|------|------|
| [test_all_routes.py](../../test/test_all_routes.py) | 枚举所有主要地点间路线指令 |
| [test_full_path.py](../../test/test_full_path.py) | 端到端全路径导航测试 |
| [test_single_intersection.py](../../test/test_single_intersection.py) | 单路口导航测试 |

### 4.5 开发者文档

| 文件 | 用途 |
|------|------|
| [NODE_CREATE.md](../../src/NODE_CREATE.md) | Condition Collector 模块创建流程（402 行） |

### 4.3 Whisper

| 文件 | 描述 |
|------|------|
| [archive/whisper/edge-deploy-tech-spec.md](./archive/whisper/edge-deploy-tech-spec.md) | Whisper 边缘部署技术规格 |
| [archive/whisper/wsl2-cuda-deploy.md](./archive/whisper/wsl2-cuda-deploy.md) | WSL2 CUDA 部署指南 |

---

## 快速参考

| 需求 | 查阅 |
|------|------|
| 文档 frontmatter 格式 | [RULE.md](./RULE.md) |
| 项目整体认知 | [overview/project_overview.md](./overview/project_overview.md) |
| Memory Bank 修改流程 | [memory/RULE.md](./memory/RULE.md) |
| 代码命名规范 | [rule/code/coding_style.md](./rule/code/coding_style.md) |
| 错误处理标准 | [rule/code/error_handling.md](./rule/code/error_handling.md) |
| 安全红线 | [rule/SECURITY.md](./rule/SECURITY.md) |
| TDD 循环流程 | [rule/TDD.md](./rule/TDD.md) |
| 架构决策记录 | [changelog/](./changelog/) |
| Vision 标定流程 | [rule/calibration_runbook.md](./rule/calibration_runbook.md) |
| 故障排查 | [archive/troubleshooting/](./archive/troubleshooting/) |