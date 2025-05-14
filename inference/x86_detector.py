from .base_detector import BaseDetector
import onnxruntime as ort

class X86Detector(BaseDetector):
    def __init__(self):
        self.session = None
        
    def load_model(self, model_path):
        # 注意：这里需要使用对应的 ONNX 模型文件
        onnx_path = model_path.replace('.rknn', '.onnx')
        self.session = ort.InferenceSession(onnx_path)
        
    def inference(self, image):
        input_name = self.session.get_inputs()[0].name
        return self.session.run(None, {input_name: image})
        
    def release(self):
        self.session = None