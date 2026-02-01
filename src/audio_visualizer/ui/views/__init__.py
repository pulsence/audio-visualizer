from .general.generalView import View
from .general.utilities import Fonts

Fonts.h1_font.setPointSize(24)
Fonts.h1_font.setBold(True)
Fonts.h2_font.setPointSize(16)
Fonts.h2_font.setUnderline(True)

__all__ = ["View", "Fonts"]


