# -*- coding: utf-8 -*-
import cv2
import numpy as np
import time
import os, socket
from PIL import Image
from imageio_ffmpeg import get_ffmpeg_exe
import subprocess
import rknn_imginfo#, ai_zhipu_imginfo
import threading
import imagehash, re, json
import glob
import logger
import copy
import requests
import base64
from typing import Optional, Dict, Any
import datetime #from datetime 
import set_mp4

# 全局变量用于控制线程
svr_ip = "f.hzwkj.cn"
svr_port = 60087
stop_thread = False
file_operation_lock = threading.Lock()  # 文件操作锁
device_locks = {}  # 每个设备的专用锁
# 定时处理
Alarm_date = 0
Alarm_clock = 20
Alarm_MP4 = True
config_path = r"./config.json"
# 保存照片以及处理状态的列表
IPC_lst = []
# 创建一个互斥锁
lock = threading.Lock()
# 图像信息
IPC_img_info = {"img_path": "",
                "img_time": "",
                "img_type": 0,
                "ai_info": {}}

def get_Report_time(fday = 0):
    try:
        # 获取前一天的日期
        yesterday = datetime.date.today() + datetime.timedelta(days=fday)

        # 组合日期与时间（20:00:00）
        target_time = datetime.datetime.combine(yesterday, datetime.time(20, 0, 0))

        # 转换为时间戳（本地时间对应的UTC秒数）
        timestamp = int(target_time.timestamp())
        return timestamp
    except Exception as e:
        #logger.wdlog(f"处理消息时出错: {str(e)}")
        return 20

def write_config_file(new_config, filename=config_path):
    """
    将新的配置写入 JSON 文件。
    :param filename: JSON 文件的路径。
    :param new_config: 要写入的新的配置数据。
    :return: 是否成功写入配置文件。
    """
    try:
        if new_config is None:
            logger.wdlog("未提供新的配置数据")
            return False
        new_config["Report_time"] = get_Report_time(1)
        # 写入 JSON 文件
        with open(filename, 'w') as file:
            json.dump(new_config, file, indent=4)
        logger.wdlog(f"配置文件{filename}更新成功")
        return True

    except Exception as e:
        logger.wdlog(f"写入配置文件时出错: {str(e)}")
        return False

def read_config_file(filename=config_path):
    """
    读取JSON文件并将其内容转换为Python对象。

    :param filename: JSON文件的路径。
    :return: 转换后的Python对象。
    """
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            return data
    except Exception as e:
        logger.wdlog(f"处理消息时出错: {str(e)}")
        return None

def extract_ip_address_from_path(path):
    parts = path.split('/')
    for part in parts:
        if '.' in part and len(part.split('.')) == 4:
            try:
                # 确保这部分是一个有效的 IP 地址
                socket.inet_aton(part)
                return part
            except socket.error as e:
                # 不是有效的 IP 地址，继续搜索
                logger.wdlog(f"IPC_ID获取失败：{e}")
                continue
    return None

def call_image_analysis(
    image_path: str, 
    client_id: str, 
    ipc_id: str, 
    ipc_name: str,
    img_time: str = "",
    type_state: int = 1, 
    api_url: str = f"http://{svr_ip}:{svr_port}",
    key: str = ""
) -> Optional[Dict[str, Any]]:
    """
    调用图像分析API接口
    
    Args:
        image_path: 图片路径
        client_id: 客户ID
        ipc_id: 摄像头ID
        ipc_name: 摄像头名称
        img_time: 图片时间，格式：YYYY-MM-DD HH:MM:SS
        type_state: 模型类型，1为千问模型，2为智谱模型
        api_url: API服务器地址
        key: 智谱API密钥（type_state=2时需要）
        
    Returns:
        分析结果字典，如果失败返回None
    """
    try:
        # 读取并编码图片
        with open(image_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        img_name = os.path.basename(image_path)

        img_list = rknn_imginfo.get_human_images_base64(image_path)
        # 构建请求数据
        payload = {
            "type_state": type_state,
            "client_id": client_id,
            "ipc_id": ipc_id,
            "img_name": img_name,
            "ipc_name": ipc_name,
            "image_base64": image_base64,
            "image_base64_lst": img_list,
            "img_time": img_time or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 如果提供了key，添加到请求中
        if key:
            payload["key"] = key
        
        # 发送POST请求
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            f"{api_url}/api/image_analysis", 
            data=json.dumps(payload), 
            headers=headers
        )
        
        # 检查响应状态
        if response.status_code == 200:
            result = response.json()
            if result["code"] == 200:
                return result["data"]
            else:
                print(f"API调用失败: {result['message']}")
                return None
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"发生错误: {str(e)}")
        return None


