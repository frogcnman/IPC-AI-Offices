import os, uuid, json, time
import cv2
import udp_get_id
import threading
import time
import json
import paho.mqtt.client as mqtt
import logger
import getonvif
from onvif import ONVIFCamera
import subprocess
import hashlib
import base64
import IPC_img_human
import socket
import web_config 
import datetime

config_zt = False
id_path = r"./user_id.json"
config_path = r"./config.json"
datapath = r"./models"
imgpath = r"./img"

CY_userinfo = [
    {"username": "admin", "passwd": ""},
    {"username": "admin", "passwd": "123"},
    {"username": "admin", "passwd": "1234"},
    {"username": "admin", "passwd": "12345"},
    {"username": "admin", "passwd": "123456"},
    {"username": "admin", "passwd": "888888"},
    {"username": "admin", "passwd": "111111"},
    {"username": "admin", "passwd": "123456"},
    {"username": "Admin", "passwd": "111111"},
    {"username": "admin", "passwd": "admin"},
    {"username": "admin", "passwd": "abc123"},
    {"username": "admin", "passwd": "666666"}
]

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
        logger.wdlog(f"处理消息时出错: {str(e)}")
        return 20

def get_local_ip():
    """
    获取本机在局域网中的IP地址
    :return: 本机IP地址字符串，获取失败返回空字符串
    """
    try:
        # 创建一个UDP套接字
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接一个外部地址，实际不会建立连接
        s.connect(('8.8.8.8', 80))
        # 获取本机IP地址
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.wdlog(f"获取本机IP地址失败: {str(e)}")
        return ""

def md5_base64_encrypt(data):
    # 创建md5对象
    md5_hash = hashlib.md5()

    # 对数据进行编码，然后使用update方法更新hash对象
    md5_hash.update(data.encode('utf-8'))

    # 获取MD5加密后的二进制数据
    md5_binary = md5_hash.digest()

    # 将二进制数据编码为BASE64格式
    base64_encoded = base64.b64encode(md5_binary)

    # 将BASE64编码的数据转换为字符串
    encrypted_data = base64_encoded.decode('utf-8')

    return encrypted_data


