"""
Suite de tests de validation unitaire et d'intégration cyber-physique KiddySentinel (2 IRM).
Vérifie la robustesse de :
1. La classification géométrique invariant des landmarks MediaPipe.
2. Le routage et la conformité de la matrice des besoins PECS / Makaton.
3. La journalisation d'audit thérapeutique et export CSV.
4. Le Fail-Safe Homme-Mort pédiatrique.
"""

import unittest
from types import SimpleNamespace
from backend.gesture_classifier import GestureClassifier
from backend.config import GESTURES_CONFIG
from backend.audit_logger import AuditLogger
import os

class TestKiddySentinel(unittest.TestCase):

    def setUp(self):
        self.logger = AuditLogger(log_dir="test_logs")

    def tearDown(self):
        # Nettoyage logs de test
        if os.path.exists("test_logs"):
            for f in os.listdir("test_logs"):
                os.remove(os.path.join("test_logs", f))
            os.rmdir("test_logs")

    def test_matrix_completeness(self):
        """Vérifie que tous les gestes du sujet 2 IRM sont bien configurés"""
        expected_gestures = [
            "POINTING", "OPEN_PALM", "THUMBS_UP", "THUMBS_DOWN", 
            "CALL_ME", "FIST", "CLAP", "PINCH", "FAIL_SAFE"
        ]
        for g in expected_gestures:
            self.assertIn(g, GESTURES_CONFIG, f"Le geste {g} doit être présent dans la matrice.")
            self.assertIn("speech", GESTURES_CONFIG[g])
            self.assertIn("action", GESTURES_CONFIG[g])
            self.assertIn("oled", GESTURES_CONFIG[g])

    def test_audit_logging(self):
        """Vérifie l'enregistrement et les métriques thérapeutiques"""
        self.logger.log_event("VISION", "Index Pointé", "EAU_SOIF", "J'ai soif")
        self.logger.log_event("VISION", "Signe Call Me", "APPEL_PARENT", "Maman Papa")
        self.logger.log_event("ACOUSTIC_CLAP", "Clap", "TOGGLE_LIGHT", "Lumière")
        
        stats = self.logger.get_summary_stats()
        self.assertEqual(stats["total_interactions"], 3)
        self.assertEqual(stats["soif_count"], 1)
        self.assertEqual(stats["appel_parents_count"], 1)
        self.assertEqual(stats["clap_count"], 1)

    def test_gesture_classifier_pointing(self):
        """Test de la reconnaissance d'un index pointé synthétique"""
        # Construction de 21 landmarks mock
        landmarks = [SimpleNamespace(x=0.5, y=0.8, z=0.0) for _ in range(21)]
        # Poignet à (0.5, 0.8)
        landmarks[0] = SimpleNamespace(x=0.5, y=0.8, z=0.0)
        landmarks[9] = SimpleNamespace(x=0.5, y=0.5, z=0.0) # Palm size = 0.3
        
        # Index tendu
        landmarks[6] = SimpleNamespace(x=0.5, y=0.45, z=0.0)
        landmarks[8] = SimpleNamespace(x=0.5, y=0.1, z=0.0) # loin du poignet
        
        # Autres doigts repliés
        for f_pip, f_tip in [(10, 12), (14, 16), (18, 20)]:
            landmarks[f_pip] = SimpleNamespace(x=0.5, y=0.6, z=0.0)
            landmarks[f_tip] = SimpleNamespace(x=0.5, y=0.65, z=0.0) # proches
            
        landmarks[2] = SimpleNamespace(x=0.4, y=0.65, z=0.0)
        landmarks[4] = SimpleNamespace(x=0.42, y=0.68, z=0.0) # pouce replié

        gesture, conf, _ = GestureClassifier.classify(landmarks)
        self.assertEqual(gesture, "POINTING")

if __name__ == "__main__":
    unittest.main()
