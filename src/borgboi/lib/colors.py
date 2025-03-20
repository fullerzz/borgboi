from catppuccin import PALETTE
from catppuccin.extras.pygments import FrappeStyle, LatteStyle, MacchiatoStyle, MochaStyle
from pydantic import BaseModel
from rich.syntax import SyntaxTheme

PYGMENTS_STYLES: dict[str, SyntaxTheme] = {
    "catppuccin-latte": LatteStyle,
    "catppuccin-frappe": FrappeStyle,
    "catppuccin-macchiato": MacchiatoStyle,
    "catppuccin-mocha": MochaStyle,
}  # type: ignore

flavor = PALETTE.mocha


class ColorHex(BaseModel):
    """
    ColorHex class to hold color hex values for Catppuccin Mocha theme.
    This class is used to provide a consistent way to access color values
    throughout the application.
    """

    rosewater: str = flavor.colors.rosewater.hex
    flamingo: str = flavor.colors.flamingo.hex
    pink: str = flavor.colors.pink.hex
    mauve: str = flavor.colors.mauve.hex
    red: str = flavor.colors.red.hex
    maroon: str = flavor.colors.maroon.hex
    peach: str = flavor.colors.peach.hex
    yellow: str = flavor.colors.yellow.hex
    green: str = flavor.colors.green.hex
    teal: str = flavor.colors.teal.hex
    sky: str = flavor.colors.sky.hex
    sapphire: str = flavor.colors.sapphire.hex
    blue: str = flavor.colors.blue.hex
    lavender: str = flavor.colors.lavender.hex
    text: str = flavor.colors.text.hex
    subtext0: str = flavor.colors.subtext0.hex
    subtext1: str = flavor.colors.subtext1.hex
    overlay0: str = flavor.colors.overlay0.hex
    overlay1: str = flavor.colors.overlay1.hex
    overlay2: str = flavor.colors.overlay2.hex
    surface0: str = flavor.colors.surface0.hex
    surface1: str = flavor.colors.surface1.hex
    surface2: str = flavor.colors.surface2.hex
    base: str = flavor.colors.base.hex
    mantle: str = flavor.colors.mantle.hex
    crust: str = flavor.colors.crust.hex


COLOR_HEX = ColorHex()