def set_date():
    # 定义命令列表
    try:
        commands = [
            "timedatectl set-timezone Asia/Shanghai",
            "systemctl status systemd-timesyncd",
            "date '+%Y-%m-%d %H:%M:%S'"
        ]

        # 运行每个命令
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, text=True, capture_output=True)

            # 打印命令输出
            # logger.wdlog(f"Command: {cmd}")
            logger.wdlog(f"CMD_SetDate:\n{result.stdout}")

            # 如果命令执行失败，打印错误信息
            if result.returncode != 0:
                logger.wdlog(f"CMD_SetDate_Error:\n{result.stderr}")
    except Exception as e:
        logger.wdlog(f"CMD_SetDate_Error:\n{str(e)}")

def get_alarm_date():
    try:
        # 获取当前年月日的时间元组
        current_time = time.localtime()
        year, month, day = current_time.tm_year, current_time.tm_mon, current_time.tm_mday

        # 构造当天 00:00:00 的时间元组
        midnight_tuple = (year, month, day, 0, 0, 0, 0, 0, 0)

        # 转换为时间戳并取整
        timestamp = int(time.mktime(midnight_tuple))
    except:
        logger.wrlog()
        timestamp = 0
    return timestamp


# IPC_lst 公有变量互斥
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
def thread_safe_clear():
    global IPC_lst
    with lock:
        IPC_lst = [d for d in IPC_lst if d["img_type"] != 1]


def thread_safe_append(item):
    with lock:
        IPC_lst.append(item)
        # print('Addlst:',IPC_lst)


def thread_safe_set(index, item):
    global IPC_lst
    with lock:
        IPC_lst[index] = item
        # print('Editlst:', IPC_lst)


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 图像去重功能模块部分，此处 run_proc_img() 将启用线程进行运行
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 文件名路径格式化获取文件生成具体日期时间函数
def format_timestamp_from_filename(file_path):
    # 从文件路径中提取文件名
    filename = file_path.split('/')[-1]
    # 使用正则表达式匹配时间戳
    match = re.search(r'\d+', filename)
    if match:
        # 获取时间戳字符串并转换为整数
        timestamp = int(match.group())
        # 使用time库格式化日期时间字符串
        formatted_date_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        return formatted_date_time
    else:
        return None


def get_image_hash(image_path):
    """
    计算图片的哈希值
    :param image_path: 图片的路径
    :return: 图片的哈希值
    """
    with Image.open(image_path) as img:
        hash_value = imagehash.phash(img)
    return hash_value


# 这里 目前测试合理范围应该是在 5-7之间，目标是平均每小时3-4条；年化在140元算力费用内；而去重的数据又具有实际效用
# 10 去重周期300s,发现去重效果不理想基本去重保留第一帧，其他均被删除；
# 5 去重周期300S,第一次计算每小时7.4条；当前去重效果较为满意，基本保证了人在区域活动的变化均可保存，同一地方的细节动作保存还需验证；

