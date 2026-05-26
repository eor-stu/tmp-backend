---
name: Navigator 最终接近与 arrive 动作支持
category: adr
field: code
description: 新增 arrive 动作和 _final_approach 模式，使 Navigator 在完成所有转向后能可靠地到达 main 节点位置
date: 2026-05-26
---

# 015: Navigator 最终接近与 arrive 动作支持

**日期**: 2026-05-26
**状态**: 已通过
**决策者**: n1ghts4kura

## 背景

旧版 Navigator 在完成最后一次转向后直接进入 DONE 状态，车停在最后一个路口上，无法到达实际的 main 节点目的地（如 pharmacy、toilet 等）。需要在指令序列末尾增加"最终接近"阶段——从最后一个路口巡线行进到目的地，依赖终点检测判定到达。

此外，`get_commands()` 重写后（ADR-014）在指令序列末尾追加了 `arrive` 动作，Navigator 需要能解释并执行它。

约束：
- 最终接近阶段不应被路口检测干扰（目的地附近可能有导引线交叉）
- 必须复用已有的终点检测机制（画面上半 40% 连续 3 帧丢线）
- Mock 模式下也要能模拟终点到达

## 考虑的方案

| 方案 | 可靠性 | 实现复杂度 | 选否原因 |
|------|--------|------------|----------|
| A: _final_approach 标志 + 关闭路口检测 + 终点检测判定 | 高（终点检测已验证） | 低 | **选择** |
| B: 在最后一个路口直接 forward(距离) 开环前进 | 低（依赖距离估算） | 低 | 无闭环反馈，距离误差累积 |
| C: 路口检测识别 main 节点特征 | 低（main 节点无统一视觉特征） | 高 | 需要新的视觉检测逻辑 |

## 决策

**选择:** 方案 A

## 理由

1. **复用已有机制**：终点检测（ADR-012）已定义——巡线过程中画面上半 40% 连续 3 帧无黑线即判定到达，无需新增视觉模块
2. **关闭路口检测**：最终接近阶段跳过路口检测，避免目的地附近的导引线交叉触发误判
3. **实现简洁**：新增一个布尔标志 + 一个状态设置函数 + 三个 tick 函数中的 arrive 检查分支

## 架构

### _final_approach 模式

```
_final_approach = False (默认):
  FOLLOW_LINE → 路口检测 → CROSSING → TURNING → ...

_final_approach = True:
  FOLLOW_LINE → 终点检测 → DONE
  （路口检测完全跳过，IntersectionDetector 不再工作）
```

### arrive 动作传播路径

```
get_commands() → [{...}, {"action": "arrive", "param": 0.0}]
                        ↓
Navigator.run()          → 检查首条指令是否为 turn(180)
_tick_crossing()         → forward 段完成后检查 arrive → _enter_final_approach()
_tick_turning()          → 转向完成后检查 arrive → _enter_final_approach()
_get_next_turn()         → 遇到 arrive 返回 None（非 turn）
```

### _enter_final_approach()

```python
def _enter_final_approach(self) -> None:
    self._final_approach = True
    self._intersections_target = 0
    self._intersections_passed = 0
    self._intersection_detector.reset()
    self._pid.reset()
    self._tick_count = 0
    self._state = NavState.FOLLOW_LINE
```

进入后：
- 路口计数器归零，路口检测器重置
- 状态直接切换到 FOLLOW_LINE
- `_tick_follow_line_real()` 中 `if not self._final_approach:` 跳过整个路口检测分支
- 终点检测（`detect_upper` + 连续丢线计数）正常运作，触发 DONE

### Mock 模式

Mock 模式下最终接近模拟：进入 `_final_approach` 后，`_tick_follow_line_mock()` 在 `MOCK_INTERSECTION_TICKS * 2` 个 tick 后直接触发 DONE，模拟抵达终点。

### run() 初始 turn(180)

当指令序列首条为 `turn(180)` 时，`run()` 直接将其作为初始转身执行——设置 `_pending_turn_angle` 并进入 TURNING 状态，跳过 IDLE/FOLLOW_LINE 的预热。这处理了 `get_commands()` 输出首条必为 `turn(180)` 的情况。

## 状态机更新

```
IDLE → TURNING (初始 180°)
         ↓
    FOLLOW_LINE ⇄ CROSSING ⇄ TURNING
         ↓                      ↓
    _final_approach       _final_approach
         ↓                      ↓
    FOLLOW_LINE ──(终点检测)──→ DONE
```

## 具体变更

| 文件 | 变更 |
|------|------|
| `src/vision/navigator.py` | 新增 `_final_approach` 标志、`_enter_final_approach()` 方法；`_tick_crossing`/`_tick_turning`/`_get_next_turn` 增加 arrive 处理；`_tick_follow_line_real` 在 final approach 下跳过路口检测；`_tick_follow_line_mock` 增加 final approach 模拟；`run()` 处理初始 turn(180) |

## 放弃的替代方案

- **方案 B**: 开环 `forward(距离)` 无反馈，距离估算误差会导致未到达或过冲
- **方案 C**: main 节点无统一视觉特征，需要为每个目的地单独标注，不通用

## 后续行动

- [ ] 实车验证 final approach 阶段终点检测的可靠性（在不同光照条件下）
- [ ] 确认 arrive 后终点检测不会因远处线条被误触发
