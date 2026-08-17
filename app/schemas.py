from typing import Literal
from pydantic import BaseModel, Field, model_validator

OperationType = Literal[
    "trim", "speed", "mute", "volume", "text_overlay", "style_transfer"
]

class EditOperation(BaseModel):
    type: OperationType
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    speed: float | None = Field(default=None, ge=0.5, le=2.0)
    volume: float | None = Field(default=None, ge=0.0, le=4.0)
    text: str | None = Field(default=None, max_length=300)
    position: Literal["top", "center", "bottom"] | None = None
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
        if self.type == "style_transfer" and not self.style_prompt:
            raise ValueError("style_transfer requires style_prompt")
        return self

class EditPlan(BaseModel):
    assistant_message: str = Field(description="Short user-facing explanation of the planned edit.")
    operations: list[EditOperation] = Field(default_factory=list)

    @property
    def uses_wan(self) -> bool:
        return any(op.type == "style_transfer" for op in self.operations)

class CommandRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
