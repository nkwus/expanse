from __future__ import annotations
import pygame

from .theme import Theme
from .scope import ScopeView, draw_scope
from .panels import (
    draw_top_bar, draw_command_bar, draw_status_panel,
    draw_contact_panel, draw_event_log,
)
from . import theme as T
from ..config import TOP_BAR_H, CMD_BAR_H, LEFT_PANEL_W, RIGHT_PANEL_W, DEFAULT_SCOPE_VIEW_M


class Renderer:
    def __init__(self, surface, theme: Theme) -> None:
        self.surface = surface
        self.theme = theme
        w, h = surface.get_size()
        self.top_rect = pygame.Rect(0, 0, w, TOP_BAR_H)
        self.cmd_rect = pygame.Rect(0, h - CMD_BAR_H, w, CMD_BAR_H)
        self.left_rect = pygame.Rect(0, TOP_BAR_H, LEFT_PANEL_W, h - TOP_BAR_H - CMD_BAR_H)
        self.right_rect = pygame.Rect(w - RIGHT_PANEL_W, TOP_BAR_H, RIGHT_PANEL_W, h - TOP_BAR_H - CMD_BAR_H)
        self.scope_rect = pygame.Rect(
            LEFT_PANEL_W, TOP_BAR_H,
            w - LEFT_PANEL_W - RIGHT_PANEL_W,
            h - TOP_BAR_H - CMD_BAR_H,
        )
        rh = self.right_rect.height
        self.contacts_rect = pygame.Rect(self.right_rect.x, self.right_rect.y, self.right_rect.width, int(rh * 0.6))
        self.events_rect = pygame.Rect(
            self.right_rect.x, self.contacts_rect.bottom,
            self.right_rect.width, rh - self.contacts_rect.height,
        )
        self.scope = ScopeView(rect=self.scope_rect)
        self.scope.scale_px_per_m = self.scope_rect.width / DEFAULT_SCOPE_VIEW_M

    def draw(self, world, clock, prompt=None, cursor_world=None, show_help: bool = False) -> None:
        self.surface.fill(T.BG)
        draw_top_bar(
            self.surface, self.top_rect, self.theme.font_md,
            clock.now_sim, clock.multiplier_label, clock.now_real,
        )
        ownship = world.player_ship()
        tracks = world.player_tracks().all() if hasattr(world, "player_tracks") else []
        events = getattr(world, "events", [])
        draw_status_panel(self.surface, self.left_rect, self.theme.font_md, ownship)
        draw_scope(self.surface, self.scope, world, self.theme.font_sm)
        draw_contact_panel(
            self.surface, self.contacts_rect, self.theme.font_md,
            tracks=tracks, ownship=ownship, now=world.now_sim,
        )
        draw_event_log(self.surface, self.events_rect, self.theme.font_md, events)
        draw_command_bar(self.surface, self.cmd_rect, self.theme.font_md, prompt, cursor_world)
        if show_help:
            self._draw_help_overlay()
        outcome = getattr(world, "outcome", None)
        if outcome is not None:
            self._draw_outcome_banner(outcome, events)

    def _draw_help_overlay(self) -> None:
        import pygame
        w, h = self.surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.surface.blit(overlay, (0, 0))
        from .draw import draw_text
        lines = [
            "EXPANSE // TACTICAL  —  KEY REFERENCE",
            "",
            "TIME",
            "  Space    pause / resume",
            "  1-4      set multiplier (1x / 10x / 100x / 1000x)",
            "  , / .    step multiplier down / up",
            "",
            "MANEUVER",
            "  H        heading (then click scope to aim)",
            "  T 0-9    thrust in g (clamped by crew tolerance)",
            "  + / -    nudge thrust by 1 g",
            "  X        cut drive",
            "  B        flip-and-burn to zero velocity",
            "",
            "WEAPONS",
            "  F        fire torpedo (then click a contact)",
            "  P        cycle PDC mode (AUTO / HOLD / MANUAL)",
            "",
            "SCOPE",
            "  wheel    zoom            [ / ]   slow zoom",
            "  WASD     pan             C       center on ownship",
            "",
            "F1 to close",
        ]
        x = w // 2 - 220
        y = 80
        lh = self.theme.font_md.get_linesize() + 2
        for line in lines:
            draw_text(self.surface, self.theme.font_md, line, (x, y), T.TEXT)
            y += lh

    def _draw_outcome_banner(self, outcome, events) -> None:
        import pygame
        w, h = self.surface.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.surface.blit(overlay, (0, 0))
        colors = {"win": T.OWNSHIP, "loss": T.HOSTILE, "stalemate": T.TEXT_DIM}
        color = colors.get(outcome, T.TEXT)
        titles = {"win": "VICTORY", "loss": "LOSS", "stalemate": "STALEMATE"}
        font = self.theme.font_xl
        from .draw import draw_text
        draw_text(self.surface, font, titles.get(outcome, outcome.upper()), (w // 2, h // 2 - 20), color, align="c")
        # Last scenario-end message as subtitle
        sub = next((e.message for e in reversed(events) if e.kind.name == "SCENARIO_END"), "")
        draw_text(self.surface, self.theme.font_md, sub, (w // 2, h // 2 + 20), T.TEXT, align="c")
        draw_text(self.surface, self.theme.font_md, "[Esc] Quit", (w // 2, h // 2 + 48), T.TEXT_DIM, align="c")
