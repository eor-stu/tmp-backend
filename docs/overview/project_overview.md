---
name: 项目概览
category: concept
field: global
description: AI 助手在项目中建立世界观的基准文档
date: 2026-05-26
---

# 项目概览

本文档为 AI 助手在 `ufc-2026-backend` 项目中执行任何任务前建立的"世界观"。如果世界观不正确，后续所有构建都会偏离目标。

## 1. 项目做什么

**UFC 2026 Backend** 是一个医院导航与智能分诊系统后端，提供：

| 能力 | 描述 |
|------|------|
| **语音交互** | STT (Whisper) + TTS (Piper) 实现语音输入输出 |
| **诊室选择** | AI Agent 根据患者症状选择合适诊室 |
| **路线规划** | 根据目的地和用户需求（如"现在去洗手间"、"看病前"）生成/修改医院导航路线 |
| **视觉导航** | OpenCV 黑线巡线 + PID 差速控制 + 路口检测，将路径指令转为实际行驶 |
| **机器人控制** | `/car/*` API 接口实现底盘运动控制 |

### 核心用户流程

```
用户（语音）→ STT → LLM 推理 → Route Patcher → Map + Dijkstra → Vision Navigator → 车辆控制 → TTS → 用户

## 2. 项目边界

| 边界 | 描述 |
|------|------|
| **范围内** | 单机器人室内导航、语音咨询、本地/云端 LLM 推理 |
| **范围外** | 多机器人协作、实时地图更新、传感器融合 |
| **外部依赖** | whisper.cpp（语音）、llama.cpp（本地 LLM）、DeepSeek API（云端 LLM） |
| **输出形式** | REST API + 音频文件。无前端或移动端组件 |

### 这个项目不是什么

- 不是通用聊天机器人
- 不是地图渲染系统
- 不是实时追踪系统
- 不是医疗诊断系统（仅提供位置/路线建议）

## 3. 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **AI 框架** | DSPy | 基于 Signature 的任务定义，ChainOfThought 推理 |
| **本地 LLM** | llama-cpp-python + GGUF（Q4 量化） | CUDA 加速的离线推理 |
| **云端 LLM** | DeepSeek API（通过 litellm） | 本地 GPU 不可用时的在线推理 |
| **STT** | whisper.cpp | 支持 CUDA 的语音转文字 |
| **TTS** | Piper | 使用 RNN-T 模型实现文字转语音 |
| **后端** | FastAPI + uvicorn + Pydantic | REST API + 运行时类型验证 |
| **测试** | pytest + pytest-cov | 80%+ 覆盖率的单元/集成测试 |

### 核心依赖

```
# AI / LLM
dspy
litellm
llama-cpp-python

# 后端
fastapi
uvicorn
pydantic

