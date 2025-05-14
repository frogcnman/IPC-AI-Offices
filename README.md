# IPC项目

基于ONVIF的智能摄像头系统(大多数商用摄像头均支持ONVIF协议，有一些需要在配置中开启ONVIF协议)

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

## 从Git获取项目


# 克隆项目
- git clone https://github.com/frogcnman/IPC-AI-Offices.git 
- cd IPC-AI-Offices 
# 构建并启动容器
- docker-compose up -d

# 使用方法
docker 下正常运行后，访问 ，访问配置接口 http://IP:8000 即可访问监控设备配置页面，页面会自动刷新局域网中所有支持ONVIF协议的IPC设备，这里你需要配置监控设备的账号和密码，即可自动获取监控设备的RTSP视频流地址，保存后即配置完成了局域网中的监控设备；

# 系统使用说明
- 1. 使用手机打开微信，搜索“海知微科技”公众号，关注后进入公众号；
- 2. 在公众号中，通过“设备配置”-“+添加网关”，扫描上面配置页面上的二维码，即可完成设备的配置，可配置“设备名称”。
- 3. 通过公众号 “慧眼主页”进入系统首页后即可查看监控设备的信息；
- 说明：当前系统的使用场景配置为企业使用，当前系统免费；

## 目录结构

- models/: 模型文件
- docs/: 项目文档
- img/: 图像缓存
- logs/: 日志文件
- scripts/: 部署脚本
- tests/: 单元测试

## 许可证

本项目采用私有许可证