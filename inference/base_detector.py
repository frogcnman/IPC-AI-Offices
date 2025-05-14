from abc import ABC, abstractmethod
import numpy as np

class BaseDetector(ABC):
    @abstractmethod
    def load_model(self, model_path):
        pass

    @abstractmethod
    def inference(self, image):
        pass

    @abstractmethod
    def release(self):
        pass