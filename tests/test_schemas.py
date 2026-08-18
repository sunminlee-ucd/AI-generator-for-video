import pytest
from pydantic import ValidationError

from app.schemas import EditOperation, EditPlan, MotionKeyframe


def test_style_transfer_requires_prompt():
    with pytest.raises(ValidationError):
        EditOperation(type="style_transfer")


def test_plan_detects_wan():
    plan = EditPlan(
        assistant_message="Restyle the video.",
        operations=[EditOperation(type="style_transfer", style_prompt="hand-painted animation")],
    )
    assert plan.uses_wan is True


def test_mask_requires_background_video():
    with pytest.raises(ValidationError):
        EditOperation(type="masked_video", shape="star")


def test_music_requires_audio_asset():
    with pytest.raises(ValidationError):
        EditOperation(type="music", volume=0.25)


def test_motion_keyframes_are_sorted_and_allow_offscreen_positions():
    operation = EditOperation(
        type="masked_video",
        secondary_asset_id="bg",
        shape="star",
        motion_keyframes=[
            MotionKeyframe(time_seconds=2, x=300, y=100),
            MotionKeyframe(time_seconds=0, x=-120, y=20, easing="ease_in_out"),
        ],
    )
    assert [frame.time_seconds for frame in operation.motion_keyframes] == [0, 2]
    assert operation.motion_keyframes[0].x == -120


def test_motion_keyframe_times_must_be_unique():
    with pytest.raises(ValidationError):
        EditOperation(
            type="picture_in_picture",
            secondary_asset_id="overlay",
            motion_keyframes=[
                MotionKeyframe(time_seconds=1, x=20, y=20),
                MotionKeyframe(time_seconds=1, x=40, y=40),
            ],
        )
