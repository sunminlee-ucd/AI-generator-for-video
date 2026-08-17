from __future__ import annotations

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas import EditPlan

SYSTEM_PROMPT = """You are the edit planner for a conversational video editor.
Convert the user's request into the smallest accurate list of supported edit operations.

Supported operations:
- trim: remove content outside start_seconds/end_seconds.
- speed: playback speed from 0.5 to 2.0.
- mute: remove audio.
- volume: audio multiplier from 0.0 to 4.0.
- text_overlay: add text at top, center, or bottom.
- style_transfer: generative visual restyling. Put a detailed visual prompt in style_prompt.

Rules:
1. Never invent unsupported operations.
2. Use seconds for time values.
3. If the user asks for a generative visual style, use style_transfer.
4. Do not add style_transfer for ordinary cuts, speed, audio, or text edits.
5. Keep assistant_message concise and state what will be changed.
6. If a request cannot be represented, return no operations and explain that limitation.
7. Prefer one operation over several redundant operations.
"""

class GeminiPlanner:
    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google import genai
        from google.genai import types
        self._client = genai.Client(api_key=api_key)
        self._types = types
        self._model = model

    def plan(self, user_prompt: str, metadata: dict) -> EditPlan:
        duration = metadata.get("duration_seconds")
        dimensions = metadata.get("dimensions", {})
        context = (
            f"Video duration: {duration} seconds. "
            f"Video dimensions: {dimensions.get('width')}x{dimensions.get('height')}. "
            f"Has audio: {metadata.get('has_audio', False)}.\n\n"
            f"User request: {user_prompt}"
        )
        config = self._types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EditPlan,
            temperature=0.1,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=context,
            config=config,
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty edit plan")
        return EditPlan.model_validate_json(response.text)