def execute_command(command_str):
    """
    执行命令行命令。

    :param command_str: 包含命令和参数的字符串
    :return: 命令的输出
    """
    # 使用shell=True来执行命令，注意这可能会引入安全风险
    result = subprocess.run(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 检查命令是否成功执行
    if result.returncode == 0:
        return result.stdout
    else:
        # 如果命令执行失败，返回错误信息
        return f"Error: {result.stderr}"


def insert_string_into_rtsp(url, insert_str):
    """
    在 rtsp URL 中的 'rtsp://' 后面和 IP 地址/端口前面插入一个字符串。

    参数:
        url (str): 原始 rtsp URL。
        insert_str (str): 需要插入的字符串。

    返回:
        str: 修改后的 rtsp URL。
    """
    if url.startswith("rtsp://"):
        # 分离 "rtsp://" 和后面的内容
        base = "rtsp://"
        rest = url[len(base):]  # 去掉 "rtsp://" 的部分

        # 拼接插入字符串
        modified_url = f"{base}{insert_str}{rest}"
        return modified_url
    else:
        raise ValueError("URL 不以 'rtsp://' 开头")


def get_device_info(ip, port, username, password):
    get_dict = {}
    lst = [{"username": username, "passwd": password}]
    lst = lst + CY_userinfo
    #print(lst)
    for user_i in lst:
        try:
            u_name = user_i.get("username", "")
            p_word = user_i.get("passwd", "")
            # 连接到设备
            print(ip, port, u_name, p_word)
            camera = ONVIFCamera(ip, port, u_name, p_word)

            # 手动获取 media 服务
            media_service = camera.create_media_service()

            # 获取设备配置
            profiles = media_service.GetProfiles()
            if not profiles:
                print("未找到媒体配置文件")
                continue
                # 获取快照 URI

            # 遍历配置文件，提取 RTSP 流 URL
            for index, profile in enumerate(profiles, start=1):
                stream_uri = camera.media.GetStreamUri(
                    {'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
                     'ProfileToken': profile.token})
                # print(f"RTSP Stream URL for Profile {profile.Name}: {stream_uri.Uri}")
                n_url = insert_string_into_rtsp(stream_uri.Uri, f"{u_name}:{p_word}@")
                get_dict[f'rtsp_url{index}'] = n_url
            break
        except Exception as e:
            # 打印出异常信息
            print(f"get_device_info: {e}")
            get_dict = {}
    return get_dict


def get_IPC_NVR_info(ip, port, username, password):
    try:
        get_info = {}
        devlst = []
        # port = 2020  # 设备的端口，通常是 80 或 8080
        # print(ip, prot, username, password)
        getinfo = get_device_info(ip, port, username, password)
        # print(getinfo)
        if getinfo:
            # print('ip:',ip,'port:',port,getinfo)
            getinfo['ip'] = ip
            getinfo['port'] = port
            devlst.append(getinfo)
        if devlst:
            get_info['IPC'] = devlst
        return get_info
    except:
        return get_info


def create_or_read_id_file(filename=id_path):
    try:
        id_file = {"client_id": "", "passwd": ""}
        if not os.path.exists(filename):
            # 文件不存在，创建一个 JSON 文件并写入默认配置
            with open(filename, 'w') as file:
                json.dump(id_file, file, indent=4)
            logger.wdlog(f"配置文件{filename}创建成功")
            return id_file
        else:
            with open(filename, 'r') as file:
                data = json.load(file)
            return data
    except Exception as e:
        logger.wdlog(f"处理消息时出错: {str(e)}")
        return None


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


# 检查config.json配置文件是否存在，不存在则创建，创建时设置预制参数；
def create_config_file(client_id, passwd, filename=config_path, default_config=None):
    # 如果没有提供默认配置，则使用预定义的配置
    if default_config is None:
        # c_id = str(uuid.uuid4())
        rt = get_Report_time()
        default_config = {"mqtt_info": {
            "server": "hzwmqtt.hzwkj.cn",
            "port": 30570,
            "client_id": client_id,
            "username": client_id,
            "password": passwd,
            "topics": [f"/ai_analysis_status/configuration/svr_topic/{client_id}"],
            "publish": f"/ai_analysis_status/configuration/cli_publish/{client_id}"

        },
            "ai_info": {
                "zhipuapi": {"key": "00c80c80f5192d30d0de94941d1628de.mic0bpFJgOqFEC83"
                             }
            },
            "rknn_path": "./data/yolov5s_relu.rknn",
            "RSTP_url": "",
            "warning_txt": [],
            "MP4": True,
            "Report_time": rt
        }

    # 检查文件是否存在
    try:
        if not os.path.exists(filename):
            # 文件不存在，创建一个 JSON 文件并写入默认配置
            with open(filename, 'w') as file:
                json.dump(default_config, file, indent=4)
            logger.wdlog(f"配置文件{filename}创建成功")
            return True
        else:
            return True
    except Exception as e:
        logger.wdlog(f"处理消息时出错: {str(e)}")
        return False


# 文件路径检测
def check_or_create_directory(directory_path):
    # 检查目录是否存在
    try:
        if not os.path.exists(directory_path):
            print(f"目录 {directory_path} 不存在，正在创建...")
            # 创建目录，包括中间的父目录
            os.makedirs(directory_path)
        return True
    except Exception as e:
        logger.wdlog(f"处理消息时出错: {str(e)}")
        return False


# 视频流检测
def check_rtsp_stream(rtsp_list, mqtt_client):
    """
    检查多个RTSP流是否可用
    :param rtsp_list: 包含多个设备信息的列表，每个设备包含dev_name、ip和rtsp地址
    :return: 所有RTSP流都可用返回True，否则返回False
    """
    try:
        if not rtsp_list:
            logger.wdlog("RTSP列表为空")
            return False

        all_streams_valid = True
        try:
            sendlist = []
            for device in rtsp_list:
                rtsp_url = device.get('rtsp', '')
                dev_name = device.get('dev_name', '未知设备')
                ipc_id = device.get('ip', '')
                ipc_state = False
                if not rtsp_url:
                    logger.wdlog(f"设备 {dev_name} 的RTSP地址为空")
                    return False

                # 创建 VideoCapture 对象，尝试连接到 RTSP 流
                cap = cv2.VideoCapture(rtsp_url)
                
                # 检查是否成功打开流
                if not cap.isOpened():
                    logger.wdlog(f"无法打开设备 {dev_name} 的RTSP流: {rtsp_url}")
                    cap.release()
                    ipc_state = False
                else:
                    ipc_state = True

                # 尝试读取第一帧图像以验证流是否有效
                ret, frame = cap.read()
                if not ret:
                    logger.wdlog(f"无法从设备 {dev_name} 的RTSP流获取帧: {rtsp_url}")
                    cap.release()
                    ipc_state = False
                    #return False
                else:
                    ipc_state = True

                logger.wdlog(f"设备 {dev_name} 的RTSP流正常")
                ipc_info = {
                    "ipc_id": ipc_id,
                    "ipc_state": ipc_state,
                    "ipc_name": dev_name,
                    "rtsp_url": rtsp_url
                }
                sendlist.append(ipc_info)
                cap.release()
        finally:
            logger.wdlog(f"所有RTSP流正常")
            if sendlist:
                senddict = {
                    "ipc_info": sendlist
                }
                mqtt_client.publish_message(senddict)
        return all_streams_valid

    except Exception as e:
        logger.wdlog(f"检查RTSP流时出错: {str(e)}")
        return False


# 自定义MQTT类
class MQTTClient:
    def __init__(self, config):
        self.MQTTHOST = config.get('server')
        self.MQTTPORT = config.get('port')
        self.clientid = config.get('clientid')
        self.username = config.get('username')
        self.password = config.get('password')
        self.topics = config.get('topics')
        self.publish_topic = config.get('publish')
        self.client = mqtt.Client(client_id=self.clientid, clean_session=True)  # mqtt.Client(self.clientid)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.username_pw_set(self.username, self.password)
        self.running = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.wdlog("Connected to MQTT Broker!")
            for topic in self.topics:
                self.client.subscribe(topic)
        else:
            logger.wdlog("Failed to connect, return code %d\n", rc)

    def on_message(self, client, userdata, msg):
        # 收到消息处理消息
        global config_zt
        get_config = False
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        msg_dict = json.loads(msg.payload.decode())
        if msg_dict:
            get_command = msg_dict.get("command", "")
            # config 是配置标志 0 表示配置 1 指定IP 端口 用户名 密码 进行配置 100重启服务；
            if get_command == "config":  # {"command":"config","type":0,"ip":"",port"","username":"","passwd":""}
                config_type = msg_dict.get("type", -1)
                if config_type == 0:
                    # print('本地设置1')
                    user_name = msg_dict.get("username", "")
                    pass_wd = msg_dict.get("passwd", "")
                    warning_txt = msg_dict.get("warning_txt", "")
                    MP4 = msg_dict.get("MP4", True)
                    #Report_time = msg_dict.get("Report_time", 12)
                    ai_info = msg_dict.get("ai_info", "")#{"zhipuapi": {"key": "00c80c80f5192d30d0de94941d1628de.mic0bpFJgOqFEC83"}}
                    open_devices = getonvif.getonviflst()
                    if open_devices:
                        if len(open_devices) == 1:
                            ip = str(open_devices[0][0])
                            port = int(open_devices[0][1])
                            # print(f"IP:{ip}{type(ip)},PORT:{port}{type(port)},User:{user_name}{type(user_name)},Pass:{pass_wd}{type(pass_wd)}")
                            time.sleep(0.1)
                            dev_dict = get_IPC_NVR_info(ip, port, user_name, pass_wd,)
                            print(dev_dict)
                            lst = dev_dict.get("IPC", [])
                            if lst:
                                print("找到可用的摄像头地址：", lst)
                                rtsp_url = lst[0].get("rtsp_url1", {})
                                print(f"{rtsp_url}")
                                # 保存摄像头rtsp地址
                                f_config = read_config_file()
                                if f_config:
                                    f_config["RSTP_url"] = rtsp_url
                                    f_config["warning_txt"] = warning_txt
                                    f_config["MP4"] = MP4
                                    #f_config["Report_time"] = Report_time
                                    f_config["ai_info"] = ai_info
                                    write_config_file(f_config)
                                    # 正常获取RTSP地址流
                                    logger.wdlog(f'获取配置信息：{f_config}')
                                    set_config = {"command": "config", "type": 100, "rtsp": rtsp_url}
                                    get_config = True
                                else:
                                    # 读取本地config 保存错误
                                    set_config = {"command": "config", "type": -101}
                            else:
                                # 没有找到可用的摄像头RTSP地址！
                                set_config = {"command": "config", "type": -100}
                            # set_config = {"command": "config", "type": 99, "IPC": open_devices}
                        elif len(open_devices) > 1:
                            # 返回摄像头不止一个，需要用户指定
                            set_config = {"command": "config", "type": 1, "IPC": open_devices}

                    else:
                        # 没有找到可用的摄像头
                        set_config = {"command": "config", "type": -99}
                    # 发送返回信息
                    self.publish_message(set_config)
                elif config_type == 1:
                    # print('本地设置2')
                    a_ip = msg_dict.get("ip", "")
                    a_port = msg_dict.get("port", "")
                    u_name = msg_dict.get("username", "")
                    p_wd = msg_dict.get("passwd", "")
                    warning_txt = msg_dict.get("warning_txt", "")
                    MP4 = msg_dict.get("MP4", True)
                    #Report_time = msg_dict.get("Report_time", 12)
                    ai_info = msg_dict.get("ai_info", "")
                    dev_dict = get_IPC_NVR_info(a_ip, a_port, u_name, p_wd)
                    lst = dev_dict.get("IPC", [])
                    if lst:
                        # print("找到可用的摄像头地址：")
                        rtsp_url = lst[0].get("rtsp_url1", {})
                        print(f"{rtsp_url}")
                        # 保存摄像头rtsp地址
                        f_config = read_config_file()
                        if f_config:
                            f_config["RSTP_url"] = rtsp_url
                            f_config["warning_txt"] = warning_txt
                            f_config["MP4"] = MP4
                            #f_config["Report_time"] = Report_time
                            f_config["ai_info"] = ai_info
                            write_config_file(f_config)
                            # 正常获取RTSP地址流
                            logger.wdlog(f'获取配置信息：{f_config}')
                            set_config = {"command": "config", "type": 100, "rtsp": rtsp_url}
                            get_config = True
                        else:
                            # 读取本地config 保存错误
                            set_config = {"command": "config", "type": -101}
                    else:
                        # 没有找到可用的摄像头RTSP地址！
                        set_config = {"command": "config", "type": -100}
                    # 发送返回信息
                    self.publish_message(set_config)
                elif config_type == 100:#初始化系统
                    set_config = {"command": "config", "type": 100}
                    # 发送返回信息
                    self.publish_message(set_config)
                    time.sleep(2)
                    #删除config.json 文件
                    execute_command(r"rm ./config.json")
                    #删除img/cache 目录下所有文件
                    execute_command(r"rm ./img/cache/*.jpg")
                    config_zt = True
                else:
                    print('over')
            elif get_command == "cmd":
                # cmd 表示远程指令操作，这里可以实现重启、远程升级等；可以远程执行命令行或脚本；
                cmd_txt = msg_dict.get("cmd_txt", "")
                get_verify = msg_dict.get("get_verify", "")
                e_verify = md5_base64_encrypt("Hzwkj@888" + cmd_txt)
                if cmd_txt and get_verify == e_verify:
                    get = execute_command(cmd_txt)
                    set_cmd = {"command": "cmd", "execution": get}
                    # 发送返回信息
                    self.publish_message(set_cmd)
        if get_config:
            config_zt = True

    def publish_message(self, payload, pub=None, qos=1):
        if pub is None:  # 如果没有指定发布主题，使用实例的 `publish_topic`
            pub = self.publish_topic
        set_json = json.dumps(payload)
        result = self.client.publish(pub, set_json, qos)
        # status = result[0]
        # if status == 0:
        #     logger.wdlog(f"Send `{payload}` to topic `{self.publish_topic}`")
        # else:
        #     logger.wdlog(f"Failed to send message to topic {self.publish_topic}")

    # def connect(self):
    #     self.client.connect(self.MQTTHOST, self.MQTTPORT, 60)
    #     self.client.loop_start()
    #
    # def disconnect(self):
    #     self.client.loop_stop()
    #     self.client.disconnect()
    #
    # def start(self):
    #     thread = threading.Thread(target=self.connect)
    #     thread.start()
    def connect(self):
        self.running = True
        self.client.connect(self.MQTTHOST, self.MQTTPORT, 60)
        self.client.loop_start()
        while self.running:
            time.sleep(1)  # 检查间隔可以根据需要调整
        self.disconnect()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def start(self):
        self.thread = threading.Thread(target=self.connect)
        self.thread.start()

    def stop(self):
        self.running = False
        time.sleep(1)
        self.thread.join()  # 等待线程结束


# 程序初始化进行自检；
# 初始化文件夹；没有则创建，初始化文件
# /logs /data /img/cache 没有则创建；
def IPC_ini():
    try:
        getid = create_or_read_id_file()
        if not getid:
            logger.wdlog('user_id.json创建或读取失败！程序退出。')
            exit(0)
        else:
            client_id = getid.get("client_id", "")
            if not client_id:
                logger.wdlog('启动client_id 获取')
                # 初始化设备ID，获取ID后设备重启；
                try:
                    un, pw = udp_get_id.tcp_direct_request()
                    if un and pw:
                        id_file = {"client_id": un, "passwd": pw}
                        write_config_file(id_file, id_path)
                        IPC_ini()
                except Exception as e:
                    logger.wdlog(f"处理RTSP 流时出错: {str(e)}")
                    #return False
            else:
                # 已经获取client_id
                pw = getid.get("passwd", "")
                if create_config_file(client_id, pw):
                    logger.wdlog('config.json存在')
                    f_config = read_config_file()
                    if f_config:
                        logger.wdlog("成功读取config.json配置文件")
                        
                        # 1. 首先检查所有必要的目录和文件
                        required_paths = [
                            (imgpath, "图像缓存目录"),
                            (datapath, "数据存储目录")#,(f_config.get("rknn_path", ""), "RKNN模型文件")
                        ]
                        
                        for path, desc in required_paths:
                            if not os.path.exists(path):
                                logger.wdlog(f"{desc}不存在，程序退出")
                                return False
                        
                        # 2. 初始化配置参数
                        mqtt_info = f_config.get("mqtt_info", {})
                        if not mqtt_info:
                            logger.wdlog("MQTT配置项为空，程序退出")
                            return False
                        
                        # 3. 初始化业务参数
                        init_params = {
                            #"Report_time": f_config.get("Report_time", 12),
                            "MP4": f_config.get("MP4", True),
                            "akey": f_config.get("ai_info", {}).get("zhipuapi", {}).get("key", ""),
                            "full_text": f_config.get("warning_txt", "")
                        }
                            
                        # # 单独设置其他配置
                        # IPC_img_human.warning_txt = f_config.get("warning_txt", "")
                        # IPC_img_human.ai_info = f_config.get("ai_info", {})
                        
                        # if not IPC_img_human.set_configinfo(**init_params):
                        #     logger.wdlog("业务参数初始化失败")
                        #     return False
                        
                        # 4. 启动MQTT客户端
                        try:
                            mqtt_client = MQTTClient(mqtt_info)
                            mqtt_client.start()
                            time.sleep(5)  # 等待MQTT连接建立
                            
                            # 5. 发送本地IP信息
                            local_ip = get_local_ip()
                            if not local_ip:
                                logger.wdlog("获取本地IP失败")
                                #return False
                                
                            IPC_host = f"{local_ip}"
                            sendmsg = {
                                "set_ip": {
                                    "userid": client_id,
                                    "Ip": IPC_host
                                    }              
                            }
                            logger.wdlog(f"发送IP信息：{sendmsg}")
                            mqtt_client.publish_message(sendmsg)
                            
                            #6. 启动Web服务
                            web_config.run_web_server(client_id)
                            
                            # 7. 检查RTSP流并启动业务
                            rtsp_url = f_config.get("RSTP_url", [])
                            if rtsp_url and check_rtsp_stream(rtsp_url, mqtt_client):
                                logger.wdlog(f"RTSP流检查通过，启动业务处理{rtsp_url},{client_id}")
                                IPC_img_human.main_run(rtsp_url, client_id, mqtt_client)
                            else:
                                logger.wdlog("RTSP流无效")
                            
                            # 8. 主循环监控
                            global config_zt
                            while True:
                                #print(f"当前Web配置状态{web_config.get_devices_config_status()},当前配置重启状态{config_zt}")
                                if web_config.get_devices_config_status():
                                    config_zt = True
                                    web_config.reset_devices_config_status()    
                                if config_zt:
                                    try:
                                        logger.wdlog("收到重启信号")
                                        config_zt = False
                                        try:
                                            web_config.stop_web_server() 
                                            logger.wdlog("web服务停止成功")
                                        except Exception as e:
                                            logger.wdlog(f"停止Web服务时发生错误: {str(e)}")
                                        try:
                                            IPC_img_human.main_stop()
                                            logger.wdlog("图像业务服务停止成功")
                                        except Exception as e:
                                            logger.wdlog(f"停止业务处理时发生错误: {str(e)}")
                                        try:
                                            mqtt_client.stop()
                                            logger.wdlog("MQTT客户端停止成功")
                                        except Exception as e:
                                            logger.wdlog(f"停止MQTT客户端时发生错误: {str(e)}")
                                                                              
                                        time.sleep(5)
                                        return IPC_ini()  # 重新初始化
                                    except Exception as e:
                                        logger.wdlog(f"重启过程发生错误: {str(e)}")
                                        return IPC_ini()
                                time.sleep(3)
                                
                        except Exception as e:
                            logger.wdlog(f"MQTT或业务启动错误: {str(e)}")
                            return False
                            
                    else:
                        logger.wdlog("配置文件读取失败")
                        return False
                else:
                    logger.wdlog('配置文件创建失败')
                    return False
                    
    except Exception as e:
        logger.wdlog(f"初始化过程发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    retry_count = 0
    max_retries = 100
    
    while retry_count < max_retries:
        try:
            if IPC_ini():
                break
            retry_count += 1
            logger.wdlog(f"初始化失败，第{retry_count}次重试")
            time.sleep(5)
        except Exception as e:
            logger.wdlog(f"程序异常退出: {str(e)}")
            retry_count += 1
            time.sleep(5)
            
    if retry_count >= max_retries:
        logger.wdlog("达到最大重试次数，程序退出")


