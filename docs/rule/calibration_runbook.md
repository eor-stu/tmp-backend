---
name: Vision 巡线导航标定操作手册
category: guide
field: code
description: 从设计到现实的 7 步标定流程，包含脚本用法、参数对照、数据分析和常见问题
date: 2026-05-26
---

# Vision 巡线导航标定操作手册

本文档描述如何将理论设计的 vision 巡线导航系统通过系统化标定流程落地到真实硬件上。

## 前置条件

- 树莓派已连接的 USB 摄像头
- 已连线的 LOBOROBOT 四轮底盘
- 地面有黑色粗线条（含至少一个十字或 T 字路口）
- VNC 连接树莓派桌面（用于画面观察）
- 卷尺（用于底盘标定）

## 整体流程

```
Phase 1 画面验证 → Phase 2 路口采样 → Phase 3 阈值校准
                                      ↓
Phase 4 PID 静态标定 → Phase 5 直线巡线 → Phase 6 单路口 → Phase 7 全路径
                        ↑                                   ↓
                        └────────── 发现问题则回溯 ──────────┘
Phase 附 底盘物理标定（可在任意阶段插入）
```

---

## Phase 1: 画面验证

**目的**: 确认黑线在实际光照/地面条件下能被正确检测。

**操作**:
```bash
python -m test.test_vision_scene --tag phase1_check --display
```

1. 将车放在真实地面上（有黑线的位置）
2. 观察右侧二值化小窗：黑线是否清晰呈现为白色区域？
3. 用手遮挡光线模拟明暗变化，确认自适应阈值能补偿
4. 按 `s` 保存截图给 Claude Code 参考

**判断标准**:
- 黑线轮廓清晰连续，无大面积断裂
- 噪点可控（零星小白点可接受，大面积雪花不可接受）
- 不同光照下黑线边缘波动 < 20% 线宽

**可调参数** (`src/vision/line_detector.py`):

| 参数 | 默认 | 调整方向 |
|------|------|---------|
| `ADAPTIVE_BLOCK_SIZE` | 11 | 太小→噪点多；太大→线边缘模糊。奇数，9-15 |
| `ADAPTIVE_C` | 2 | 太小→更多白；太大→更少白。建议 0-5 |
| `MIN_CONTOUR_AREA` | 100 | 太小→噪点被当成线；太大→线被忽略 |

**将观察结果告知 Claude Code**:
- 画面中黑线宽度大概占多大比例？
- 噪点多不多？
- 光照均匀吗？有没有一侧亮一侧暗？

---

## Phase 2: 路口采样

**目的**: 采集"正常巡线"vs"接近路口"两组对比数据，确定面积阈值。

**操作**:
```bash
# 位置 A：正常巡线中（离路口 > 0.5m）
python -m test.test_vision_scene --tag on_line --display

# 位置 B：接近路口（该触发检测的位置）
python -m test.test_vision_scene --tag near_junction --display
```

1. 手动将车推到位置 A，运行脚本，观察 5-10 秒
2. 将车推到位置 B，运行脚本，观察 5-10 秒
3. 查看是否有横线轮廓出现（`horizontal` 字段 > 0）

**路口检测原理**: 使用双信号加权投票机制（`intersection_detector.py`）：
- 信号1（强，2票）：轮廓面积相对于固定基线的尖峰检测
- 信号2（弱，1票）：Sobel 水平边缘检测 + 保持帧防闪烁
- 需要累积 3 票且包含至少一次面积尖峰才触发

线检测使用按列最暗百分位分析（`line_detector.py`）找出黑线中心，配合自适应阈值二值化。

**产出**:
- `data/vision_calib/line_scene/on_line.jsonl`
- `data/vision_calib/line_scene/near_junction.jsonl`

**将数据交给 Claude Code**: Claude Code 会自动 `Read` 这两个文件，对比 `area`、`vertical`、`horizontal`、`ratio` 字段的分布，给出 `AREA_THRESHOLD_RATIO` 的建议修改值。

---

## Phase 3: 阈值校准

**由 Claude Code 主导**: Claude Code 读完 Phase 2 数据后，会：
1. 给出 `AREA_THRESHOLD_RATIO` 的建议值（原 0.3）
2. 必要时调整 `ASPECT_VERTICAL`(2.0) / `ASPECT_HORIZONTAL`(2.0)
3. 直接修改源码

**验证**: 重新跑 Phase 2 的 `near_junction` 位置，确认 `at_intersection` 字段正确触发。

---

## Phase 4: PID 静态标定

**目的**: 轮子悬空验证 PID 响应是否合理，不涉及真实行驶。

**操作**:
```bash
python -m test.test_vision_pid --tag pid_static --display
```

1. 把车架起来（轮子悬空）
2. 运行时可以看到当前偏差条和电机输出
3. 手动在摄像头前移动一张黑色纸片，模拟偏差变化
4. 观察电机响应：
   - 线偏右 → 右侧轮速应 > 左侧（向右修正）
   - 偏差归零 → 两侧等速
   - 快速晃动 → 响应是否平滑（无抖动/无超大超调）

**产出**: `data/vision_calib/pid_test/pid_static.jsonl`

**将数据交给 Claude Code**: 描述车的电机响应表现（"偏差0.3时左轮15右轮25，感觉响应偏慢"），Claude Code 分析 JSONL 中的 `deviation` 和 `left_speed`/`right_speed` 时序关系。

