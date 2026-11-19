"""Brand settings for «صحتك أهم». Change colours or fonts here only."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
FONT_BOLD = str(ASSETS / "fonts" / "Tajawal-Bold.ttf")
FONT_REGULAR = str(ASSETS / "fonts" / "Tajawal-Regular.ttf")
LOGO = ASSETS / "logo.png"          # optional: transparent PNG of the logo
MUSIC_DIR = ASSETS / "music"        # optional: royalty-free .mp3 files

BRAND_NAME = "صحتك أهم"

# Colours (RGB)
DUSTY_PINK = (212, 165, 165)   # #D4A5A5
DEEP_ROSE = (168, 119, 123)    # #A8777B
SUGAR = (250, 246, 240)        # #FAF6F0
TEXT = (74, 63, 58)            # #4A3F3A
WHITE = (255, 255, 255)

# Formats
REEL_SIZE = (1080, 1920)
SLIDE_SIZE = (1080, 1350)
FPS = 30

# ElevenLabs voice chosen for the page
VOICE_ID = "g3YpdjT1OTh9cunaumJs"
VOICE_MODEL = "eleven_multilingual_v2"

# One fixed style description so every AI image matches
IMAGE_STYLE = (
    "Soft natural window light, overhead or 45-degree angle, light wood or cream marble "
    "surface, cream linen and dusty-pink props, shallow depth of field, calm, clean, "
    "minimal, warm editorial food photography. No faces, no people except hands, "
    "no text, no letters, no logos, no watermarks."
)
