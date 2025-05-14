from .base_detector import BaseDetector
from rknnlite.api import RKNNLite

class RKDetector(BaseDetector):
    def __init__(self):
        self.rknn_lite = RKNNLite()
        
    def load_model(self, model_path):
        ret = self.rknn_lite.load_rknn(model_path)
        if ret != 0:
            raise RuntimeError('Load RKNN model failed')
        ret = self.rknn_lite.init_runtime()
        if ret != 0:
            raise RuntimeError('Init runtime environment failed!')
            
    def inference(self, image):
        return self.rknn_lite.inference(inputs=[image])
        
    def release(self):
        self.rknn_lite.release()