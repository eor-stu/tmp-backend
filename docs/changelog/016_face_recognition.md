# 016: 人脸识别方案选择

**日期**: 2026-05-26
**状态**: 已通过
**决策者**: n1ghts4kura

## 背景

需要为医院导航后端添加用户人脸识别功能，要求：
- 1:N 人脸识别（上传图片 → 匹配已注册用户）
- 1 注册接口（上传姓名 + 图片 → 存储 embedding）
- JSON 文件存储用户数据（与项目现有模式一致）
- 部署目标含树莓派 4（资源受限）

## 考虑的方案

| 方案 | 依赖 | 模型大小 | 安装难度 | 识别精度 | 结论 |
|------|------|----------|----------|----------|------|
| DeepFace (deepface) | TensorFlow (572MB) | 大 | pip install 失败 (TF wheel 损坏) | 高 | **放弃** |
| face_recognition (dlib) | dlib (编译安装) | ~100MB | pip install 成功（清华源 + 清理 /tmp） | 高 | **选择** |
| OpenCV LBPH | opencv-python (已有) | 0 | 零依赖 | 中低 | 放弃 |
| ONNX 模型 + OpenCV DNN | onnxruntime | ~50MB | 需手动下载模型 | 中高 | 放弃 |

## 决策

**选择:** face_recognition (dlib)

## 理由

1. API 极简：`face_recognition.face_encodings(image)` 一行出 128-d embedding
2. 精度高：dlib 的 ResNet 预训练模型在 LFW 上 99.38%
3. 无重型 DL 框架：不需要 TensorFlow/PyTorch，dlib 纯 C++ 编译
4. 安装可行：清理 /tmp 空间后通过清华源 pip install 成功

## 放弃的替代方案

- **DeepFace**: 依赖 TensorFlow 572MB，pip install 时 TF wheel 文件损坏，树莓派资源不足以支持
- **OpenCV LBPH**: 需要每个用户多张训练图片，不适合单张注册场景
- **ONNX 模型**: 需要手动管理模型文件下载和版本，增加运维复杂度

## 后续行动

- [x] 实现 `/face/register` 和 `/face/face-recog` 路由
- [x] 实现 JSON 用户数据库 (users.json)
- [ ] 实测阈值调优（当前 cosine 距离阈值 0.5）
- [ ] 树莓派实机性能测试