**可调参数** (`src/vision/pid_controller.py`):

| 参数 | 默认 | 调整方向 |
|------|------|---------|
| `DEFAULT_KP` | 30 | 太小→响应慢、偏差纠正不及时；太大→震荡、左右摇摆 |
| `DEFAULT_KI` | 1.0 | 太小→稳态偏差纠正慢；太大→过冲、积分饱和 |
| `DEFAULT_KD` | 10 | 太小→震荡；太大→响应迟钝 |
| `BASE_SPEED` | 20 | 整体巡线速度 |
| `MAX_SPEED` | 35 | 差速上限，防止一侧电机饱和 |
| `MIN_SPEED` | 5 | 差速下限，防止一侧失速 |

---

## Phase 5: 直线巡线测试

**目的**: 第一条闭环——无路口直线，验证基本巡线能力。

**操作**:
```bash
python -m test.test_vision_pid --tag pid_straight --display
```

1. 在地上画一条无路口的直线（或找一条现成走廊）
2. 通过 VNC 观察偏差条是否稳定

**判断标准**:
- 偏差长期均值接近 0（无系统偏差累积）
- 偏差标准差小（无剧烈震荡）
- Ki=1.0 能否消除缓慢漂移

**产出**: `data/vision_calib/pid_test/pid_straight.jsonl`

**将数据交给 Claude Code**: 描述实际车身行为（"车左右抖动频率约1Hz"、"车一直往左边偏"），Claude Code 分析偏差时序统计。

---

## Phase 6: 单路口测试

**目的**: 验证路口检测 + 过路口 + 转向的完整链路。

**操作**:
```bash
# 方式一: 直接用 test 脚本测试单个路口
python -m test.test_single_intersection
# 方式二: 启动后端通过 API 测试
python -m src.main
curl -X POST http://localhost:8000/vision/start_navigate \
  -H "Content-Type: application/json" \
  -d '{"start":"entrance","destination":"pharmacy"}'
```
Navigator 内部使用 `[{action: "forward"|"turn", param: float}]` 命令格式，
如 `set_commands([{"action":"turn","param":180},{"action":"forward","param":2},{"action":"turn","param":-90}])`。

1. 设置一个 T 字或十字路口
2. 观察路口检测在何时触发（应离路口足够近）
3. 确认 `forward(0.15)` 推进后车身位置
4. 确认 `turn(90)` 后车身方向

**判断标准**:
- 路口检测不早不晚（不在远处误触发，不走过头才触发）
- `forward(0.15)` 推进后车身在路口中心附近
- 转向后能重新看到下一段黑线

**将数据交给 Claude Code**: 描述每个环节的表现：
- 路口触发时车离路口还有多远？
- 推进 0.15m 够不够到路口中心？
- 转向 90° 后角度准确吗？

Claude Code 据此调整 `FORWARD_DISTANCE`（`src/vision/navigator.py`）或底盘标定值。

---

## Phase 7: 全路径端到端

**目的**: 跑完整真实路径，验证终点检测和整体稳定性。

**操作**:
```bash
# 枚举所有路线指令
python -m test.test_all_routes
# 端到端导航测试
python -m test.test_full_path
# 或通过 API 发起完整导航
python -m src.main
```

**判断标准**:
- 每个路口正确触发，无漏检无误检
- 终点检测在正确位置触发（无提前终止）
- 全程无脱线、无冲出路线

---

## Phase 附: 底盘物理标定

**目的**: 验证 `V_FORWARD` 和 `V_ROTATE` 标定值是否准确。

**操作**:
```bash
python -m test.test_chassis_calib
```

1. 脚本依次执行 `forward(1.0)` × 3 和 `turn(360)` × 3
2. 每次执行后，用卷尺测量实际前进距离 / 目测实际角度
3. 将实际值告知 Claude Code

**产出**: `data/vision_calib/chassis/` 下的日志

**当前标定值** (`src/car/LOBOROBOT.py`):
- `V_FORWARD`: 0.186 m/s (2026-05-24 标定，原 0.215)
- `V_ROTATE`: 75.8 deg/s (2026-05-24 标定，原 96.0)

**将数据交给 Claude Code**: 汇报每次测试的实际值，Claude Code 计算平均值并与标定值比较，决定是否更新 `V_FORWARD` / `V_ROTATE`。

---

## 快速参考

| 需求 | 脚本 | 命令 |
|------|------|------|
| 看画面效果 | test_vision_scene | `python -m test.test_vision_scene --tag test --display` |
| 采路口对比数据 | test_vision_scene | `python -m test.test_vision_scene --tag on_line` |
| PID 响应采集 | test_vision_pid | `python -m test.test_vision_pid --tag my_test --display` |
| 底盘速度验证 | test_chassis_calib | `python -m test.test_chassis_calib` |
| 全导航测试 | src.main | `python -m src.main` + API 调用 |

### 每次迭代的反馈模板

向 Claude Code 汇报时包含：
1. **跑了哪个 Phase / 脚本 / tag**
2. **观察到的现象**（不解释原因，只描述事实）
3. **JSONL 文件位置**

Claude Code 会处理剩下的：读数据、分析、给出参数建议、改代码。
