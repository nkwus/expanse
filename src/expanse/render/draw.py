from __future__ import annotations
from math import cos, sin, tau
import pygame

from . import theme as T


def draw_dashed_circle(surface, color, center, radius, dashes=64):
    if radius < 3:
        return
    cx, cy = center
    step = tau / (dashes * 2)
    for i in range(dashes):
        a0 = i * 2 * step
        a1 = a0 + step
        p0 = (cx + cos(a0) * radius, cy + sin(a0) * radius)
        p1 = (cx + cos(a1) * radius, cy + sin(a1) * radius)
        pygame.draw.aaline(surface, color, p0, p1)


def draw_arrow(surface, color, start, end, head_len=8):
    pygame.draw.aaline(surface, color, start, end)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    L = (dx * dx + dy * dy) ** 0.5
    if L < 1e-6:
        return
    ux, uy = dx / L, dy / L
    left = (end[0] - ux * head_len - uy * head_len * 0.5,
            end[1] - uy * head_len + ux * head_len * 0.5)
    right = (end[0] - ux * head_len + uy * head_len * 0.5,
             end[1] - uy * head_len - ux * head_len * 0.5)
    pygame.draw.aaline(surface, color, end, left)
    pygame.draw.aaline(surface, color, end, right)


def draw_text(surface, font, text, pos, color=T.TEXT, align="tl"):
    surf = font.render(text, True, color)
    r = surf.get_rect()
    x, y = pos
    if align == "tl":
        r.topleft = (x, y)
    elif align == "tr":
        r.topright = (x, y)
    elif align == "tc":
        r.midtop = (x, y)
    elif align == "bl":
        r.bottomleft = (x, y)
    elif align == "br":
        r.bottomright = (x, y)
    elif align == "ml":
        r.midleft = (x, y)
    elif align == "mr":
        r.midright = (x, y)
    elif align == "c":
        r.center = (x, y)
    surface.blit(surf, r)
    return r


def draw_panel(surface, rect, label=None, font=None):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    if label and font:
        draw_text(surface, font, label, (rect.x + 6, rect.y + 4), T.TEXT_DIM)
