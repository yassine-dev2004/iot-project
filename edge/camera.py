import abc
import os
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class CameraSource(abc.ABC):
    @abc.abstractmethod
    def read_frame(self) -> np.ndarray:
        """Returns the next BGR frame or raises StopIteration / returns None if finished."""
        pass

    @abc.abstractmethod
    def release(self):
        """Release device or file handle."""
        pass


class USBWebcamSource(CameraSource):
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            logger.warning(f"Could not open USB webcam at index {device_index}")

    def read_frame(self) -> np.ndarray:
        if not self.cap.isOpened():
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self):
        if self.cap.isOpened():
            self.cap.release()


class VideoFileSource(CameraSource):
    """
    Loops a video file continuously or produces dummy test frames if file is absent.
    Ideal for CI/CD and edge testing without hardware.
    """
    def __init__(self, video_path: str, loop: bool = True):
        self.video_path = video_path
        self.loop = loop
        self.cap = None
        self._frame_count = 0
        if os.path.exists(video_path):
            self.cap = cv2.VideoCapture(video_path)
        else:
            logger.warning(f"Video file '{video_path}' not found on disk. Generating synthetic test frames.")

    def read_frame(self) -> np.ndarray:
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                if self.loop:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                else:
                    return None
            return frame

        # Synthetic frame generator
        self._frame_count += 1
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add slight movement so motion detector & liveness pass
        dx = int(10 * np.sin(self._frame_count * 0.1))
        dy = int(5 * np.cos(self._frame_count * 0.1))
        # Draw fake door & face circle
        cv2.rectangle(img, (200, 100), (440, 480), (50, 50, 50), -1)
        cv2.circle(img, (320 + dx, 240 + dy), 60, (200, 180, 150), -1)
        cv2.putText(img, f"Test Frame #{self._frame_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        return img

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()


class Picamera2Source(CameraSource):
    """Raspberry Pi Camera Module via modern picamera2 library."""
    def __init__(self, resolution=(640, 480)):
        self.picam2 = None
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={"size": resolution, "format": "BGR888"})
            self.picam2.configure(config)
            self.picam2.start()
            logger.info("Picamera2 initialized successfully.")
        except Exception as e:
            logger.warning(f"Picamera2 initialization failed: {e}. Fallback to mock.")

    def read_frame(self) -> np.ndarray:
        if self.picam2:
            return self.picam2.capture_array()
        return None

    def release(self):
        if self.picam2:
            self.picam2.stop()


class ImageFileSource(CameraSource):
    """Reads a single real-life photo (.jpg, .png, .webp) for face enrollment or testing."""
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.frame = cv2.imread(image_path) if os.path.exists(image_path) else None
        if self.frame is None:
            logger.warning(f"Could not read image file: '{image_path}'")

    def read_frame(self) -> np.ndarray:
        return self.frame.copy() if self.frame is not None else None

    def release(self):
        self.frame = None


def create_camera_source(source_arg: str) -> CameraSource:
    lower = source_arg.lower()
    if lower.startswith("webcam:") or source_arg.isdigit():
        idx = int(source_arg.split(":")[-1]) if ":" in source_arg else int(source_arg)
        return USBWebcamSource(idx)
    elif lower in ("picam", "picamera2"):
        return Picamera2Source()
    elif lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
        return ImageFileSource(source_arg)
    else:
        # Default to video file
        return VideoFileSource(source_arg, loop=True)
