import platform

def is_rk_platform():
    return platform.machine().lower() == 'aarch64'

def create_detector():
    if is_rk_platform():
        try:
            from .rk_detector import RKDetector
            return RKDetector()
        except ImportError:
            raise ImportError("RK platform libraries not found")
    else:
        from .x86_detector import X86Detector
        return X86Detector()