import socket, time
import hashlib, base64


def md5_encrypt(data):
    # 创建md5对象
    md5_hash = hashlib.md5()

    # 对数据进行编码，然后使用update方法更新hash对象
    md5_hash.update(data.encode('utf-8'))

    # 获取16进制的加密结果
    encrypted_data = md5_hash.hexdigest()

    return encrypted_data


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


def udp_broadcast_example(max_retries=3, retry_delay=1.0):
    for attempt in range(max_retries):
        send_sock = None
        sock = None
        try:
            # 创建UDP套接字
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # 设置超时
            send_sock.settimeout(5.0)  # 5秒超时
            
            # 广播地址和端口
            broadcast_address = '255.255.255.255'
            port = 9527
            # 要发送的消息
            message = 'C8FF2CDCD6A183742A6D633FC403391F'
            # 发送广播消息
            send_sock.sendto(message.encode(), (broadcast_address, port))
            # 关闭套接字
            send_sock.close()
        except Exception as e:
            print(f"尝试 {attempt + 1}/{max_retries} 失败: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        finally:
            if send_sock:
                send_sock.close()
            if sock:
                sock.close()
    return None, None


def tcp_direct_request(server_ip="f.hzwkj.cn", max_retries=3, retry_delay=1.0):
    """
    直接连接外网服务器获取账号密码
    server_ip: 外网服务器IP地址
    """
    for attempt in range(max_retries):
        sock = None
        try:
            # 创建TCP套接字
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)  # 增加超时时间到10秒
            
            # 服务器地址和端口
            server_address = (server_ip, 19527)
            message = 'C8FF2CDCD6A183742A6D633FC403391F'
            
            # 连接服务器
            print(f"正在连接服务器 {server_ip}...")
            sock.connect(server_address)
            
            # 发送注册请求
            sock.send(message.encode())
            print(f"已发送注册请求到服务器")
            
            # 等待服务器响应
            data = sock.recv(1024)
            if data:
                id = data.decode()
                un = md5_encrypt(id)
                pw = md5_base64_encrypt(un)
                print("收到服务器响应，发送确认...")
                sock.send("02F8228F9E18766146E938A32EC1F549".encode())
                time.sleep(0.5)  # 确保数据发送完成
                print(f"注册成功！")
                return un, pw
                
        except socket.timeout:
            print(f"连接超时，尝试 {attempt + 1}/{max_retries}")
        except ConnectionRefusedError:
            print(f"连接被拒绝，尝试 {attempt + 1}/{max_retries}")
        except Exception as e:
            print(f"尝试 {attempt + 1}/{max_retries} 失败: {str(e)}")
        finally:
            if sock:
                sock.close()
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
                
    return None, None

# if __name__ == "__main__":
#     # 测试外网注册
#     server_ip = "f.hzwkj.cn"
#     print(f"开始连接服务器: {server_ip}")
#     un, pw = tcp_direct_request(server_ip)
#     if un and pw:
#         print(f"用户名: {un}")
#         print(f"密码: {pw}")
#     else:
#         print("注册失败")
