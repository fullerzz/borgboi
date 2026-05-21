from __future__ import annotations

from dataclasses import dataclass

from pygments.style import Style  # type: ignore[import-untyped]
from pygments.token import (  # type: ignore[import-untyped]
    Comment,
    Error,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Operator,
    Other,
    Punctuation,
    String,
    Text,
    Whitespace,
    _TokenType,
)
from rich.syntax import PygmentsSyntaxTheme


@dataclass(frozen=True)
class ColorHex:
    """Hex color values for a Catppuccin flavor."""

    rosewater: str
    flamingo: str
    pink: str
    mauve: str
    red: str
    maroon: str
    peach: str
    yellow: str
    green: str
    teal: str
    sky: str
    sapphire: str
    blue: str
    lavender: str
    text: str
    subtext1: str
    subtext0: str
    overlay2: str
    overlay1: str
    overlay0: str
    surface2: str
    surface1: str
    surface0: str
    base: str
    mantle: str
    crust: str


# Catppuccin palette values vendored from catppuccin-python to avoid a runtime dependency.
LATTE = ColorHex(
    rosewater="#dc8a78",
    flamingo="#dd7878",
    pink="#ea76cb",
    mauve="#8839ef",
    red="#d20f39",
    maroon="#e64553",
    peach="#fe640b",
    yellow="#df8e1d",
    green="#40a02b",
    teal="#179299",
    sky="#04a5e5",
    sapphire="#209fb5",
    blue="#1e66f5",
    lavender="#7287fd",
    text="#4c4f69",
    subtext1="#5c5f77",
    subtext0="#6c6f85",
    overlay2="#7c7f93",
    overlay1="#8c8fa1",
    overlay0="#9ca0b0",
    surface2="#acb0be",
    surface1="#bcc0cc",
    surface0="#ccd0da",
    base="#eff1f5",
    mantle="#e6e9ef",
    crust="#dce0e8",
)
FRAPPE = ColorHex(
    rosewater="#f2d5cf",
    flamingo="#eebebe",
    pink="#f4b8e4",
    mauve="#ca9ee6",
    red="#e78284",
    maroon="#ea999c",
    peach="#ef9f76",
    yellow="#e5c890",
    green="#a6d189",
    teal="#81c8be",
    sky="#99d1db",
    sapphire="#85c1dc",
    blue="#8caaee",
    lavender="#babbf1",
    text="#c6d0f5",
    subtext1="#b5bfe2",
    subtext0="#a5adce",
    overlay2="#949cbb",
    overlay1="#838ba7",
    overlay0="#737994",
    surface2="#626880",
    surface1="#51576d",
    surface0="#414559",
    base="#303446",
    mantle="#292c3c",
    crust="#232634",
)
MACCHIATO = ColorHex(
    rosewater="#f4dbd6",
    flamingo="#f0c6c6",
    pink="#f5bde6",
    mauve="#c6a0f6",
    red="#ed8796",
    maroon="#ee99a0",
    peach="#f5a97f",
    yellow="#eed49f",
    green="#a6da95",
    teal="#8bd5ca",
    sky="#91d7e3",
    sapphire="#7dc4e4",
    blue="#8aadf4",
    lavender="#b7bdf8",
    text="#cad3f5",
    subtext1="#b8c0e0",
    subtext0="#a5adcb",
    overlay2="#939ab7",
    overlay1="#8087a2",
    overlay0="#6e738d",
    surface2="#5b6078",
    surface1="#494d64",
    surface0="#363a4f",
    base="#24273a",
    mantle="#1e2030",
    crust="#181926",
)
COLOR_HEX = ColorHex(
    rosewater="#f5e0dc",
    flamingo="#f2cdcd",
    pink="#f5c2e7",
    mauve="#cba6f7",
    red="#f38ba8",
    maroon="#eba0ac",
    peach="#fab387",
    yellow="#f9e2af",
    green="#a6e3a1",
    teal="#94e2d5",
    sky="#89dceb",
    sapphire="#74c7ec",
    blue="#89b4fa",
    lavender="#b4befe",
    text="#cdd6f4",
    subtext1="#bac2de",
    subtext0="#a6adc8",
    overlay2="#9399b2",
    overlay1="#7f849c",
    overlay0="#6c7086",
    surface2="#585b70",
    surface1="#45475a",
    surface0="#313244",
    base="#1e1e2e",
    mantle="#181825",
    crust="#11111b",
)


