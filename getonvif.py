import socket
import xml.etree.ElementTree as ET
import re
from urllib.parse import urlparse

# ONVIF Discovery constants
MULTICAST_ADDRESS = '239.255.255.250'
PORT = 3702
MESSAGE = \
    '<?xml version="1.0" encoding="UTF-8"?>' \
    '<Envelope xmlns:dn="http://www.onvif.org/ver10/network/wsdl" ' \
    'xmlns="http://www.w3.org/2003/05/soap-envelope">' \
    '<Header>' \
    '<wsa:MessageID xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">uuid:1</wsa:MessageID>' \
    '<wsa:To xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>' \
    '<wsa:Action xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>' \
    '</Header>' \
    '<Body>' \
    '<Probe xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ' \
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema" ' \
    'xmlns="http://schemas.xmlsoap.org/ws/2005/04/discovery">' \
    '<Types>dn:NetworkVideoTransmitter</Types>' \
    '<Scopes />' \
    '</Probe>' \
    '</Body>' \
    '</Envelope>'

def get_xmlinfo(G_xml):
    try:
        get_str = ""
        root = ET.fromstring(G_xml)
        namespace = {'wsdd': 'http://schemas.xmlsoap.org/ws/2005/04/discovery'}
        xaddrs_element = root.find('.//wsdd:XAddrs', namespace)
        if xaddrs_element is not None:
            get_str = xaddrs_element.text
        else:
            get_str = ""
    except Exception as e:
        print(f"get_device_info: {e}")
    return get_str

def get_first_ipv4_port(url):
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, url)
    results = []
    for single_url in urls:
        ipv4_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ipv4_match = re.search(ipv4_pattern, single_url)
        if ipv4_match:
            ipv4_end = ipv4_match.end()
            remaining_url = single_url[ipv4_end:]
            port_match = re.search(r':(\d+)', remaining_url)
            if port_match:
                port = int(port_match.group(1))
            else:
                port = 80
            results = [ipv4_match.group(), port]
    return results

def discover_onvif_devices(count=10):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(5)  # 设置较短的超时时间

    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.sendto(MESSAGE.encode(), (MULTICAST_ADDRESS, PORT))

    devices = []
    try:
        for _ in range(count):
            try:
                data, addr = sock.recvfrom(65536)
                g_xml = data.decode()
                get_str = get_xmlinfo(g_xml)
                get_prot = get_first_ipv4_port(get_str)
                if get_prot and get_prot not in devices:
                    devices.append(get_prot)
                    yield get_prot  # 立即返回每个设备的响应
            except socket.timeout:
                break  # 如果超时，则退出循环
    finally:
        sock.close()
    return devices

def getonviflst():
    lst = []
    for device in discover_onvif_devices():
        # print(device)
        lst.append(device)
    return lst

# if __name__ == "__main__":
#     lst = []
#     for device in discover_onvif_devices():
#         #print(device)
#         lst.append(device)
#     print(lst)
