from borgboi.tui.config_panel import _aws_profile_display, _render_section


def test_render_section_escapes_plain_text_values() -> None:
    rendered = _render_section({"Repo Path": "/var/backups/[test]", "S3 Bucket": "bucket[name]"})

    assert "/var/backups/\\[test]" in rendered
    assert "bucket\\[name]" in rendered


def test_render_section_still_formats_booleans_as_colored_markup() -> None:
    rendered = _render_section({"Offline": True, "Debug": False})

    assert "[#a6e3a1]True[/]" in rendered
    assert "[#f38ba8]False[/]" in rendered


def test_aws_profile_display_uses_provider_chain_when_profile_unset() -> None:
    assert _aws_profile_display(None) == "provider chain"
    assert _aws_profile_display("sandbox") == "sandbox"
