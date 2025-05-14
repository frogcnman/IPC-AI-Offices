from flask import Flask, render_template, jsonify, request
import json
import os,time
from onvif import ONVIFCamera
from zeep.helpers import serialize_object
import threading
import logger
import qrcode
from PIL import Image

app = Flask(__name__)
CONFIG_FILE = 'config/ipc_config.json'

Set_devices_type = False
web_server_thread = None
server_running = False
# 常量定义
CY_USERINFO = [
    {"username": "admin", "passwd": "123"},
    {"username": "admin", "passwd": ""},
    {"username": "admin", "passwd": "888888"},
    {"username": "admin", "passwd": "111111"},
    {"username": "admin", "passwd": "123456"},
    {"username": "Admin", "passwd": "111111"},
    {"username": "admin", "passwd": "admin"},
    {"username": "admin", "passwd": "abc123"},
    {"username": "admin", "passwd": "666666"}
]

def generate_qrcode(text, filename='qrcode.png'):
    """
    生成二维码图片
    :param text: 要转换的文本内容
    :param filename: 保存的文件名，默认为 qrcode.png
    :return: 生成的图片路径
    """
    try:
        # 创建QRCode对象
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # 添加数据
        qr.add_data(text)
        qr.make(fit=True)
        
        # 创建图片
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 确保static目录存在
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        os.makedirs(static_dir, exist_ok=True)
        save_path = os.path.join(static_dir, filename)
        
        # 保存图片
        img.save(save_path)
        logger.wdlog(f"二维码已生成: {save_path}")
        return save_path
    except Exception as e:
        logger.wdlog(f"生成二维码失败: {str(e)}")
        return None

def get_devices_config_status():
    """
    获取设备配置状态
    """
    global Set_devices_type
    return Set_devices_type

def reset_devices_config_status():
    """
    重置设备配置状态
    """
    global Set_devices_type
    Set_devices_type = False

def insert_string_into_rtsp(url, insert_str):
    if url.startswith("rtsp://"):
        base = "rtsp://"
        rest = url[len(base):]
        return f"{base}{insert_str}{rest}"
    else:
        raise ValueError("URL 不以 'rtsp://' 开头")

def get_device_info(ip, port, username, password):
    get_dict = {}
    lst = [{"username": username, "passwd": password}]
    lst = lst + CY_USERINFO
    
    for user_i in lst:
        try:
            u_name = user_i.get("username", "")
            p_word = user_i.get("passwd", "")
            camera = ONVIFCamera(ip, port, u_name, p_word)
            media_service = camera.create_media_service()
            profiles = media_service.GetProfiles()
            
            if not profiles:
                print("未找到媒体配置文件")
                break

            for index, profile in enumerate(profiles, start=1):
                stream_uri = camera.media.GetStreamUri({
                    'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
                    'ProfileToken': profile.token
                })
                n_url = insert_string_into_rtsp(stream_uri.Uri, f"{u_name}:{p_word}@")
                get_dict[f'rtsp_url{index}'] = n_url
            break
        except Exception as e:
            print(f"get_device_info: {e}")
            get_dict = {}
    return get_dict

def get_IPC_NVR_info(ip, port, username, password):
    try:
        get_info = {}
        devlst = []
        getinfo = get_device_info(ip, port, username, password)
        if getinfo:
            getinfo['ip'] = ip
            getinfo['port'] = port
            # 如果没有设备名称，设置一个默认值
            if 'dev_name' not in getinfo:
                getinfo['dev_name'] = f'IPC_{ip}'
            devlst.append(getinfo)
        if devlst:
            get_info['IPC'] = devlst
        return get_info
    except Exception as e:
        print(f"获取IPC信息错误: {str(e)}")
        return {}

@app.route('/')
def index():
    return render_template('ipc_config.html')