def _make_styles(colors: ColorHex) -> dict[_TokenType, str]:
    return {
        Comment: colors.overlay2,
        Comment.Hashbang: colors.overlay2,
        Comment.Multiline: colors.overlay2,
        Comment.Preproc: colors.pink,
        Comment.Single: colors.overlay2,
        Comment.Special: colors.overlay2,
        Generic: colors.text,
        Generic.Deleted: colors.red,
        Generic.Emph: f"{colors.text} underline",
        Generic.Error: colors.text,
        Generic.Heading: f"{colors.text} bold",
        Generic.Inserted: f"{colors.text} bold",
        Generic.Output: colors.overlay0,
        Generic.Prompt: colors.text,
        Generic.Strong: colors.text,
        Generic.Subheading: f"{colors.text} bold",
        Generic.Traceback: colors.text,
        Error: colors.text,
        Keyword: colors.mauve,
        Keyword.Constant: colors.mauve,
        Keyword.Declaration: f"{colors.mauve} italic",
        Keyword.Namespace: colors.mauve,
        Keyword.Pseudo: colors.pink,
        Keyword.Reserved: colors.mauve,
        Keyword.Type: colors.yellow,
        Literal: colors.text,
        Literal.Date: colors.text,
        Name: colors.text,
        Name.Attribute: colors.green,
        Name.Builtin: f"{colors.red} italic",
        Name.Builtin.Pseudo: colors.red,
        Name.Class: colors.yellow,
        Name.Constant: colors.text,
        Name.Decorator: colors.text,
        Name.Entity: colors.text,
        Name.Exception: colors.yellow,
        Name.Function: colors.blue,
        Name.Label: f"{colors.teal} italic",
        Name.Namespace: colors.text,
        Name.Other: colors.text,
        Name.Tag: colors.blue,
        Name.Variable: f"{colors.text} italic",
        Name.Variable.Class: f"{colors.yellow} italic",
        Name.Variable.Global: f"{colors.text} italic",
        Name.Variable.Instance: f"{colors.text} italic",
        Number: colors.peach,
        Number.Bin: colors.peach,
        Number.Float: colors.peach,
        Number.Hex: colors.peach,
        Number.Integer: colors.peach,
        Number.Integer.Long: colors.peach,
        Number.Oct: colors.peach,
        Operator: colors.sky,
        Operator.Word: colors.mauve,
        Other: colors.text,
        Punctuation: colors.overlay2,
        String: colors.green,
        String.Backtick: colors.green,
        String.Char: colors.green,
        String.Doc: colors.green,
        String.Double: colors.green,
        String.Escape: colors.pink,
        String.Heredoc: colors.green,
        String.Interpol: colors.green,
        String.Other: colors.green,
        String.Regex: colors.pink,
        String.Single: colors.green,
        String.Symbol: colors.red,
        Text: colors.text,
        Whitespace: colors.text,
    }


class LatteStyle(Style):
    """Catppuccin Latte Pygments style."""

    background_color = LATTE.mantle
    highlight_color = LATTE.surface0
    line_number_background_color = LATTE.mantle
    line_number_color = LATTE.text
    line_number_special_background_color = LATTE.mantle
    line_number_special_color = LATTE.text

    styles = _make_styles(LATTE)


class FrappeStyle(Style):
    """Catppuccin Frappé Pygments style."""

    background_color = FRAPPE.mantle
    highlight_color = FRAPPE.surface0
    line_number_background_color = FRAPPE.mantle
    line_number_color = FRAPPE.text
    line_number_special_background_color = FRAPPE.mantle
    line_number_special_color = FRAPPE.text

    styles = _make_styles(FRAPPE)


class MacchiatoStyle(Style):
    """Catppuccin Macchiato Pygments style."""

    background_color = MACCHIATO.mantle
    highlight_color = MACCHIATO.surface0
    line_number_background_color = MACCHIATO.mantle
    line_number_color = MACCHIATO.text
    line_number_special_background_color = MACCHIATO.mantle
    line_number_special_color = MACCHIATO.text

    styles = _make_styles(MACCHIATO)


class MochaStyle(Style):
    """Catppuccin Mocha Pygments style."""

    background_color = COLOR_HEX.mantle
    highlight_color = COLOR_HEX.surface0
    line_number_background_color = COLOR_HEX.mantle
    line_number_color = COLOR_HEX.text
    line_number_special_background_color = COLOR_HEX.mantle
    line_number_special_color = COLOR_HEX.text

    styles = _make_styles(COLOR_HEX)


PYGMENTS_STYLES = {
    "catppuccin-latte": PygmentsSyntaxTheme(LatteStyle),
    "catppuccin-frappe": PygmentsSyntaxTheme(FrappeStyle),
    "catppuccin-macchiato": PygmentsSyntaxTheme(MacchiatoStyle),
    "catppuccin-mocha": PygmentsSyntaxTheme(MochaStyle),
}
