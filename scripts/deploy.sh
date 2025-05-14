#!/bin/bash

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
}

# 安装依赖
echo "Installing dependencies..."
pip3 install -r ../requirements.txt

# 检查模型文件
MODEL_FILES=("yolov4-tiny.cfg" "yolov4-tiny.weights" "yolov5s.onnx")
for file in "${MODEL_FILES[@]}"; do
    if [ ! -f "../data/$file" ]; then
        echo "Error: Model file $file not found in data directory"
        exit 1
    fi
done

# 创建必要的目录
mkdir -p ../logs
mkdir -p ../img/cache

echo "Deployment completed successfully"