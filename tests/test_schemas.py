import pytest
from pydantic import ValidationError

from app.schemas import EditOperation, EditPlan


def test_style_transfer_requires_prompt():
    with pytest.raises(ValidationError):
        EditOperation(type="style_transfer")


def test_plan_detects_wan():
    plan = EditPlan(
        assistant_message="Restyle the video.",
        operations=[EditOperation(type="style_transfer", style_prompt="hand-painted animation")],
    )
    assert plan.uses_wan is True
