"""
Application-wide constants and configuration defaults.

This module centralizes all magic numbers, default values, and configuration
constants used throughout the PDF signing application.
"""

from pathlib import Path
import os

# Application metadata
APP_NAME = "PDF İmzacı"
APP_VERSION = "2.3"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

# Paths and directories
HOME_DIR = Path(os.environ.get('USERPROFILE', Path.home()))
CONFIG_DIR = HOME_DIR / '.imzaci'
CONFIG_FILE = CONFIG_DIR / 'config.json'
DEFAULT_DLL = Path(r"C:\Windows\System32\akisp11.dll")

# Temporary directory for generated files
import tempfile
TEMP_DIR = Path(tempfile.gettempdir()) / 'imzaci'

# UI Geometry and Layout
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 860
WINDOW_THEME = "flatly"  # light theme options: flatly, litera, lumen, etc.

# Signature and overlay settings (persisted under 'signature' in config)
DEFAULT_SIGNATURE_SETTINGS = {
    # NOTE: 'width_mm' is used as the signature font size (mm) in the current UI semantics
    'width_mm': 3.0,         # font size / text size for the generated signature (mm)
    'logo_width_mm': 15.0,   # logo image width in mm (user-requested default)
    'margin_mm': 12.0,       # legacy single margin value (mm)
    'margin_x_mm': 12.0,     # horizontal margin (mm)
    'margin_y_mm': 25.0,     # vertical margin (mm)
    'placement': 'top-right', # default placement
    'font_family': 'Segoe',   # default font family for signature text
    'font_style': 'Bold',     # default font style
} 

# Signature placement options: (code, localized_label)
PLACEMENT_OPTIONS = [
    ('top-right', 'Sağ Üst'),
    ('top-left', 'Sol Üst'),
    ('bottom-right', 'Sağ Alt'),
    ('bottom-left', 'Sol Alt'),
    ('center', 'Orta'),
]

# Font configuration
FONT_FAMILY = "Segoe UI"
FONT_EMOJI_FAMILY = "Segoe UI Emoji"
TITLE_FONT_SIZE = 20
SUBTITLE_FONT_SIZE = 10
ICON_FONT_SIZE = 12
SMALL_FONT_SIZE = 8

# Icon configuration
ICON_SIZE_NORMAL = 18
ICON_SIZE_LARGE = 28
ICON_SIZE_HOVER = 30

# PDF rendering
PDF_PAGE_WIDTH_PT = 595.0   # A4 width in points
PDF_PAGE_HEIGHT_PT = 842.0  # A4 height in points
MM_TO_POINTS = 72.0 / 25.4  # conversion factor: millimeters to points
IMAGE_SCALE_FACTOR = 0.8
MAX_IMAGE_WIDTH_RATIO = 0.2  # max 20% of page width

# Logging and output
LOG_PANEL_HEIGHT = 85  # pixels for log output
LOG_ROWS = 7

# PKCS#11 parameters
PKCS11_TIMEOUT = 30  # seconds
SLOT_REFRESH_INTERVAL = 5000  # milliseconds

# File size thresholds
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10 MB (for PDF compression decisions)

# Debounce timings
PREVIEW_REFRESH_DEBOUNCE = 200  # milliseconds
SIGNATURE_SAVE_DEBOUNCE = 500   # milliseconds
