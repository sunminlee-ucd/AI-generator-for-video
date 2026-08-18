from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

OperationType = Literal[
    "trim",
    "speed",
    "mute",
    "volume",
    "text_overlay",
    "split_screen",
    "picture_in_picture",
    "masked_video",
    "music",
    "style_transfer",
]

EasingType = Literal["linear", "ease_in", "ease_out", "ease_in_out"]


class MotionKeyframe(BaseModel):
    time_seconds: float = Field(ge=0)
    x: int = Field(ge=-8192, le=8192)
    y: int = Field(ge=-8192, le=8192)
    easing: EasingType = "linear"


class EditOperation(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: OperationType
    enabled: bool = True

    # Shared timing / media fields.
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    source_asset_id: str | None = None
    secondary_asset_id: str | None = None

    # Basic video / audio editing.
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    volume: float | None = Field(default=None, ge=0.0, le=4.0)

    # Text.
    text: str | None = Field(default=None, max_length=300)
    position: Literal["top", "center", "bottom"] | None = None
    font_family: str | None = Field(default="DejaVu Sans", max_length=120)
    font_size: int | None = Field(default=48, ge=8, le=240)
    font_color: str | None = Field(default="white", max_length=40)
    text_background_color: str | None = Field(default="black@0.45", max_length=40)
    bold: bool = False

    # Composition / masks.
    layout: Literal["side_by_side", "stacked"] | None = None
    ratio: float | None = Field(default=0.5, ge=0.15, le=0.85)
    shape: Literal["circle", "star", "heart", "triangle"] | None = None
    x: int | None = Field(default=40, ge=0)
    y: int | None = Field(default=40, ge=0)
    width: int | None = Field(default=360, ge=32, le=4096)
    height: int | None = Field(default=360, ge=32, le=4096)
    rotation: float | None = Field(default=0, ge=-360, le=360)
    opacity: float | None = Field(default=1.0, ge=0.0, le=1.0)
    feather: int | None = Field(default=0, ge=0, le=100)
    border_width: int | None = Field(default=0, ge=0, le=50)
    border_color: str | None = Field(default="white", max_length=40)
    fit: Literal["cover", "contain"] | None = None
    motion_keyframes: list[MotionKeyframe] = Field(default_factory=list)

    # Background music.
    fade_in_seconds: float | None = Field(default=0.0, ge=0, le=30)
    fade_out_seconds: float | None = Field(default=0.0, ge=0, le=30)
    loop: bool = True
    ducking: bool = False

    # Generative video.
    style_prompt: str | None = Field(default=None, max_length=1500)

    @model_validator(mode="after")
    def validate_required_fields(self):
        if self.type == "trim" and self.start_seconds is None and self.end_seconds is None:
            raise ValueError("trim requires start_seconds or end_seconds")
        if self.type == "speed" and self.speed is None:
            raise ValueError("speed requires speed")
        if self.type == "volume" and self.volume is None:
            raise ValueError("volume requires volume")
        if self.type == "text_overlay" and not self.text:
            raise ValueError("text_overlay requires text")
        if self.type in {"split_screen", "picture_in_picture"} and not self.secondary_asset_id:
            raise ValueError(f"{self.type} requires secondary_asset_id")
        if self.type == "masked_video":
            if not self.secondary_asset_id:
                raise ValueError("masked_video requires secondary_asset_id for the background video")
            if not self.shape:
                raise ValueError("masked_video requires shape")
        if self.type == "music" and not self.source_asset_id:
            raise ValueError("music requires source_asset_id")
        if self.type == "style_transfer" and not self.style_prompt:
            raise ValueError("style_transfer requires style_prompt")
        if self.motion_keyframes:
            if self.type not in {"masked_video", "picture_in_picture"}:
                raise ValueError("motion_keyframes are supported only for masked_video and picture_in_picture")
            ordered = sorted(self.motion_keyframes, key=lambda frame: frame.time_seconds)
            for previous, current in zip(ordered, ordered[1:]):
                if abs(previous.time_seconds - current.time_seconds) < 1e-6:
                    raise ValueError("motion keyframe times must be unique")
            self.motion_keyframes = ordered
        return self


class EditPlan(BaseModel):
    assistant_message: str = Field(description="Short user-facing explanation of the proposed edit.")
    operations: list[EditOperation] = Field(default_factory=list)

    @property
    def uses_wan(self) -> bool:
        return any(op.enabled and op.type == "style_transfer" for op in self.operations)


class CommandRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class ApplyPlanRequest(BaseModel):
    prompt: str = Field(default="Manual edit", max_length=4000)
    assistant_message: str = Field(default="Applied edited changes.", max_length=1000)
    operations: list[EditOperation]


class ReplaceOperationsRequest(BaseModel):
    operations: list[EditOperation]
