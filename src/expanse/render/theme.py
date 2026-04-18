from __future__ import annotations
from dataclasses import dataclass
import pygame


BG = (5, 10, 12)
GRID = (18, 32, 34)
RING = (28, 55, 55)
RING_LABEL = (70, 120, 110)
OWNSHIP = (110, 240, 140)
FRIENDLY = (100, 220, 240)
HOSTILE = (240, 160, 60)
WEAPON = (240, 80, 60)
STALE = (90, 100, 105)
UNKNOWN = (200, 200, 210)
TEXT = (180, 220, 220)
TEXT_DIM = (100, 140, 140)
TEXT_HI = (230, 250, 250)
PANEL_BG = (10, 18, 22)
PANEL_BORDER = (30, 60, 60)
ACCENT = (200, 230, 80)
TRACK_PREDICTED = (90, 150, 170)


@dataclass
class Theme:
    font_sm: pygame.font.Font
    font_md: pygame.font.Font
    font_lg: pygame.font.Font
    font_xl: pygame.font.Font


def load_theme() -> Theme:
    pygame.font.init()
    name = pygame.font.match_font("dejavusansmono,consolas,menlo,liberationmono,monospace")
    return Theme(
        font_sm=pygame.font.Font(name, 12),
        font_md=pygame.font.Font(name, 14),
        font_lg=pygame.font.Font(name, 18),
        font_xl=pygame.font.Font(name, 24),
    )
