import os
import cv2
import numpy as np
import base64
from inference.detector_factory import is_rk_platform, create_detector
#rknn_model = './data/yolov5s_relu.rknn'
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

if is_rk_platform():
    rknn_model = os.path.join(MODEL_DIR, 'yolov5s_relu.rknn')
else:
    rknn_model = os.path.join(MODEL_DIR, 'yolov5s_relu.onnx')

# 在模型加载前添加平台检查和环境配置
if is_rk_platform():
    os.environ['RKNN_RUNTIME_MODE'] = '1'  # 启用 RK NPU
    if not os.path.exists(rknn_model):
        raise FileNotFoundError(f"RKNN model not found: {rknn_model}")
else:
    if not os.path.exists(rknn_model):
        raise FileNotFoundError(f"ONNX model not found: {rknn_model}")
#IMG_PATH = 'zidane.jpg'

OBJ_THRESH = 0.65
NMS_THRESH = 0.40
IMG_SIZE = (640, 640)

CLASSES = ("person", "bicycle", "car", "motorbike ", "aeroplane ", "bus ", "train", "truck ", "boat", "traffic light",
           "fire hydrant", "stop sign ", "parking meter", "bench", "bird", "cat", "dog ", "horse ", "sheep", "cow",
           "elephant",
           "bear", "zebra ", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis",
           "snowboard", "sports ball", "kite",
           "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
           "fork", "knife ",
           "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza ", "donut",
           "cake", "chair", "sofa",
           "pottedplant", "bed", "diningtable", "toilet ", "tvmonitor", "laptop	", "mouse	", "remote ",
           "keyboard ", "cell phone", "microwave ",
           "oven ", "toaster", "sink", "refrigerator ", "book", "clock", "vase", "scissors ", "teddy bear ",
           "hair drier", "toothbrush ")

def filter_boxes(boxes, box_confidences, box_class_probs):
    """Filter boxes with object threshold.
    """
    box_confidences = box_confidences.reshape(-1)
    candidate, class_num = box_class_probs.shape

    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)

    _class_pos = np.where(class_max_score * box_confidences >= OBJ_THRESH)
    scores = (class_max_score * box_confidences)[_class_pos]

    boxes = boxes[_class_pos]
    classes = classes[_class_pos]

    return boxes, classes, scores


def nms_boxes(boxes, scores):
    """Suppress non-maximal boxes.
    # Returns
        keep: ndarray, index of effective boxes.
    """
    x = boxes[:, 0]
    y = boxes[:, 1]
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]

    areas = w * h
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x[i], x[order[1:]])
        yy1 = np.maximum(y[i], y[order[1:]])
        xx2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]])
        yy2 = np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])

        w1 = np.maximum(0.0, xx2 - xx1 + 0.00001)
        h1 = np.maximum(0.0, yy2 - yy1 + 0.00001)
        inter = w1 * h1

        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
    keep = np.array(keep)
    return keep


def box_process(position, anchors):
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE[1] // grid_h, IMG_SIZE[0] // grid_w]).reshape(1, 2, 1, 1)

    col = col.repeat(len(anchors), axis=0)
    row = row.repeat(len(anchors), axis=0)
    anchors = np.array(anchors)
    anchors = anchors.reshape(*anchors.shape, 1, 1)

    box_xy = position[:, :2, :, :] * 2 - 0.5
    box_wh = pow(position[:, 2:4, :, :] * 2, 2) * anchors

    box_xy += grid
    box_xy *= stride
    box = np.concatenate((box_xy, box_wh), axis=1)

    # Convert [c_x, c_y, w, h] to [x1, y1, x2, y2]
    xyxy = np.copy(box)
    xyxy[:, 0, :, :] = box[:, 0, :, :] - box[:, 2, :, :] / 2  # top left x
    xyxy[:, 1, :, :] = box[:, 1, :, :] - box[:, 3, :, :] / 2  # top left y
    xyxy[:, 2, :, :] = box[:, 0, :, :] + box[:, 2, :, :] / 2  # bottom right x
    xyxy[:, 3, :, :] = box[:, 1, :, :] + box[:, 3, :, :] / 2  # bottom right y

    return xyxy


