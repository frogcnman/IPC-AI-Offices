#3566 radxa 安装
date '+%Y-%m-%d %H:%M:%S'
timedatectl set-timezone Asia/Shanghai
sudo systemctl status systemd-timesyncd
date '+%Y-%m-%d %H:%M:%S'

#程序依赖linux系统安装的系统硬解码的FFmpeg,依赖安装了NPU相关驱动；

#FFMPEG
sudo apt-get update
sudo apt-get install build-essential cmake git libdrm-dev librga-dev librockchip-mpp-dev libsdl2*-dev libx264-dev libx265-dev pkg-config
git clone https://github.com/nyanmisaka/ffmpeg-rockchip
pushd ffmpeg-rockchip/
./configure --prefix=/usr --enable-gpl --enable-version3 --enable-libdrm --enable-rkmpp --enable-rkrga --enable-libx264 --enable-libx265 --enable-ffplay
make -j$(nproc)
sudo make install
popd

#实现硬件解码视频流；

wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh
bash Miniconda3-latest-Linux-aarch64.sh
nano ~/.bashrc
#添加
export PATH=~/miniconda3/bin:$PATH

source ~/.bashrc

conda init
conda -V

conda create -n pyipc python=3.12.3 requests beautifulsoup4 psutil numpy Pillow
onvif-zeep opencv-python-headless

#进入虚拟环境
cd /home/hzw # cd /home/radxa
conda activate pyipc
conda install pip
sudo apt-get install libxslt1.1
pip install requests beautifulsoup4 psutil
pip install onvif-zeep
pip install opencv-python
pip install opencv-python-headless
pip install imageio-ffmpeg
pip install imagehash
pip install rknn_toolkit_lite2-2.3.0-cp312-cp312-manylinux_2_17_aarch64.manylinux2014_aarch64.whl
pip install zhipuai -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install paho-mqtt


#使用窗口管理器让程序运行在后端
apt install screen
#创建 IPC 窗口
screen -S pyipc
#然后运行 python 程序
#退出、关闭SSH工具后，运行下面命令重新进入pyipc 窗体，程序依然运行；
screen -r pyipc

sudo nano /etc/systemd/system/aiipc.service

[Unit]
Description=aiipc
After=network.target
[Service]
ExecStart=/bin/bash /home/radxa/IPC_home/run.sh
WorkingDirectory=/home/radxa/IPC_home
StandardOutput=journal
Restart=always
User=root

[Install]
WantedBy=multi-user.target

sudo systemctl daemon-reload
sudo systemctl enable aiipc.service
sudo systemctl start aiipc.service

#使用登录账号安装 conda
bash Miniconda3-latest-Linux-aarch64.sh

# PC 版本 运行 当前使用虚拟环境 
# 首先安装 python3-venv
sudo apt install python3-venv

# 在项目目录创建虚拟环境
cd /home/hzw/work/cb/IPC_home
python3 -m venv ipc_home

# 激活虚拟环境
cd /home/hzw/work/cb/IPC_home && source ipc_home/bin/activate
# 安装依赖
pip install -r requirements.txt

cd /home/hzw/work/cb/IPC_home
docker-compose up -d

#数据库
#使用数据库保存监控获取到的信息；通过查询固定的值进行数据返回；