@app.route('/api/scan_devices', methods=['GET'])
def scan_devices():
    try:
        global Set_devices_type
        import getonvif
        devices = getonvif.getonviflst()
        if devices:
            formatted_devices = []
            # 读取已保存的配置
            saved_config = {'IPC': []}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    saved_config = json.load(f)

            for device in devices:
                device_info = {
                    'ip': device[0],
                    'port': device[1],
                    'rtsp_url1': '',
                    'dev_name': f'IPC_{device[0]}'
                }
                
                # 查找已保存的设备信息
                for saved_device in saved_config.get('IPC', []):
                    if saved_device['ip'] == device[0]:
                        device_info['rtsp_url1'] = saved_device.get('rtsp_url1', '')
                        device_info['dev_name'] = saved_device.get('dev_name', device_info['dev_name'])
                        break
                
                formatted_devices.append(device_info)
                Set_devices_type = False
            return jsonify({'status': 'success', 'devices': formatted_devices})
        return jsonify({'status': 'error', 'message': '未发现设备'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/get_rtsp', methods=['POST'])
def get_rtsp():
    try:
        data = request.json
        ip = data.get('ip')
        port = int(data.get('port'))
        username = data.get('username', 'admin')
        password = data.get('password', '')
        dev_name = data.get('dev_name', f'IPC_{ip}')  # 获取设备名称
        
        print(f"尝试获取RTSP - IP:{ip} Port:{port} User:{username}")
        
        info = get_IPC_NVR_info(ip=ip, port=port, username=username, password=password)
        if info and 'IPC' in info:
            # 设置设备名称
            info['IPC'][0]['dev_name'] = dev_name
            save_config(info)
            return jsonify({'status': 'success', 'info': info})
        return jsonify({'status': 'error', 'message': '获取RTSP信息失败'})
    except Exception as e:
        print(f"RTSP获取异常: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取失败: {str(e)}'})

def save_config(config):
    os.makedirs('config', exist_ok=True)
    existing_config = {'IPC': []}
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                existing_config = json.load(f)
        except Exception as e:
            print(f"读取配置文件失败: {e}")

    if 'IPC' in config:
        new_devices = config['IPC']
        for new_device in new_devices:
            # 确保设备信息完整
            if not all(key in new_device for key in ['ip', 'rtsp_url1']):
                print(f"设备信息不完整: {new_device}")
                continue
                
            # 确保设备名称存在
            if 'dev_name' not in new_device or not new_device['dev_name']:
                new_device['dev_name'] = f'IPC_{new_device["ip"]}'
                
            # 统一设备信息结构
            device_info = {
                'ip': new_device['ip'],
                'port': new_device.get('port', 80),
                'dev_name': new_device['dev_name'],
                'rtsp_url1': new_device['rtsp_url1'],
                'rtsp_url2': new_device.get('rtsp_url2', '')
            }
            
            # 更新或添加设备信息
            device_exists = False
            for i, device in enumerate(existing_config['IPC']):
                if device['ip'] == device_info['ip']:
                    existing_config['IPC'][i] = device_info
                    device_exists = True
                    break
            
            if not device_exists:
                existing_config['IPC'].append(device_info)

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(existing_config, f, indent=4)
        return True
    except Exception as e:
        print(f"保存配置文件失败: {e}")
        return False

@app.route('/api/save_device_name', methods=['POST'])
def save_device_name():
    try:
        data = request.json
        ip = data.get('ip')
        dev_name = data.get('dev_name')  # 修改参数名以匹配前端
        rtsp_url1 = data.get('rtsp_url1', '')
        
        if not ip or not dev_name:
            return jsonify({'status': 'error', 'message': '参数不完整'})
        
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            device_found = False
            for device in config.get('IPC', []):
                if device['ip'] == ip:
                    new_config = {
                        'IPC': [{
                            'ip': ip,
                            'dev_name': dev_name,
                            'rtsp_url1': rtsp_url1 or device.get('rtsp_url1', ''),
                            'port': device.get('port', 80),
                            'rtsp_url2': device.get('rtsp_url2', '')
                        }]
                    }
                    if save_config(new_config):
                        device_found = True
                        break
            
            if device_found:
                return jsonify({'status': 'success'})
        
        return jsonify({'status': 'error', 'message': '设备未找到或保存失败'})
    except Exception as e:
        print(f"保存设备名称失败: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/save_all_devices', methods=['POST'])
def save_all_devices():
    try:
        global Set_devices_type
        data = request.json
        devices = data.get('devices', [])
        
        print("\n开始处理设备配置...")
        # 创建设备信息JSON
        devices_info = []
        for device in devices:
            device_info = {
                "dev_name": device.get('dev_name', '未知'),
                "ip": device.get('ip', '未知'),
                "rtsp": device.get('rtsp_url1', '未知')
            }
            devices_info.append(device_info)
        
        # 打印格式化的JSON信息
        print("\n设备配置信息:")
        print(json.dumps(devices_info, ensure_ascii=False, indent=4))
        
        # 保存到config.json文件
        config_path = './config.json'
        try:
            # 读取现有配置
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # 更新RTSP_url字段
            if len(devices_info) > 0:
                # 使用第一个设备的RTSP URL
                config['RSTP_url'] = devices_info
                
                # 保存更新后的配置
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                Set_devices_type = True
                logger.wdlog(f'当前配置状态{Set_devices_type}')
                return jsonify({
                    'status': 'success',
                    'message': '配置保存成功,系统重启请稍后...',
                    'devices': devices_info
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '没有可用的设备信息'
                })
                
        except Exception as e:
            print(f"保存到config.json失败: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'保存配置失败: {str(e)}'
            })
            
    except Exception as e:
        print(f"处理设备配置失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/get_saved_devices', methods=['GET'])
def get_saved_devices():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return jsonify({'status': 'success', 'devices': config.get('IPC', [])})
        return jsonify({'status': 'success', 'devices': []})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """
    关闭Flask服务器的路由
    """
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('未找到Web服务器')
    func()
    return 'Web服务器正在关闭...'

def start_web_server():
    """
    启动Web服务器的函数
    """
    app.run(host='0.0.0.0', port=8088, debug=False)


def run_web_server(client_id):
    """
    在新线程中启动Web服务器
    """
    global web_server_thread, server_running
    if not server_running:
        if client_id:
            generate_qrcode(client_id)
            time.sleep(1)
        web_server_thread = threading.Thread(target=start_web_server)
        web_server_thread.daemon = True
        server_running = True
        web_server_thread.start()
        logger.wdlog("Web服务器启动成功")
        return web_server_thread
    return None

def stop_web_server():
    """
    停止Web服务器
    """
    global web_server_thread, server_running
    if server_running and web_server_thread:
        try:
            # 发送关闭请求
            import requests
            requests.post('http://localhost:8088/shutdown')
            server_running = False
            web_server_thread.join(timeout=5)
            web_server_thread = None
            logger.wdlog("Web服务器已停止")
            return True
        except Exception as e:
            logger.wdlog(f"停止Web服务器时出错: {str(e)}")
            return False
    return False
#配置IPCWEB页面；
# if __name__ == '__main__':
#     run_web_server()
#     # 保持主线程运行
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("Web服务器停止运行")