import socket
from concurrent.futures import ThreadPoolExecutor
import ipaddress
from onvif import ONVIFCamera
import time, sys
import requests
from bs4 import BeautifulSoup
import psutil
from zeep.helpers import serialize_object
import getonvif

# 定义要扫描的端口列表
ports_to_scan = [554, 8554, 2020, 8000, 8080, 8088, 6688]

# 设定最大扫描线程数
MAX_THREADS = 100

CY_userinfo = [
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


def scan_ports(ip, ports):
    open_ports = []
    for port in ports:
        try:
            # 尝试连接指定的端口
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 设置超时时间为2秒
            result = sock.connect_ex((ip, port))
            if result == 0:  # 如果连接成功，端口开放
                open_ports.append(port)
            sock.close()
        except socket.error:
            continue  # 如果连接失败，跳过
    return ip, open_ports


def get_hostname(ip, port=80):
    try:
        # 尝试发起 HTTP 请求
        url = f"http://{ip}:{port}"
        response = requests.get(url, timeout=2)  # 设置超时时间为2秒
        response.raise_for_status()  # 如果请求失败，将抛出异常

        # 使用 BeautifulSoup 解析网页内容
        soup = BeautifulSoup(response.text, 'html.parser')

        # 获取 <title> 标签的内容
        title = soup.title.string if soup.title else 'No title found'
        return title
    except requests.exceptions.RequestException as e:
        # print(f"无法获取 {ip} 的 HTTP 响应: {e}")
        return None


def scan_ip_range(start_ip, end_ip):
    open_devices = []

    # 使用线程池并行扫描
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = []
        for ip_int in range(start_ip, end_ip + 1):
            ip = str(ipaddress.IPv4Address(ip_int))
            futures.append(executor.submit(scan_ports, ip, ports_to_scan))

        for future in futures:
            ip, open_ports = future.result()
            if len(open_ports) >= 2:  # 如果至少有两个端口开放
                hostname = get_hostname(ip)  # 获取主机名
                open_devices.append((ip, open_ports, hostname))

    return open_devices


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
    for user_i in lst:
        try:
            u_name = user_i.get("username", "")
            p_word = user_i.get("passwd", "")
            # 连接到设备
            camera = ONVIFCamera(ip, port, u_name, p_word)

            # 手动获取 media 服务
            media_service = camera.create_media_service()
            # # 获取设备信息
            # device_info = serialize_object(camera.devicemgmt.GetDeviceInformation())
            #
            # # print(type(device_info))
            # if device_info:
            #     get_dict['dev_name'] = device_info.get('Manufacturer', '') + device_info.get('Model', '')
            # 获取设备配置
            profiles = media_service.GetProfiles()
            # print(f"Number of Profiles: {len(profiles)}")
            if not profiles:
                print("未找到媒体配置文件")
                break
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


def get_network_info():
    # 获取网络接口信息
    interfaces = psutil.net_if_addrs()
    for interface, addrs in interfaces.items():
        # 排除掉 lo 和 docker0 接口
        if interface in ['lo', 'docker0']:
            continue
        for addr in addrs:
            # 查找 IPv4 地址和对应的子网掩码
            if addr.family == socket.AF_INET:
                ip_address = addr.address
                netmask = addr.netmask
                return ip_address, netmask
    return None, None


def get_network():
    ip, netmask = get_network_info()
    if ip and netmask:
        # 使用 ipaddress 库计算网络地址
        network = ipaddress.IPv4Network(f'{ip}/{netmask}', strict=False)
        return network.network_address
    else:
        return None


def get_IPCorNVR(network):
    try:
        bt = time.time()
        network = ipaddress.IPv4Network(f"{network}/24")
        start_ip = int(network.network_address)
        end_ip = int(network.broadcast_address)
        # 扫描局域网中的设备
        open_devices = scan_ip_range(start_ip, end_ip)
        et = time.time() - bt
        # print(f"用时：{et:.2f}秒")
        return open_devices
    except:
        return None


def get_IPC_NVR_info(ip, port, username, password):  # 修正参数名称
    try:
        get_info = {}
        devlst = []
        getinfo = get_device_info(ip, port, username, password)
        if getinfo:
            getinfo['ip'] = ip
            getinfo['port'] = port
            devlst.append(getinfo)
        if devlst:
            get_info['IPC'] = devlst
        return get_info
    except Exception as e:
        print(f"获取IPC信息错误: {str(e)}")  # 添加错误输出
        return {}


if __name__ == "__main__":
    # print("网段查询中...", end='', flush=True)
    # network = get_network()
    # sys.stdout.write('\r')
    # sys.stdout.flush()
    # print(f"所在网段: {network}")
    # # 扫描网段 192.168.1.1 到 192.168.1.255
    # print("扫描网络IPC...", end='', flush=True)
    # open_devices = get_IPCorNVR(network)
    # # open_devices = [('192.168.10.200', [80, 8000], 'NVR'), ('192.168.10.201', [80, 554, 8088], None), ('192.168.10.202', [80, 554, 8088], None), ('192.168.10.203', [80, 554, 2020], 'IPC'), ('192.168.10.222', [80, 554, 2020], 'IPC')]
    print("扫描网络IPC...", end='', flush=True)

    open_devices = getonvif.getonviflst()
    sys.stdout.write('\r')
    sys.stdout.flush()
    print('扫描IPC结果：', open_devices)
    username = input("请输入摄像头用户名:")  # 'admin'  # 设备的用户名
    password = input("请输入摄像头密码:")  # 'hzwkj888'  # 设备的密码
    ipc_index = input(f"请输入摄像头编号[0-{len(open_devices)-1}]:")
    try:
        if not ipc_index:
            i_i = 0
        else:
            i_i = int(ipc_index)
        if i_i+1 >len(open_devices):
            print('超出输入范围的整数')
            eixt(0)
    except:
        print('您输入的不是整数！')
        exit(0)
    if username == "":
        username = "admin"
    print("分析IPC信息中...", end='', flush=True)
    ip = open_devices[i_i][0]
    port = open_devices[i_i][1]
    dev_dict = get_IPC_NVR_info(ip,port, username, password)
    sys.stdout.write('\r')
    sys.stdout.flush()
    print(dev_dict)
# {'IPC': [{'dev_name': 'IPCAMC6F0SoZ3N0PmL2', 'rtsp_url1': 'rtsp://admin:hzwkj888@192.168.10.201:554/11', 'rtsp_url2': 'rtsp://admin:hzwkj888@192.168.10.201:554/12', 'ip': '192.168.10.201', 'port': 8088}, {'dev_name': 'IPCAMC6F0SoZ3N0PmL2', 'rtsp_url1': 'rtsp://admin:hzwkj888@192.168.10.202:554/11', 'rtsp_url2': 'rtsp://admin:hzwkj888@192.168.10.202:554/12', 'ip': '192.168.10.202', 'port': 8088}, {'dev_name': 'TP-LinkTL-IPC44KW-ZOOM-DUAL', 'rtsp_url1': 'rtsp://admin:hzwkj888@192.168.10.203:554/stream1', 'rtsp_url2': 'rtsp://admin:hzwkj888@192.168.10.203:554/stream2', 'ip': '192.168.10.203', 'port': 80}, {'dev_name': 'ANJIAAJ0525', 'rtsp_url1': 'rtsp://admin:123456@192.168.10.205:8554/profile0', 'rtsp_url2': 'rtsp://admin:123456@192.168.10.205:8554/profile1', 'ip': '192.168.10.205', 'port': 6688}, {'dev_name': 'TP-LinkTL-IPC56CE', 'rtsp_url1': 'rtsp://admin:hzwkj888@192.168.10.222:554/stream1', 'rtsp_url2': 'rtsp://admin:hzwkj888@192.168.10.222:554/stream2', 'ip': '192.168.10.222', 'port': 80}]}
"""
业务流程规划：
通过MQTT进行业务数据交互：
设计本地Config文件保存初始化信息：
每个3566 设备需要一个序列号，作为MQTT通讯标志；
1.初始化获取视频流地址（摄像头配置）；
    1.0.通过序列号绑定用户微信和设备；
    1.1.用户扫描本地支持Onvif协议的IPC(可手工输入IP地址或)；
    1.2.引导用户配置账户和密码（内置字典，穷举进行破解）；这里需要提示用户在哪里能够获取账号和密码；
    1.3.通过Onvif协议获取IPC RTSP拉流地址（可手工配置RTSP地址）；
    1.4.通过CV2对RTSP地址进行有效验证，通过验证保存至Config完成摄像头配置；
2.配置用户信息及初始化参数；
    1.1.配置用户监控主体名称（我家、妈妈家）；
    1.2.配置家庭成员；
    1.3.配置关心项（预制项、可编辑）；
    1.4.配置24小时统计时间（默认中午12点）；
    1.5.配置是否需要生成每日视屏；
3.启动业务流程；
    1.1.通过视频流+人体识别+AI图像分析+文字意图，得到文字信息；
    1.2.通过MQTT发送信息
    1.3.通过微信公众号，推送预警、日报；
"""