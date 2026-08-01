"""
ADS OS Desktop -- Brand Theme
Matches ADS Creative Space's existing brand system.
"""

BRASS = "#B68100"
INK = "#1A1A1A"
PARCHMENT = "#F5F0E6"
WHITE = "#FFFFFF"
MUTED = "#6B6B6B"

# Standard button roles -- (fg_color, hover_color). Use these for every new
# button instead of picking colors ad hoc, so the app stays visually
# consistent as more screens are built. Existing buttons across already-
# shipped modules are not being retroactively refactored to this in one
# pass -- that's a separate, mechanical, lower-risk future cleanup.
BUTTON_PRIMARY = (BRASS, INK)          # main call-to-action (Save, Generate, +New)
BUTTON_SECONDARY = (WHITE, PARCHMENT)  # secondary action (Cancel, Edit)
BUTTON_DANGER = ("#8B2E2E", "#5E1F1F")  # destructive action (Delete)
BUTTON_SUCCESS = ("#2E8B57", INK)       # positive/confirm action
BUTTON_NEUTRAL = (MUTED, INK)           # low-emphasis action (Clear Log)

# NOTE: True Bodoni Moda / Work Sans require the font files to be installed
# on the machine and registered with Tkinter (via a package like tkextrafont).
# Until you decide it's worth bundling those font files, these are the closest
# widely-available system fonts on Windows that approximate the same feel:
FONT_HEADING = ("Georgia", 20, "bold")     # serif, stands in for Bodoni Moda
FONT_SUBHEADING = ("Georgia", 14, "bold")
FONT_BODY = ("Segoe UI", 12)                # stands in for Work Sans
FONT_BODY_BOLD = ("Segoe UI", 12, "bold")
FONT_SMALL = ("Segoe UI", 10)
