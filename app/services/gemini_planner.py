from __future__ import annotations

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas import EditPlan

SYSTEM_PROMPT = """You are the edit planner for a conversational media editor.
The source can be either a video or a still image. Uploaded visual assets can also be videos or images.
Convert the user's request into the smallest accurate list of supported edit operations.
The output is a proposal: the user will fine-tune parameters before applying it.

Supported operations:
- trim: keep content between start_seconds/end_seconds. A still image behaves like a timed clip.
- speed: playback speed from 0.5 to 2.0.
- mute: remove source audio.
- volume: source audio multiplier from 0.0 to 4.0.
- text_overlay: add text with position/font controls.
- split_screen: combine the source with an uploaded image or video using secondary_asset_id and layout.
- picture_in_picture: place an uploaded image or video using secondary_asset_id and x/y/width/height. Motion is supported.
- media_overlay: place an uploaded image or video over the current canvas using source_asset_id and x/y/width/height. Motion is supported.
- masked_video: legacy/source-mask operation. Put the project source inside a circle/star/heart/triangle while secondary_asset_id is the full-canvas background. The background may be an image or video. Motion is supported.
- masked_media: place an uploaded image or video (source_asset_id) inside a circle/star/heart/triangle over the current canvas. Motion is supported.
- music: add an uploaded/licensed audio asset using source_asset_id. You may set volume, fade_in_seconds, fade_out_seconds, loop, and ducking.
- style_transfer: generative visual restyling. Put a detailed visual prompt in style_prompt.

Motion keyframes:
- motion_keyframes may be used with masked_video, masked_media, picture_in_picture, or media_overlay.
- Each keyframe has time_seconds, x, y, and easing.
- Supported easing values are linear, ease_in, ease_out, and ease_in_out.
- Use at least two keyframes when the user asks a layer to move.
- x/y may be negative when the layer should enter from or leave the screen.
- Keep keyframe times within the project duration.

Rules:
1. Treat image and video visual assets as interchangeable when the requested operation supports visual media.
2. Never use an audio asset in a visual operation or a visual asset as music.
3. Use only asset IDs that appear in the uploaded asset list.
4. Use seconds for time values.
5. If the user asks for a generative visual style, use style_transfer; do not use it for normal compositing.
6. Keep assistant_message concise and state what is being proposed, not that it already happened.
7. Return no operations only when required media is missing or the request truly cannot be represented by the supported operations. In that case, clearly explain what the user needs to provide or change.
8. Prefer media_overlay or masked_media for extra uploaded visual layers. Use masked_video only when the project source itself must be masked over another background.
9. If the user's request is achievable with the supported operations, return at least one operation. Do not return an empty operation list just because the request is phrased casually or in a language other than English.
"""

EMPTY_PLAN_RETRY = """
The previous draft contained zero operations. Re-evaluate the user's request carefully.
If any supported operation can satisfy the request, return one or more concrete operations now.
Only return zero operations when an additional media asset is required but missing, or when the request genuinely cannot be represented by the supported operations. If you still return zero operations, make assistant_message explicitly tell the user what is missing or unsupported.
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

    def plan(self, user_prompt: str, metadata: dict, assets: list[dict] | None = None, source_kind: str = "video") -> EditPlan:
        duration = metadata.get("duration_seconds")
        dimensions = metadata.get("dimensions", {})
        asset_lines = [f"- id={asset['id']}; filename={asset['filename']}; kind={asset['kind']}" for asset in assets or []]
        asset_context = "\n".join(asset_lines) if asset_lines else "(none)"
        context = (
            f"Project source kind: {source_kind}. Duration: {duration} seconds. "
            f"Dimensions: {dimensions.get('width')}x{dimensions.get('height')}. "
            f"Has audio: {metadata.get('has_audio', False)}.\n"
            f"Uploaded assets:\n{asset_context}\n\n"
            f"User request: {user_prompt}"
        )

        plan = self._generate(context)
        if plan.operations:
            return plan

        retry_context = f"{context}\n\n{EMPTY_PLAN_RETRY}\nPrevious assistant message: {plan.assistant_message}"
        return self._generate(retry_context)

    def _generate(self, context: str) -> EditPlan:
        config = self._types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EditPlan,
            temperature=0.1,
        )
        response = self._client.models.generate_content(model=self._model, contents=context, config=config)
        if not response.text:
            raise RuntimeError("Gemini returned an empty edit plan")
        return EditPlan.model_validate_json(response.text)
