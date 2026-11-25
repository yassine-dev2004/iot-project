import os
import json
import csv
from datetime import datetime

class AuditLogger:
    """
    Journal d'audit et suivi thérapeutique.
    Exporte les interactions horodatées pour orthophonistes, pédopsychiatres et éducateurs spécialisés.
    """
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.session_file = os.path.join(self.log_dir, f"audit_session_{datetime.now().strftime('%Y%m%d')}.jsonl")
        self.csv_file = os.path.join(self.log_dir, f"therapeutique_export_{datetime.now().strftime('%Y%m%d')}.csv")
        self._ensure_csv_header()

    def _ensure_csv_header(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "indice_type", "geste_nom", "action_realisee", 
                    "phrase_synthetisee", "confiance", "details_iot"
                ])

    def log_event(self, indice_type: str, gesture_name: str, action: str, speech: str, confidence: float = 1.0, details: dict = None):
        event = {
            "timestamp": datetime.now().isoformat(),
            "indice_type": indice_type, # "VISION", "ACOUSTIC_CLAP", "FAIL_SAFE"
            "gesture_name": gesture_name,
            "action": action,
            "speech": speech,
            "confidence": confidence,
            "details": details or {}
        }
        
        # Enregistrement JSONL
        with open(self.session_file, mode="a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            
        # Enregistrement CSV pour les soignants
        with open(self.csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                event["timestamp"],
                event["indice_type"],
                event["gesture_name"],
                event["action"],
                event["speech"],
                f"{event['confidence']:.2f}",
                json.dumps(event["details"])
            ])
        return event

    def get_summary_stats(self):
        counts = {
            "total_interactions": 0,
            "soif_count": 0,
            "appel_parents_count": 0,
            "urgences_count": 0,
            "clap_count": 0,
            "autres_count": 0
        }
        if os.path.exists(self.session_file):
            with open(self.session_file, mode="r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        counts["total_interactions"] += 1
                        ev = json.loads(line)
                        act = ev.get("action", "")
                        if act == "EAU_SOIF":
                            counts["soif_count"] += 1
                        elif act == "APPEL_PARENT":
                            counts["appel_parents_count"] += 1
                        elif act == "DANGER_SOS":
                            counts["urgences_count"] += 1
                        elif ev.get("indice_type") == "ACOUSTIC_CLAP":
                            counts["clap_count"] += 1
                        else:
                            counts["autres_count"] += 1
        return counts
