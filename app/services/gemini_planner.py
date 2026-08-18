from __future__ import annotations

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.schemas import EditPlan

SYSTEM_PROMPT = """You are the edit planner for a conversational video editor.
Convert the user's request into the smallest accurate list of supported edit operations.
The output is a proposal: the user will fine-tune parameters before applying it.

Supported operations:
- trim: remove content outside start_seconds/end_seconds.
- speed: playback speed from 0.5 to 2.0.
- mute: remove audio.
- volume: audio multiplier from 0.0 to 4.0.
- text_overlay: add text. You may set position, font_family, font_size, font_color, text_background_color, and bold.
- split_screen: combine the source video with an uploaded secondary video. Set secondary_asset_id and layout.
- picture_in_picture: overlay an uploaded secondary video. Set secondary_asset_id and x/y/width/height. It may use motion_keyframes.
- masked_video: play the source video inside a circle/star/heart/triangle while an uploaded secondary video plays behind it. secondary_asset_id is the background video. It may use motion_keyframes.
- music: add an uploaded/licensed audio asset using source_asset_id. You may set volume, fade_in_seconds, fade_out_seconds, loop, and ducking.
- style_transfer: generative visual restyling. Put a detailed visual prompt in style_prompt.

Motion keyframes:
- motion_keyframes may be used only with masked_video or picture_in_picture.
- Each keyframe has time_seconds, x, y, and easing.
- Supported easing values are linear, ease_in, ease_out, and ease_in_out.
- Use at least two keyframes when the user asks the layer to move.
- x/y may be negative when the user wants the layer to enter from or leave the screen.
- Keep keyframe times within the source video duration.
- The easing on a keyframe controls the movement from that keyframe toward the next keyframe.

Rules:
1. Never invent unsupported operations.
2. Use seconds for time values.
3. Use only asset IDs that appear in the provided asset list.
4. If the user asks for a generative visual style, use style_transfer.
5. Do not add style_transfer for ordinary cuts, speed, audio, text, layout, masks, motion, or music edits.
6. Keep assistant_message concise and state what is being proposed, not that it has already happened.
7. If a request cannot be represented or refers to media that has not been uploaded, return no operations and explain what asset is needed.
8. Prefer one operation over several redundant operations.
9. For masked_video, the main/source video is the foreground and secondary_asset_id is the background video.
10. When adding motion to a masked_video, keep its mask shape and size parameters on that same operation.
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

    def plan(self, user_prompt: str, metadata: dict, assets: list[dict] | None = None) -> EditPlan:
        duration = metadata.get("duration_seconds")
        dimensions = metadata.get("dimensions", {})
        asset_lines = []
        for asset in assets or []:
            asset_lines.append(
                f"- id={asset['id']}; filename={asset['filename']}; kind={asset['kind']}"
            )
        asset_context = "\n".join(asset_lines) if asset_lines else "(none)"
        context = (
            f"Source video duration: {duration} seconds. "
            f"Dimensions: {dimensions.get('width')}x{dimensions.get('height')}. "
            f"Has audio: {metadata.get('has_audio', False)}.\n"
            f"Uploaded assets:\n{asset_context}\n\n"
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