def yolov5_post_process(input_data):
    anchors = [[[10.0, 13.0], [16.0, 30.0], [33.0, 23.0]], [[30.0, 61.0],
                                                            [62.0, 45.0], [59.0, 119.0]],
               [[116.0, 90.0], [156.0, 198.0], [373.0, 326.0]]]

    boxes, scores, classes_conf = [], [], []
    # 1*255*h*w -> 3*85*h*w

    input_data = [_in.reshape([len(anchors[0]), -1] + list(_in.shape[-2:])) for _in in input_data]
    for i in range(len(input_data)):
        boxes.append(box_process(input_data[i][:, :4, :, :], anchors[i]))
        scores.append(input_data[i][:, 4:5, :, :])
        classes_conf.append(input_data[i][:, 5:, :, :])

    # transpose, reshape
    def sp_flatten(_in):
        ch = _in.shape[1]
        _in = _in.transpose(0, 2, 3, 1)
        return _in.reshape(-1, ch)

    boxes = [sp_flatten(_v) for _v in boxes]
    classes_conf = [sp_flatten(_v) for _v in classes_conf]
    scores = [sp_flatten(_v) for _v in scores]

    boxes = np.concatenate(boxes)
    classes_conf = np.concatenate(classes_conf)
    scores = np.concatenate(scores)

    # filter according to threshold
    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf)

    # nms
    nboxes, nclasses, nscores = [], [], []
    for c in set(classes):
        inds = np.where(classes == c)
        b = boxes[inds]
        c = classes[inds]
        s = scores[inds]
        keep = nms_boxes(b, s)

        nboxes.append(b[keep])
        nclasses.append(c[keep])
        nscores.append(s[keep])

    if not nclasses and not nscores:
        return None, None, None

    boxes = np.concatenate(nboxes)
    classes = np.concatenate(nclasses)
    scores = np.concatenate(nscores)
    return boxes, classes, scores


def draw(image, boxes, scores, classes):
    """Draw the boxes on the image.
    # Argument:
        image: original image.
        boxes: ndarray, boxes of objects.
        classes: ndarray, classes of objects.
        scores: ndarray, scores of objects.
    """
    for box, score, cl in zip(boxes, scores, classes):
        top, left, right, bottom = [int(_b) for _b in box]
        print('class: {}, score: {}'.format(CLASSES[cl], score))
        print('box coordinate left,top,right,down: [{}, {}, {}, {}]'.format(top, left, right, bottom))

        cv2.rectangle(image, (top, left), (right, bottom), (255, 0, 0), 2)
        cv2.putText(image, '{0} {1:.2f}'.format(CLASSES[cl], score),
                    (top, left - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 0, 255), 2)


def letterbox(im, new_shape=(640, 640), color=(0, 0, 0)):
    # Resize and pad image while meeting stride-multiple constraints
    shape = im.shape[:2]  # current shape [height, width]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    # Compute padding
    ratio = r, r  # width, height ratios
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]  # wh padding

    dw /= 2  # divide padding into 2 sides
    dh /= 2

    if shape[::-1] != new_unpad:  # resize
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)  # add border
    return im, ratio, (dw, dh)
#识别调用

# rknn_lite = RKNNLite()
# # load RKNN model
# #print('--> Load RKNN model')
# ret = rknn_lite.load_rknn(rknn_model)
# if ret != 0:
#     print('Load RKNN model failed')
#     exit(ret)

# # Init runtime environment
# #print('--> Init runtime environment')
# ret = rknn_lite.init_runtime()
# if ret != 0:
#     print('Init runtime environment failed!')
#     exit(ret)
# 删除原来的 RKNNLite 初始化代码，替换为通用检测器初始化
# 初始化检测器
try:
    detector = create_detector()
    detector.load_model(rknn_model)
except Exception as e:
    print(f"Error initializing detector: {e}")
    raise

