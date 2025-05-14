import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from image_processing import ImageProcessor

class TestImageProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = ImageProcessor()

    def test_image_resize(self):
        # TODO: 实现图像缩放测试
        pass

    def test_image_preprocess(self):
        # TODO: 实现图像预处理测试
        pass

if __name__ == '__main__':
    unittest.main()