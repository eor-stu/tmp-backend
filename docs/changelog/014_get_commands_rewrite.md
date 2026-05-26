---
name: get_commands 路口计数重写
category: adr
field: code
description: 将 forward 从"按距离行进"改为"按路口计数"，每个方向变化的路口都产生 turn 指令，并引入 arrive 终点接近动作
date: 2026-05-26
---

# 014: get_commands 路口计数重写

**日期**: 2026-05-26
**状态**: 已通过
**决策者**: n1ghts4kura

## 背景

旧版 `get_commands()` 将路径转化为 `forward(distance_meters)` 指令，每个 road 节点都被错误地当作路口处理。当路径上有连续直线 road 节点时，会在中间产生不必要的停车/转向行为。此外，旧版仅在路径的最后一个方向变化处产生一条 turn 指令，导致中间路口的转向被丢失。

约束：
- 必须正确处理地图上既有纯十字路口（4 个 nav 邻居），也有一侧通往 main 节点的走廊路口
- 地图为网格结构，相邻节点间距为单位距离（1m）
- 指令需被 `Navigator` 直接消费，格式为 `[{action, param}]`

## 考虑的方案

| 方案 | 路口判定 | 转向策略 | 选否原因 |
|------|----------|----------|----------|
| A: 四邻存在性 + 每个方向变化路口都转向 | 4 个正交相邻格存在任何类型节点（nav 或 main） | 所有方向变化的路口都产生 turn(angle) | **选择** |
| B: 纯 nav 四邻 + 仅最后转向 | 4 邻均为 nav 类型 | 只在最后一个方向变化处转弯 | 遗漏中间转向（旧行为） |
| C: 路段端点匹配 | 路径上的 nav 节点两两配对 | 只标记首尾 | 无法处理多段路径 |

## 决策

**选择:** 方案 A

## 理由

1. **四邻"存在性"判定更准确**：将 `_is_intersection` 从"4 邻均为 nav 类型"放宽为"4 邻存在任意类型节点（nav 或 main）"，正确覆盖走廊路口（一侧为 main 出口）
2. **所有方向变化都转**：消除"仅最后转向"的限制，路径上的每个方向变化路口都产生对应的 turn 指令
3. **forward 计路口非计米**：forward(2) 表示"经过 2 个路口"，语义与地图网格结构一致

## 三阶段设计

```
Phase 0: 初始动作 → turn(180)
  车停在起点 main 节点，面向远离道路方向，先 180° 转身面向道路

Phase 1: 路径分析 → 识别所有路口 + 所有方向变化
  - isect_indices: 路径上所有 _is_intersection 为真的节点索引
  - turns: 每个方向变化且所在节点为路口时的 (索引, 角度) 对

Phase 2: 构建动作序列 → forward(N) + turn(angle)
  - N = 自上个动作点以来（含当前 turn 所在路口）的路口数
  - 每个 turn 都独立产生一条 turn 指令
  - 无 turn 则所有路口进入一段 forward

Phase 3: 终点 → arrive
  标记进入最终接近模式，由 Navigator 依赖终点检测判定到达
```

## 路口判定变更

`_is_intersection` 判定逻辑：

```python
# 旧：4 邻必须均为 nav 类型
all(coord_to_node.get((x+dx, y+dy), {}).get("type") == "nav"
    for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)])

# 新：4 邻存在任意类型节点（nav 或 main）
for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
    if (x + dx, y + dy) not in coord_to_node:
        return False
return True
```

## 转向符号修正

`_get_relative_turn` 修正了旧版方向映射错误：

| diff | 含义 | 符号 | 原因 |
|------|------|------|------|
| 90 | 逆时针（east→north=90） | **-90** | 逆时针 = 左转 |
| 270 | 顺时针（east→south=270） | **+90** | 顺时针 = 右转 |

坐标空间：x 向东为正，y 向南为正。`_direction_to_degrees` 映射为 east=0, north=90, west=180, south=270。

## 使用示例

```
entrance → pharmacy:
  Path: entrance → road_2_7 → road_2_5 → pharmacy
  Intersections: road_2_7 (#1), road_2_5 (#2)
  Direction change: road_2_5 (north→west, left turn)
  Commands: [turn(180), forward(2), turn(-90), arrive]

internal_clinic → toilet:
  Path: IC → road_2_3 → road_2_5 → road_2_7 → toilet
  Intersections: road_2_3 (#1), road_2_5 (#2), road_2_7 (#3)
  Direction changes: road_2_3 (east→south, right), road_2_7 (south→east, left)
  Commands: [turn(180), forward(1), turn(90), forward(2), turn(-90), arrive]
```

## 具体变更

| 文件 | 变更 |
|------|------|
| `src/map/tools.py` | `_is_intersection` 邻域判定放宽、`_get_relative_turn` 符号修正、`get_commands` 三阶段重写 |

## 放弃的替代方案

- **方案 B**: 纯 nav 四邻无法识别走廊路口（一侧为 main 出口时判定为非路口），且仅最后转向遗漏多段路径的中间 turn
- **方案 C**: 路段端点匹配过于简化，无法处理 3 段以上的路径

## 后续行动

- [ ] 实车验证所有 90 条路线的 turn 数量正确性