def get_human(frame, classid=[0]):
    # Set inputs
    try:
        img = frame#cv2.imread(IMG_PATH)
        img, ratio, (dw, dh) = letterbox(img, new_shape=(640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # 根据平台进行不同的数据预处理
        if not is_rk_platform():
            # X86 平台：转换为 float32 并归一化
            img = img.astype(np.float32)
            img = img / 255.0
            # 调整维度顺序为 NCHW (batch, channels, height, width)
            img = img.transpose(2, 0, 1)  # HWC -> CHW
        # RK 平台保持 uint8 类型
        img = np.expand_dims(img, 0)

        # Inference
        #print('--> Running model')
        # outputs = rknn_lite.inference(inputs=[img])
        outputs = detector.inference(img)
        # Process output
        boxes, classes, scores = yolov5_post_process(outputs)

        # Print detected classes
        if classes is not None:
            if classid in classes:
                #print(classes)
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        print(f"Error get_human: {e}")
        return False
    #rknn_lite.release()


def extract_human_features(frame):
    """
    提取人体关键点特征
    :param frame: 输入图像帧
    :return: 人体关键点特征向量(np.array)或None
    """
    try:
        # 使用OpenCV提取ORB特征
        orb = cv2.ORB_create()
        # 转换为灰度图像
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 检测关键点和描述符
        kp, des = orb.detectAndCompute(gray, None)
        
        if des is not None:
            # 取前128维特征(不足补零)
            feature = np.zeros(128, dtype=np.float32)
            desc = des[0] if len(des) > 0 else None
            if desc is not None:
                feature[:min(len(desc), 128)] = desc[:128]
            return feature
        return None
    except Exception as e:
        print(f"提取人体特征错误: {e}")
        return None

def compare_features(features1, features2, threshold=0.85):
    """
    比较两个特征向量的相似度
    :param features1: 第一个特征向量
    :param features2: 第二个特征向量
    :param threshold: 相似度阈值
    :return: 相似度分数(0-1)
    """
    if features1 is None or features2 is None:
        return 0.0
    
    try:
        # 计算余弦相似度
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    except Exception as e:
        print(f"特征比较错误: {e}")
        return 0.0

def get_human_images_base64(image_path, padding=30, classid=[0]):
    """
    检测图片中的指定类别目标位置并返回base64编码的图像列表，支持边界扩展
    
    Args:
        image_path: 输入图片路径
        padding: 边界框扩展像素值，默认50像素
        classid: 目标类别ID列表，默认[0]表示人体类别
        
    Returns:
        list: base64编码的目标图像列表，如果没有检测到目标或发生错误则返回空列表
    """
    try:
        # 读取图片
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"无法读取图片: {image_path}")
            return []
            
        # 图像预处理
        img, ratio, (dw, dh) = letterbox(frame, new_shape=(640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 根据平台进行不同的数据预处理
        if not is_rk_platform():
            # X86平台：转换为float32并归一化
            img = img.astype(np.float32)
            img = img / 255.0
            # 调整维度顺序为NCHW
            img = img.transpose(2, 0, 1)  # HWC -> CHW
        
        # 扩展batch维度
        img = np.expand_dims(img, 0)
        
        # 模型推理
        outputs = detector.inference(img)
        
        # 后处理获取检测框
        boxes, classes, scores = yolov5_post_process(outputs)
        if classes is None or len(classes) == 0:
            return []
            
        # 提取目标图像并转换为base64
        human_images_base64 = []
        frame_height, frame_width = frame.shape[:2]
        
        for box, cl in zip(boxes, classes):
            if cl in classid:  # 判断是否为指定类别
                # 获取边界框坐标并扩展边界
                top, left, right, bottom = [int(_b) for _b in box]
                
                # 坐标映射问题：
                # 需要注意的是，YOLO模型是在640x640的图像上进行检测的，而原始图像可能有不同的尺寸。虽然代码中使用了`letterbox`函数进行了预处理，但返回的检测框坐标是相对于预处理后的图像的。我们需要将这些坐标映射回原始图像尺寸。
                
                # 建议修改后的代码：
                top = int((top - dw) / ratio[0])
                left = int((left - dh) / ratio[1])
                right = int((right - dw) / ratio[0])
                bottom = int((bottom - dh) / ratio[1])
                
                # 扩展边界，同时确保不超出图像范围
                top = max(0, top - padding)
                left = max(0, left - padding)
                right = min(frame_width, right + padding)
                bottom = min(frame_height, bottom + padding)
                
                # 修正裁剪方式：使用[y1:y2, x1:x2]的形式
                human_img = frame[left:bottom, top:right]
                
                # 将图像编码为base64
                if human_img.size > 0:
                    _, buffer = cv2.imencode('.jpg', human_img)
                    base64_str = base64.b64encode(buffer).decode('utf-8')
                    human_images_base64.append(base64_str)
        
        return human_images_base64
        
    except Exception as e:
        print(f"处理图片时发生错误: {e}")
        return []