# API文档

## 图像处理接口

### 人体检测

```python
from IPC_img_human import HumanDetector

detector = HumanDetector()
result = detector.detect(image)
```

### ONVIF接口

```python
from getonvif import OnvifCamera

camera = OnvifCamera()
status = camera.connect(ip, username, password)
```

## UDP通信

```python
from udp_get_id import UDPClient

client = UDPClient()
client.send_message(message)
```