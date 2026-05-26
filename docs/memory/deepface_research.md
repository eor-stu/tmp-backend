---
name: DeepFace 调研报告
category: reference
field: global
description: DeepFace 人脸识别库调研：功能、API、模型、适用场景
date: 2026-05-26
---

# DeepFace 调研报告

## 1. 是什么

Python 人脸识别封装库，MIT 协议。包装 10 种识别模型 + 19 种检测器，一条调用完成检测→对齐→归一化→表示→验证全流程。

```bash
pip install deepface
```

## 2. 核心 API

| 函数 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `DeepFace.verify()` | 1:1 人脸验证 | 两张图片路径 | `{"verified": bool}` |
| `DeepFace.find()` | 1:N 目录搜索 | 图片 + db目录 | `List[DataFrame]` |
| `DeepFace.analyze()` | 属性分析 | 图片 + actions列表 | `List[dict]` |
| `DeepFace.represent()` | 提取嵌入向量 | 图片 | `List[dict]` (含embedding) |
| `DeepFace.extract_faces()` | 检测+提取人脸 | 图片 | face对象列表 |
| `DeepFace.stream()` | 实时摄像头分析 | db目录 | 实时画面 |
| `DeepFace.register()` | 注册人脸到DB | 图片 | — |
| `DeepFace.search()` | DB检索 | 图片 | `List[DataFrame]` |

## 3. 关键参数

### 识别模型 (`model_name`)
VGG-Face (默认), Facenet, Facenet512, OpenFace, DeepFace, DeepID, ArcFace, Dlib, SFace, GhostFaceNet, Buffalo_L

### 检测器 (`detector_backend`)
opencv(默认), ssd, dlib, mtcnn, fastmtcnn, retinaface(最强), mediapipe, yolo系列(v8/v11/v12 n/s/m/l), yunet, centerface

### 距离度量 (`distance_metric`)
cosine(默认), euclidean, euclidean_l2, angular

## 4. 属性分析能力

| 属性 | 精度 |
|------|------|
| 年龄 | MAE ±4.65 |
| 性别 | 97.44% 准确率 |
| 情绪 | angry/fear/neutral/sad/disgust/happy/surprise |
| 种族 | asian/white/middle eastern/indian/latino/black |

## 5. 高级特性

- **活体检测**: `anti_spoofing=True`（提取人脸时可用）
- **DB 后端**: PostgreSQL/MongoDB/Neo4j/pgvector/Pinecone/Weaviate
- **ANN 检索**: `search_method="ann"`
- **REST API**: gunicorn 服务，端口 5005，支持文件上传/URL/base64/路径四种入图方式
- **云端**: deepface.dev 有 MCP endpoint

## 6. 适用判断

### 适合
- 需要 1:1 验证或 1:N 识别的应用
- 需要年龄/性别/情绪等面部属性
- 快速原型：一行代码跑通全流程
- 不想手动处理检测→对齐→归一化 pipeline

### 不适合
- 需要自定义训练识别模型（它是封装器，不训练）
- 实时高吞吐场景（Python 封装层有开销）
- 纯离线/嵌入式部署（依赖较重，首次加载下载模型）

## 7. 与本项目潜在结合点

本项目是医院导航后端。可能场景：
- 患者身份核验（`verify`）：挂号时确认身份
- VIP/复诊识别（`find` + `represent`）：识别老患者
- 情绪检测（`analyze`）：分诊前评估患者情绪状态

技术约束：deploy 在树莓派，需选轻量 detector（opencv/ssd）+ 小识别模型（SFace/DeepID），考虑首次模型下载的网络问题。
