import os
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

class EventCaptioner:
    """
    Summarizes door camera snapshots into a one-line event summary using Gemini API via google-genai SDK.
    PRIVACY RULES ENFORCED:
    1. Gemini receives only a single event snapshot.
    2. Strict system instruction: NEVER identify or name people by face.
       Identity is provided strictly by the local edge recognizer.
    3. Graceful fallback when GEMINI_API_KEY is missing or quota is exhausted.
    """
    def __init__(self, api_key: str = "", model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized with model '{self.model_name}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}. Fallback active.")

    def generate_caption(self, image_bytes: bytes, local_person_label: str) -> str:
        """
        Generates a concise one-line description of the event.
        If local_person_label is known (e.g. 'Alice'), incorporates that label.
        """
        # Fallback caption if no client
        fallback = self._create_fallback_caption(local_person_label)

        if not self.client:
            return fallback

        prompt = f"""
You are a smart door security assistant. Describe in one single concise sentence (max 15 words) what is happening on this porch/doorstep.
Focus strictly on visible actions: package delivery, courier dropping a parcel, visitor knocking or ringing, person entering or leaving, or empty porch.

CRITICAL PRIVACY RULE:
- NEVER guess or state the personal identity of individuals from their faces.
- The person identity is already verified locally as: '{local_person_label}'.
- Use '{local_person_label}' if appropriate, or describe general actions (e.g. 'Courier left a package on the doorstep').
- If there is no activity or just wind/leaves, output 'IGNORE'.
"""
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[pil_img, prompt]
            )
            caption = response.text.strip().replace("\n", " ")
            return caption if caption else fallback
        except Exception as e:
            logger.warning(f"Gemini API captioning failed: {e}. Utilizing fallback caption.")
            return fallback

    def _create_fallback_caption(self, person_label: str) -> str:
        if person_label == "unknown":
            return "Unknown visitor standing at front door"
        elif person_label == "motion":
            return "Motion detected near front entrance"
        elif person_label.startswith("spoof_"):
            return f"Security alert: Photo spoof attempt detected for {person_label[6:]}"
        else:
            return f"{person_label} arrived at the front door"
