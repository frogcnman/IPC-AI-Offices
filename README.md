# IPC项目

基于RK3566平台的智能摄像头系统

## 功能特点

- 支持YOLOv4/v5目标检测
- 支持ONVIF协议
- 支持人体检测和图像处理
- 支持UDP通信

## 环境要求

- Python 3.7+
- RKNN Toolkit 2
- OpenCV

## 安装

1. 克隆项目
2. 安装依赖：`pip install -r requirements.txt`
3. 下载模型文件到data目录

## 使用方法

1. 配置config.json和xconfig.json
2. 运行：`bash run.sh`

## 目录结构

- data/: 模型文件
- docs/: 项目文档
- img/: 图像缓存
- logs/: 日志文件
- scripts/: 部署脚本
- tests/: 单元测试

## 许可证

本项目采用私有许可证