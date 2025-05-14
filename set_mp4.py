import cv2
import os
import datetime
from datetime import date, timedelta
import time
import requests
from typing import Optional, Dict, Any
import logger
def upload_file(file_path: str, client_id: str, ipc_id: str, 
                server_url: str = "http://f.hzwkj.cn:60087/api/upload_file",
                max_retries: int = 5) -> Dict[str, Any]:
    """
    上传文件到服务器，支持失败重试
    
    Args:
        file_path: 要上传的文件路径
        client_id: 客户端ID
        ipc_id: 摄像头ID
        server_url: 服务器URL
        max_retries: 最大重试次数
        
    Returns:
        Dict: {
            'success': bool,  # 是否上传成功
            'message': str,   # 结果信息
            'data': Optional[Dict]  # 成功时返回服务器响应数据
        }
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {
            'success': False,
            'message': f'文件不存在: {file_path}',
            'data': None
        }
    
    # 检查文件大小
    if os.path.getsize(file_path) == 0:
        return {
            'success': False,
            'message': f'文件大小为0: {file_path}',
            'data': None
        }
    
    # 重试上传
    for attempt in range(max_retries):
        try:
            # 准备上传数据
            files = {
                'file': open(file_path, 'rb')
            }
            data = {
                'client_id': client_id,
                'ipc_id': ipc_id
            }
            
            # 发送请求
            response = requests.post(
                server_url,
                files=files,
                data=data
            )
            
            # 关闭文件
            files['file'].close()
            
            # 检查响应
            if response.status_code == 200:
                response_data = response.json()
                # 上传成功，删除本地文件
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"删除文件失败: {e}")
                    logger.wrlog()
                
                return {
                    'success': True,
                    'message': '上传成功',
                    'data': response_data['data']
                }
            else:
                print(f"第{attempt + 1}次上传失败，状态码: {response.status_code}")
                
        except Exception as e:
            print(f"第{attempt + 1}次上传出错: {e}")
        
        # 如果不是最后一次尝试，等待1秒后重试
        if attempt < max_retries - 1:
            time.sleep(1)
    
    # 所有重试都失败
    return {
            'success': False,
            'message': f'上传失败，已重试{max_retries}次',
            'data': None
            }

def create_video_from_images(directory, output_file, fps=15):
    # 仅选择以"proframe_"开头的.jpg或.png图片文件
    images = [img for img in os.listdir(directory) if (img.endswith(".jpg") or img.endswith(".png")) and img.startswith("proframe_")]
    images.sort()

    # 读取第一张图片以获取尺寸
    if not images:  # 如果没有找到符合条件的图片，则退出
        print("没有找到以'proframe_'开头的图片文件。")
        return

    first_image_path = os.path.join(directory, images[0])
    frame = cv2.imread(first_image_path)
    height, width, layers = frame.shape

    # 创建临时文件路径
    temp_output = output_file + '.temp.mp4'

    # 创建视频编写器
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(temp_output, fourcc, fps, (width, height))

    # 将图片写入视频
    for image in images:
        image_path = os.path.join(directory, image)
        frame = cv2.imread(image_path)
        video.write(frame)

    # 释放资源
    video.release()

    # 使用ffmpeg将mp4v转换为h.264编码
    try:
        import subprocess
        ffmpeg_cmd = [
            'ffmpeg', '-y',  # -y表示覆盖已存在的文件
            '-i', temp_output,  # 输入文件
            '-c:v', 'libx264',  # 使用h.264编码器
            '-preset', 'medium',  # 编码速度和质量的平衡
            '-crf', '23',  # 控制质量，范围0-51，数字越小质量越好
            output_file  # 输出文件
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        
        # 删除临时文件
        os.remove(temp_output)
        logger.wdlog(f"视频已保存为 {output_file}")
    except Exception as e:
        print(f"转码失败: {e}")
        logger.wrlog()
        # 如果转码失败，保留原始mp4v编码的文件
        os.rename(temp_output, output_file)

# 使用示例
def get_previous_day():
    yesterday = date.today() #- timedelta(days=1)
    return yesterday.strftime("%Y%m%d")

#print(get_previous_day())
def generate_and_upload_video(cliient_id, ipc_id):
    try:
        sdate = get_previous_day()
        directory = f'./img/{ipc_id}'  # 替换为你的图片目录路径
        output_file = f'./img/video_{ipc_id}_{sdate}.mp4'  # 替换为你要保存的视频文件路径
        create_video_from_images(directory, output_file)
        rest = upload_file(output_file, cliient_id, ipc_id)
        logger.wdlog(f"视频发送信息 {rest}")
        return rest
    except Exception as e:
        print(f"生成并上传视频时发生错误: {e}")
        logger.wrlog()
        return None
    



# rtsp_list =[
#         {
#             "dev_name": "墙1",
#             "ip": "192.168.1.65",
#             "rtsp": "rtsp://admin:hzwkj888@192.168.1.65:554/Streaming/Channels/101?transportmode=unicast&profile=Profile_1"
#         },
#         {
#             "dev_name": "桌面",
#             "ip": "192.168.1.199",
#             "rtsp": "rtsp://admin:hzwkj888@192.168.1.199:554/Streaming/Channels/101?transportmode=unicast&profile=Profile_1"
#         }
#     ]
# sdate = "20250501"
# client_id = "4b48e77b0e5d4484bf6e44052ab99458"
# for rtsp in rtsp_list:
#     print(generate_and_upload_video(client_id, rtsp["ip"]))