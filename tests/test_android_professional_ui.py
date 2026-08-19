from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "app" / "src" / "main"


def test_professional_editor_skin_is_wired_as_application():
    manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")
    skin = (ANDROID / "kotlin" / "com" / "sunminlee" / "aieditor" / "ProfessionalEditorSkin.kt").read_text(encoding="utf-8")
    app = (ANDROID / "kotlin" / "com" / "sunminlee" / "aieditor" / "ProfessionalApplication.kt").read_text(encoding="utf-8")

    assert 'android:name=".ProfessionalApplication"' in manifest
    assert 'android:label="AI Media Editor"' in manifest
    assert "EditorTimelineBar" in skin
    assert 'tag = "editor-timeline"' in skin
    assert 'tag = "compact-section-grid"' in app
    assert "Photo turntable" in app


def test_editor_visual_language_is_dark_and_restrained():
    skin = (ANDROID / "kotlin" / "com" / "sunminlee" / "aieditor" / "ProfessionalEditorSkin.kt").read_text(encoding="utf-8")
    feedback = (ANDROID / "kotlin" / "com" / "sunminlee" / "aieditor" / "FeedbackWidgets.kt").read_text(encoding="utf-8")

    assert "Color.rgb(14, 16, 20)" in skin
    assert "Color.rgb(137, 207, 92)" in skin
    assert "scaleX(0.965f)" in feedback
    assert "HapticFeedbackConstants.KEYBOARD_TAP" in feedback
    assert "OvershootInterpolator" not in feedback
