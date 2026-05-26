---
name: 文档系统 Memory Bank
category: infra-rule
field: global
description: 文档系统的内存存储，目的在于给AI快速投喂上下文
date: 2026-05-26
---

# 文档系统 Memory Bank

## Part 1: Currently Working

1. 工作整体方向 - `navigation` 分支：基于视觉的巡线导航系统

2. 当前具体任务 - Vision 巡线导航 Phase 7（2026-05-26）：get_commands 按路口重写完成、final_approach 模式已实现、命令格式修正，待硬件可用实车验证

3. 任务的作用：当前巡线系统使用加权投票制路口检测（面积尖峰 2 票 + Sobel 水平边缘 1 票）、自适应阈值二值化、标定物理接口过路口/转向（V_FORWARD=0.186 m/s, V_ROTATE=75.8 deg/s）、终点检测自动停车、final_approach 模式

4. 任务的工作目录：

- `src/vision/navigator.py`（362 行）、`src/vision/line_detector.py`（144 行）、`src/vision/pid_controller.py`（88 行）、`src/vision/intersection_detector.py`（88 行）、`src/vision/routes.py`、`src/car/control.py`

5. 任务开始时间：`2026-05-23`

6. 任务预期结束时间：`2026-05-30`

7. 任务状态：Phase 7 命令修正已完成，get_commands 和 Navigator final_approach 均已实现，待硬件可用实车验证

## Part 2: Context Snapshot

### Navigation 分支 (2026-05-26 Phase 7 更新)
- Vision 巡线导航系统：LineDetector (自适应阈值 + 终点检测) → PIDController (Ki=1.0) → IntersectionDetector (加权投票制) → Navigator (状态机 + final_approach + car/control.py 标定接口)
- 路口检测: 加权投票制 — 轮廓面积超过固定基线 1.5 倍得 2 票 + Sobel 水平边缘得 1 票 → 累积 >= 3 票且包含面积尖峰触发，2 帧水平信号保持防闪烁，慢速衰减（-1/帧）
- 过路口: `car.control.forward(0.15)` 前进 0.15m（基于 V_FORWARD=0.186 m/s 标定, 2026-05-24）
- 转向: `car.control.turn(angle)`（基于 V_ROTATE=75.8 deg/s 标定, 2026-05-24）
- 终点检测: 上半 40% 连续 3 帧无黑线 → 自动 DONE
- final_approach: 所有指令执行完毕后进入，仅靠终点检测判定到达，不再计数路口
- 状态机: FOLLOW_LINE → CROSSING → TURNING → ... → DONE
- Mock 模式: 摄像头不可用时强制底盘 mock，每 100 tick 生成虚拟路口；过路口/转向 mock 阶段 time.sleep(2)
- get_commands() 已重写：按功能性路口判定（4 方向邻接），输出 `[{action: "turn"|"forward"|"arrive", param: float}]`
- Navigator 消费指令序列: `turn(180) → forward(N) → turn(angle) → ... → arrive`
- 运动控制分离: 巡线差速保留直接电机控制，过路口/转向走 car/control.py 标定接口
- 标定工作流已设计（ADR-013），三脚本 + Claude Code 数据分析闭环，详见 docs/rule/calibration_runbook.md
- smbus2 替代 smbus，解决 I2C 兼容性

### Phase 1 结果 (2026-05-21) — 历史参考
- ClinicSelector: 82s → 9-15s (5-9x, CoT→Predict + docstring few-shot + config max_tokens=32)
- ConditionCollector: CoT→Predict, pipeline ~19s
- Pipeline 总时长 ~77-85s (未达 30s 目标)
- 最终使用模型：LFM2.5-1.2B-Instruct-Q4_K_M（替代 Qwen3.5-0.8B）

### DSPy 3.2.1 关键发现
- `instructions=` 直接被忽略，必须放 Signature docstring
- `max_tokens=` 直接被忽略，必须用 `config=dict(max_tokens=N)`

### 关键约束
- docs/ 内容会频繁变化，不适合硬编码路径
- AI 需要明确的入口指引，但不是完整清单

### 开发环境
- [ ] 使用 pyenv 管理 Python 3.11.2

### 已完成的改动 (累计)
- `src/triager/clinic_selector.py`: CoT→Predict, docstring 内嵌 few-shot, config max_tokens=32
- `src/triager/condition_collector.py`: CoT→Predict, docstring 指令, config max_tokens=128
- `src/triager/requirement_collector.py`: docstring 指令, config max_tokens=256
- `src/triager/route_patcher.py`: docstring 指令, config max_tokens=256, 删除 _format_locations
- `model/LFM2.5-1.2B-Instruct-Q4_K_M.*.json`: n_ctx=4096, chat_template.default, max_tokens=512, repeat_penalty=1.1
- `src/main.py`: 默认模型切换为 LFM2.5-1.2B, 新增 vision_router, 新增 face_router
- `src/vision/`: 完整巡线导航模块（6 个文件）
- `src/face/`: 人脸识别模块（user_db.py + routes.py）— face_recognition/dlib, POST /register + /face-recog