def deduplicate_images(image_folder, threshold=3):
    """
    改进后的高效图片去重函数，结合多种哈希算法提高精度
    
    参数:
    - image_folder: 图片目录
    - threshold: 哈希相似度阈值(默认提高到8)
    """
    hash_dict = {}
    original_count = 0
    deduplicated_count = 0
    deleted_count = 0

    try:
        if not os.path.exists(image_folder):
            print(f"目录不存在: {image_folder}")
            return

        image_files = sorted(glob.glob(os.path.join(image_folder, 'frame_*.jpg')))

        for image_path in image_files:
            try:
                if not os.path.isfile(image_path) or os.path.getsize(image_path) == 0:
                    print(f"跳过无效文件: {image_path}")
                    continue

                original_count += 1

                # with Image.open(image_path) as img:
                #     if img.mode != 'RGB':
                #         img = img.convert('RGB')
                #     img = img.resize((64, 64), Image.Resampling.LANCZOS)
                    
                #     # 使用多种哈希算法组合提高精度
                #     avg_hash = str(imagehash.average_hash(img))
                #     phash = str(imagehash.phash(img))
                #     dhash = str(imagehash.dhash(img))
                #     # 组合哈希作为唯一标识
                #     combined_hash = f"{avg_hash[:8]}{phash[8:16]}{dhash[16:24]}"

                # 改进的相似度比较
                is_unique = True
                # for existing_hash in hash_dict:
                #     # 计算三种哈希的相似度
                #     avg_sim = sum(c1 != c2 for c1, c2 in zip(avg_hash, existing_hash[:8]))
                #     p_sim = sum(c1 != c2 for c1, c2 in zip(phash, existing_hash[8:16]))
                #     d_sim = sum(c1 != c2 for c1, c2 in zip(dhash, existing_hash[16:24]))
                    
                #     # 只有三种哈希都相似才认为是重复图片
                #     if avg_sim <= threshold and p_sim <= threshold and d_sim <= threshold:
                #         is_unique = False
                #         break

                if is_unique:
                    # hash_dict[combined_hash] = image_path
                    deduplicated_count += 1

                    output_path = os.path.join(image_folder, 'pro' + os.path.basename(image_path))
                    os.rename(image_path, output_path)

                    f_datetime = format_timestamp_from_filename(output_path)
                    if f_datetime:
                        f_dict = {
                            "img_path": output_path,
                            "img_time": f_datetime,
                            "img_type": 0,
                            "ai_info": {}
                        }
                        thread_safe_append(f_dict)
                else:
                    os.remove(image_path)
                    deleted_count += 1

            except Exception as e:
                print(f"处理文件 {image_path} 时出错: {e}")
                continue

        if original_count > 0:
            print(f"原目录照片数量: {original_count}")
            print(f"去重后照片数量: {deduplicated_count}")
            print(f"删除的照片数量: {deleted_count}")

    except Exception as e:
        print(f"图像去重过程发生严重错误: {e}")
        logger.wdlog(f"图像去重错误: {str(e)}")


# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 启用AI线程，同步分析去重后的图像
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

def delete_files_starting_with(directory=r"./img", prefix="proframe_"):
    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        # 检查文件名是否以指定的前缀开头
        if filename.startswith(prefix):
            # 构造完整的文件路径
            file_path = os.path.join(directory, filename)
            # 删除文件
            os.remove(file_path)
            print(f"已删除: {file_path}")




# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 分析IPC_lst 发送数据并预警
# {'有人在家': '是', '人员是否安全': '否', '身体是否健康': '否', '心情是否愉悦': '否', '总结描述': '成年男性躺在客厅地板上，可能存在安全隐患；狗狗在宠物床上休息，无异常行为。'}
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
def create_video_from_images(directory, output_file, fps=30, proframe="proframe_", resolution=(None, None)):
    try:
        import os
        import cv2

        # 仅选择以"proframe_"开头的.jpg或.png图片文件
        images = [img for img in os.listdir(directory) if
                  (img.endswith(".jpg") or img.endswith(".png")) and img.startswith(proframe)]
        images.sort()

        # 读取第一张图片以获取尺寸
        if not images:  # 如果没有找到符合条件的图片，则退出
            print("没有找到以'proframe_'开头的图片文件。")
            return

        first_image_path = os.path.join(directory, images[0])
        frame = cv2.imread(first_image_path)
        height, width, layers = frame.shape

        # 如果指定了分辨率，则使用指定分辨率，否则使用图片原始分辨率
        output_width, output_height = resolution
        if output_width is None:
            output_width = width
        if output_height is None:
            output_height = height

        # 创建视频编写器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 可以使用其他编码器，如 'XVID'
        video = cv2.VideoWriter(output_file, fourcc, fps, (output_width, output_height))

        # 将图片写入视频
        for image in images:
            image_path = os.path.join(directory, image)
            frame = cv2.imread(image_path)
            # 如果需要，调整图片大小以匹配指定分辨率
            if (output_width, output_height) != (width, height):
                frame = cv2.resize(frame, (output_width, output_height))
            video.write(frame)

        # 释放资源
        video.release()
        # print(f"视频已保存为 {output_file}")
        return output_file
    except Exception as e:
        print(f"视频合成错误: {e}")
        return None




# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 获取视频流图像，主要负责图像处理、纠错，获取高质量可用图像
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
def sharpen_image(frame, center_value=5, surround_value=-1):
    """
    使用卷积滤波器对图像进行锐化处理
    :param frame: 输入图像
    :param center_value: 卷积核中心值
    :param surround_value: 卷积核周围值
    """
    kernel = np.array([[0, surround_value, 0],
                       [surround_value, center_value, surround_value],
                       [0, surround_value, 0]])  # 锐化核
    sharpened = cv2.filter2D(frame, -1, kernel)  # 应用锐化滤波器
    return sharpened


def compress_and_save_image(frame, save_path, target_height=720, max_size_kb=500):
    """
    压缩图像并保存
    """
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    width, height = img.size
    new_width = int((target_height / height) * width)
    img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)
    img.save(save_path)


def get_img(rtsp, output_path="./img/output.jpg"):
    """
    从RTSP流中捕获一张图片并覆盖之前的图片。

    :param rtsp: RTSP流地址
    :param output_path: 保存图片的路径
    """
    try:
        ffmpeg_path = get_ffmpeg_exe()  # 获取FFmpeg的可执行文件路径
        command = [
            ffmpeg_path,
            "-i", rtsp,  # 输入RTSP地址
            # "-c:v", "h264_rkmpp",  # 指定使用h264_rkmpp编码器
            "-frames:v", "1",  # 只捕获一帧
            "-q:v", "1",  # 设置图像质量（值越小质量越高）
            "-y",  # 强制覆盖输出文件
            output_path  # 输出图片路径
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # 静音模式运行
    except Exception as e:
        print(f"捕获照片发生错误: {e}")


def get_best_img(frame):
    # 定义图像的下半部分
    rn = False
    try:
        height, width, _ = frame.shape
        lower_half = frame[height // 4:, :]

        # 定义绿色的范围（在HSV颜色空间中）
        lower_green = np.array([40, 40, 40])
        upper_green = np.array([80, 255, 255])

        # 将下半部分图像转换到HSV颜色空间
        hsv_lower_half = cv2.cvtColor(lower_half, cv2.COLOR_BGR2HSV)

        # 创建掩码，只包含绿色区域
        mask_lower_half = cv2.inRange(hsv_lower_half, lower_green, upper_green)

        # 计算绿色像素的比例
        green_pixel_ratio = np.sum(mask_lower_half == 255) / (lower_half.shape[0] * lower_half.shape[1])

        # 设定阈值
        threshold = 0.5  # 例如，如果超过50%的像素是绿色，则认为下半部分异常

        # 检测图像下半部分是否异常
        if green_pixel_ratio > threshold:
            rn = False
        else:
            rn = True
        return rn
    except Exception as e:
        print(f"照片检测完整性发生错误: {e}")
        return rn


def evaluate_frame_quality(frame):
    try:
        # 1. 添加线程安全的帧复制
        frame = frame.copy() if frame is not None else None
        
        # 2. 基本验证
        if frame is None or frame.size == 0:
            return 0.0

        # 3. 使用线程安全的数据类型和操作
        with np.errstate(all='raise'):  # 捕获所有数值计算警告
            # 转换为灰度图像
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            
            # 检查数据范围
            if np.min(gray) == np.max(gray):
                return 0.0
                
            # 归一化处理
            gray_min = np.min(gray)
            gray_max = np.max(gray)
            if gray_max - gray_min == 0:
                return 0.0
            gray = (gray - gray_min) / (gray_max - gray_min)
            
            # 高斯模糊
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Sobel 算子计算
            sobelx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
            sobely = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
            
            # 安全的梯度计算
            gradient_magnitude = np.clip(
                np.sqrt(np.square(sobelx) + np.square(sobely)),
                0, None
            )
            
            # 使用更稳定的统计方法
            quality = float(np.percentile(gradient_magnitude, 50))
            
            return quality if np.isfinite(quality) else 0.0
            
    except Exception as e:
        print(f"图像质量评估错误: {e}")
        return 0.0

def select_best_frame(cap, num_frames=4):
    """选择最佳图像帧"""
    best_frame = None
    best_quality = 0.0
    frame_count = 0
    
    try:
        if not cap or not cap.isOpened():
            print("无法打开视频流")
            return None
            
        while frame_count < num_frames:
            try:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                    
                # 创建帧的副本以避免并发访问问题
                frame = frame.copy()
                
                # 验证帧数据
                if frame.size == 0 or not np.all(np.isfinite(frame)):
                    continue
                    
                # 使用互斥锁保护质量评估过程
                with threading.Lock():
                    quality = evaluate_frame_quality(frame)
                    if quality > best_quality and get_best_img(frame):
                        best_quality = quality
                        best_frame = frame.copy()
                
                frame_count += 1
                
            except Exception as e:
                print(f"处理单帧时出错: {e}")
                continue
            
        return best_frame
        
    except Exception as e:
        print(f"获取最佳图像帧出错: {e}")
        return None


# 获取高质量图片，使用CV2
def get_h_img(rtsp_url, output_path="./img/output.jpg"):
    """
    使用ffmpeg从RTSP流获取高质量图片，增加流状态验证
    
    返回:
        bool: True表示成功获取新图片，False表示失败
    """
    try:
        # 获取原始文件修改时间（如果存在）
        old_mtime = os.path.getmtime(output_path) if os.path.exists(output_path) else 0
        
        ffmpeg_path = get_ffmpeg_exe()
        command = [
            ffmpeg_path,
            "-i", rtsp_url,  # 输入RTSP地址
            "-vf", "fps=10",  # 设置帧率（如果需要）
            "-s", "1920x1080",  # 设置输出视频的分辨率
            #"-c:v", "h264_rkmpp",  # 指定使用h264_rkmpp编码器（如果需要硬件解码）
            "-frames:v", "1",  # 只捕获一帧
            "-q:v", "1",  # 设置图像质量（值越小质量越高）
            "-y",  # 强制覆盖输出文件
            output_path  # 输出图片路径
        ]
        
        # 运行命令并检查返回码
        #result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 检查命令是否成功执行
        if result.returncode != 0:
            print(f"FFmpeg命令执行失败，返回码: {result.returncode}")
            if result.stderr:
                print(f"错误信息: {result.stderr.decode('utf-8')}")
            return False

        # 检查是否真的生成了新图片
        if not os.path.exists(output_path):
            return False
            
        new_mtime = os.path.getmtime(output_path)
        if new_mtime <= old_mtime:
            return False
            
        # 验证图片内容
        try:
            frame = cv2.imread(output_path)
            if frame is None or frame.size == 0:
                return False
                
            # 检查图像质量
            if not get_best_img(frame):
                return False
                
            return True
                
        except Exception as e:
            print(f"图片验证失败: {e}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"获取图像超时: {rtsp_url}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg命令执行失败: {e.stderr.decode('utf-8')}")
        return False
    except Exception as e:
        print(f"获取图像出错: {e}")
        return False

# def get_h_img(rtsp_url, output_path="./img/output.jpg"):
#     try:
#         # 创建视频捕获对象
#         cap = cv2.VideoCapture(rtsp_url)
#         # 挑选最佳帧
#         best_frame = select_best_frame(cap)
#         # 保存缓存照片
#         cv2.imwrite(output_path, best_frame)
#         return True
#     except Exception as e:
#         print(f"缓存图片save出错: {e}")
#         return False
def ai_analysis_worker(img_path, client_id, ipc_id, ipc_name, img_time, index):
    """
    AI分析的独立工作线程
    """
    try:
        ai_info = call_image_analysis(
            image_path=img_path,
            client_id=client_id,
            ipc_id=ipc_id,
            ipc_name=ipc_name,
            img_time=img_time,
            type_state=2
        )
        if ai_info:
            new_value = {
                "img_path": img_path,
                "img_time": img_time,
                "img_type": 1,
                "ai_info": ai_info  # 这里修正了原代码中空的ai_info
            }
            thread_safe_set(index, new_value)
    except Exception as e:
        logger.wdlog(f"AI分析线程出错: {e}")
# ———————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

def unified_image_processing(rtsp_list, client_id, mqtt_client, save_folder="./img/", 
                           capture_interval=1, detection_interval=3, 
                           dedup_interval=60, cleanup_hour=2):
    """
    统一的图像处理函数，整合了图像捕获、去重、AI分析和数据清理功能
    
    参数:
    - rtsp_list: 摄像头列表
    - client_id: 客户ID
    - save_folder: 保存目录
    - capture_interval: 图像捕获间隔(秒)
    - detection_interval: 人体检测间隔(次数)
    - dedup_interval: 去重处理间隔(秒)
    - cleanup_hour: 数据清理时间(小时)
    """
    global lock  # 添加全局锁的声明
    try:
        # 初始化设备状态
        device_states = {}
        last_dedup_time = time.time()
        gf = read_config_file()
        if gf:
            last_cleanup_date = gf['Report_time']
        else:
            last_cleanup_date = get_Report_time()

        ipclst = []
        # 初始化设备目录和状态
        for device in rtsp_list:
            ip_address = device.get('ip', '')
            ipc_name = device.get('dev_name', '')
            rtsp_url = device.get('rtsp', '')
            ipc_initialize ={"ipc_id": ip_address,
                                "ipc_state": True,
                                "ipc_name": ipc_name,
                                "rtsp_url": rtsp_url}
            ipclst.append(ipc_initialize)
            if ip_address:
                device_locks[ip_address] = threading.Lock()
                save_dir = os.path.join(save_folder, ip_address)
                os.makedirs(save_dir, exist_ok=True)
                device_states[ip_address] = {
                    'last_saved_time': time.time(),
                    'detection_count': 0,
                    'retries': 0,
                    'last_features': None  # 添加last_features初始化
                }

        while not stop_thread:
            current_time = time.time()
            sendlist = copy.deepcopy(ipclst)
            # 1. 图像捕获和人体检测处理
            for device in rtsp_list:
                ip_address = device.get('ip', '')
                dev_name = device.get('dev_name', '未知设备')
                rtsp_url = device.get('rtsp', '')
                if not (ip_address and rtsp_url):
                    continue
                
                try:
                    state = device_states[ip_address]
                    
                    # 捕获和处理图像
                    with device_locks[ip_address]:
                        temp_image_path = f"./img/{ip_address}_output.jpg"
                        if get_h_img(rtsp_url, temp_image_path):   
                            ipc_state = True                    
                            state['detection_count'] += 1
                            if state['detection_count'] >= detection_interval:
                                state['detection_count'] = 0
                                
                                if os.path.exists(temp_image_path):
                                    frame = cv2.imread(temp_image_path)
                                    if frame is not None and rknn_imginfo.get_human(frame):
                                        # 新增: 计算当前帧的人体关键点特征
                                        current_features = rknn_imginfo.extract_human_features(frame)
                                        
                                        # 检查是否需要保存(基于动作变化)
                                        should_save = True
                                        if state['last_features'] is not None:  # 修改为字典访问方式
                                            # 计算特征相似度
                                            similarity = rknn_imginfo.compare_features(
                                                state['last_features'],  # 修改为字典访问方式
                                                current_features
                                            )
                                            # 相似度高于阈值则跳过保存
                                            if similarity > 0.85:  # 0.85是可调整的阈值
                                                should_save = False
                                        
                                        if should_save and current_time - state['last_saved_time'] >= capture_interval:
                                            save_path = os.path.join(save_folder, ip_address)
                                            img_path = os.path.join(save_path, f"frame_{current_time}.jpg")
                                            compress_and_save_image(frame, img_path)
                                            state['last_saved_time'] = current_time
                                            state['last_features'] = current_features  # 修改为字典访问方式
                        else:
                            #获取IPC图片失败；
                            ipc_state = False

                        for ipc in sendlist:
                            if ipc.get("ipc_id") == ip_address and ipc.get("ipc_state") != ipc_state:
                                ipc["ipc_state"] = ipc_state
                                break
                except Exception as e:
                    logger.wdlog(f"处理设备 {ip_address} 时出错: {e}")
                    continue
            if sendlist != ipclst:
                senddict = {
                    "ipc_info": sendlist
                }
                mqtt_client.publish_message(senddict)
                ipclst = copy.deepcopy(sendlist)
                #sendlist.clear()
            # 2. 图像去重处理
            
            if current_time - last_dedup_time >= dedup_interval:
                print("2. 图像去重处理")
                for device in rtsp_list:
                    ip_address = device.get('ip', '')
                    if ip_address:
                        img_dir = os.path.join(save_folder, ip_address)
                        if os.path.exists(img_dir):
                            with device_locks[ip_address]:
                                deduplicate_images(img_dir)
                last_dedup_time = current_time
            
            # 3. AI分析处理
            
                with lock:
                    get_lst = IPC_lst.copy()
                
                if get_lst:
                    
                    for index, value in enumerate(get_lst):
                        try:
                            if int(value.get("img_type", -1)) == 0:
                                img_path = value.get("img_path", "")
                                ipc_id = extract_ip_address_from_path(img_path)
                                ipc_name = next((d.get('dev_name', '') for d in rtsp_list if d.get('ip', '') == ipc_id), None)
                                if ipc_id:
                                    # 启动独立线程处理AI分析
                                    t = threading.Thread(
                                        target=ai_analysis_worker,
                                        args=(img_path, client_id, ipc_id, ipc_name, 
                                            value.get("img_time", ""), index),
                                        daemon=True
                                    )
                                    t.start()
                        except Exception as e:
                                logger.wdlog(f"AI分析 {img_path} 时出错: {e}")
            # 4. 数据清理处理         
            #current_hour = time.localtime().tm_hour
            current_day = int(time.time())
            #current_hour = time.localtime().tm_hour      
            #if current_day > last_cleanup_date and current_hour >= cleanup_hour:
            if current_day > last_cleanup_date:
                try:
                    logger.wdlo(f'开始数据清理，当前时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
                    #print("4. 数据清理处理")
                    thread_safe_clear()
                    
                    with file_operation_lock:
                        for device in rtsp_list:
                            ip_address = device.get('ip', '')
                            if ip_address:
                                set_mp4.generate_and_upload_video(client_id, ip_address)
                                save_dir = os.path.join(save_folder, ip_address)
                                if os.path.exists(save_dir):
                                    delete_files_starting_with(save_dir)
                    
                    last_cleanup_date = get_Report_time(1)
                    write_config_file(gf)     
                except Exception as e:
                    logger.wdlog(f"数据清理处理时出错: {e}")      
            # 控制处理间隔
            time.sleep(min(capture_interval, 1))
            
    except Exception as e:
        logger.wdlog(f"统一图像处理发生错误: {e}")
        logger.wrlog()

# 修改 main_run 函数
def main_run(rtsp_url, client_id, mqtt_client):
    try:
        global stop_thread
        stop_thread = False
        
        # 启动时间对时
        #set_date()
        
        # 创建并启动统一处理线程
        thread = threading.Thread(
            target=unified_image_processing,
            args=(rtsp_url, client_id, mqtt_client),
            name='统一图像处理线程'
        )
        thread.daemon = True
        thread.start()
            
    except Exception as e:
        logger.wdlog(f"主线程运行错误：{str(e)}")
        main_stop()


def main_stop():
    global stop_thread
    stop_thread = True  # 初始化停止标志为False

