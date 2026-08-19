from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_mobile_shell_has_guided_navigation_and_safe_area_support():
    assert "viewport-fit=cover" in HTML
    assert 'id="bottom-nav"' in HTML
    assert 'data-tab="ai"' in HTML
    assert 'data-tab="edits"' in HTML
    assert 'data-tab="media"' in HTML
    assert "safe-area-inset-bottom" in CSS
    assert "--touch: 48px" in CSS


def test_visual_touch_editor_is_exposed_for_layers_and_motion():
    assert 'id="direct-layer"' in HTML
    assert 'id="resize-handle"' in HTML
    assert "Position on video" in JS
    assert "Add position now" in JS
    assert "pointerdown" in JS
    assert "pointermove" in JS


def test_first_time_user_copy_avoids_developer_first_language():
    assert "Tell AI what to change" in HTML
    assert "Review and adjust" in HTML
    assert "Add video or music" in HTML
    assert "Render my changes" in HTML