# 工具
python-dotenv
```

## 4. 核心入口点

| 文件/目录 | 职责 |
|-----------|------|
| `src/main.py` | FastAPI 入口，lifespan 管理（whisper-server、LLM 配置） |
| `src/map/` | 医院地图模块，节点建图、最短路径、路径→小车指令 |
| `src/triager/` | 分诊 + 路线修改 AI Agent |
| `src/vision/` | 视觉巡线导航（黑线检测 + PID 控制 + 路口识别 + 状态机） |
| `src/car/` | 机器人底盘控制（mock 模式） |
| `src/voice/` | 语音模块 STT/TTS |
| `src/llm/` | LLM 适配器（llama.cpp / DeepSeek） |

### 探索指南

项目结构通过以下方式自行探索：

- `Bash ls src/` — 列出顶层模块目录
- `Glob "src/**/*.py"` — 了解所有模块文件
- `Grep "def " src/**/*.py` — 快速了解各模块暴露的函数
- `Read src/main.py` — 了解应用入口和路由注册

关键配置文件：`.env`、`requirements.txt`

### 核心入口点详解

#### 主应用 (`src/main.py`)

FastAPI 应用入口，负责 lifespan 管理（whisper-server、LLM 配置初始化）、CORS 配置和路由器注册。

#### 地图模块 (`src/map/`)

医院地图管理模块，提供：
- **节点查询**：获取所有 main 节点 ID、名称与描述
- **运行时图构建**：根据坐标邻近关系（`|dx|+|dy| == 1`）自动构建 edges，无需在 JSON 中手动维护
- **最短路径**：Dijkstra 算法计算两节点间最短路径
- **路径→小车指令**：`get_commands(start, end)` 将路径直接转为 `[{action, param}]` 控制指令序列

地图数据惰性加载到内存，edges 在 `Map` 对象创建时自动构建。

#### 分诊与路线修改 (`src/triager/`)

AI Agent 核心模块，负责：
- **诊室选择**：根据患者症状选择合适诊室
- **路线修改**：根据用户临时需求（如"中途去洗手间"）调整既定路线

#### 视觉导航 (`src/vision/`)

视觉巡线导航模块，将路径指令转为实际行驶行为。核心组件：

- **LineDetector**：OpenCV 黑线检测 — ROI 裁剪（下半 60%）→ 灰度 → 高斯模糊 → 自适应阈值 → 轮廓查找 → 偏差计算（-1.0~+1.0）；`detect_upper()` 检查上半 40% 用于终点判定
- **PIDController**：偏差 → 差速转向（Kp=30, Ki=1.0, Kd=10），支持抗积分饱和；丢线时 deviation=0 直行等待
- **IntersectionDetector**：加权投票制 — 轮廓面积超过固定基线 1.5 倍得 2 票 + Sobel 水平边缘检测得 1 票 → 累积 >= 3 票且包含面积尖峰触发，水平信号 2 帧保持防闪烁
- **Navigator**：状态机（FOLLOW_LINE → CROSSING → TURNING → DONE），消费 `get_commands()` 输出 `[turn(180), forward(N), turn(angle), arrive]` 指令序列；过路口用 `car.control.forward(0.15)`（基于 V_FORWARD=0.186 m/s），转向用 `car.control.turn(angle)`（基于 V_ROTATE=75.8 deg/s）；final_approach 模式：最后一段巡线结束后自动进入，仅靠终点检测判定到达；终点检测：上半 40% 连续 3 帧无黑线 → 自动停车

Mock 模式支持：
- 摄像头不可用 → 强制底盘也 mock，每 100 tick 自动生成虚拟路口
- 底盘不可用 → 仅日志记录电机指令；过路口/转向阶段 `time.sleep(2)` 模拟耗时

API：`POST /vision/start_navigate`, `POST /vision/stop`, `GET /vision/status`

#### 车辆控制 (`src/car/`)

机器人底盘控制模块，提供前进、后退、转向、停止等基础操作。当前实现为 mock 模式（仅记录日志），待硬件适配后替换为真实控制指令。

#### 语音模块 (`src/voice/`)

语音输入输出模块：
- **STT**：通过 whisper.cpp 将语音转为文字
- **TTS**：通过 Piper 将文字转为语音

#### LLM 适配器 (`src/llm/`)

统一的大语言模型接口，支持本地 llama.cpp 推理和 DeepSeek 云端 API，通过 DSPy 框架调用。

### 地图数据结构

医院地图（`src/map/map.json`）为 nodes-only 的网格设计，不再手动维护 edges：

| 节点类型 | 含义 | 示例 |
|----------|------|------|
| `main` | 患者实际访问的位置 | `entrance`, `surgery_clinic`, `toilet` |
| `nav` | 导航路径点（网格交叉口） | `road_1_1`, `road_2_3` |

Edges 在运行时由 `Map.model_post_init` 自动构建：任意两节点满足 `|dx|+|dy| == 1`（Manhattan 相邻）即连边，cost 固定为 1。nav 节点在 JSON 中共享 `"road"` 作为 id，加载时自动重命名为 `road_{x}_{y}`。

当未提供 `origin_route` 时，`patch_route()` 生成默认路线：按 `(y, x)` 坐标排序 map.json 中所有 `main` 节点，取前 6 个作为标准访问顺序。

---

## 状态：已稳定

此概览描述了项目的完整能力边界，已涵盖核心模块功能和安全保障要求。

### 待扩展内容

- **平台/模块状态**：各模块完成度、已知限制
- **架构与运行时约束**：纯函数要求、跨运行时差异