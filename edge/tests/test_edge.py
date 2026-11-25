import os
import pytest
import numpy as np
import cv2
import tempfile
import shutil

from edge.storage import EdgeStorage
from edge.faces import FaceManager
from edge.llm import EventCaptioner
from edge.notifier import EventUploader
from edge.events import EventManager
from edge.camera import VideoFileSource

@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_edge.db")
    snap_dir = os.path.join(tmp_dir, "snapshots")
    yield db_path, snap_dir
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

def test_storage_and_enrollment(temp_workspace):
    db_path, snap_dir = temp_workspace
    storage = EdgeStorage(db_path)
    # Use mock/fallback mode for synthetic grey-circle unit test
    face_mgr = FaceManager(storage, yunet_model_path="", sface_model_path="")

    # Synthetic test frame with face circle
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (320, 240), 50, (200, 200, 200), -1)

    # Enroll user 'Alice'
    assert face_mgr.enroll_face("Alice", frame) is True

    # Verify enrolled in local database
    known = storage.load_known_faces()
    assert len(known) == 1
    assert known[0]["name"] == "Alice"

def test_event_manager_cooldown_and_offline_queue(temp_workspace, monkeypatch):
    db_path, snap_dir = temp_workspace
    storage = EdgeStorage(db_path)
    face_mgr = FaceManager(storage)

    # Mock captioner
    class MockCaptioner:
        def generate_caption(self, image_bytes, label):
            return f"Mocked caption for {label}"

    # Mock uploader (simulating offline network)
    class OfflineUploader:
        def upload_event(self, event_id, payload, image_path):
            return False # Network down!

    event_mgr = EventManager(
        device_id="test-pi",
        storage=storage,
        face_manager=face_mgr,
        captioner=MockCaptioner(),
        uploader=OfflineUploader(),
        cooldown_seconds=10.0,
        snapshot_dir=snap_dir
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Process frame immediately: same personLabel ("motion") should return None
    evt1 = event_mgr.trigger_event(frame, person_label="motion", reason="test")
    assert evt1 is not None

    evt2 = event_mgr.process_frame(frame)
    assert evt2 is None

def test_ignore_caption_handling(temp_workspace):
    db_path, snap_dir = temp_workspace
    storage = EdgeStorage(db_path)
    face_mgr = FaceManager(storage)

    class IgnoreCaptioner:
        def generate_caption(self, image_bytes, label):
            return "IGNORE"

    class MockUploader:
        def upload_event(self, event_id, payload, image_path):
            return True

    event_mgr = EventManager(
        device_id="test-pi",
        storage=storage,
        face_manager=face_mgr,
        captioner=IgnoreCaptioner(),
        uploader=MockUploader(),
        cooldown_seconds=5.0,
        snapshot_dir=snap_dir
    )

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    evt = event_mgr.trigger_event(frame, person_label="motion", reason="camera_detection")
    # Event should be completely suppressed
    assert evt is None
    assert len(storage.get_pending_events()) == 0

def test_video_file_source_synthetic():
    source = VideoFileSource("non_existent_video.mp4", loop=True)
    frame = source.read_frame()
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    source.release()
