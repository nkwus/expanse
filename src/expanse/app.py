from __future__ import annotations
import pygame

from .clock import GameClock
from .config import WINDOW_W, WINDOW_H, TARGET_FPS, SIM_DT
from .render.theme import load_theme
from .render.renderer import Renderer
from .input.controller import Controller
from .scenarios import first_contact
from .audio import AudioEngine


class App:
    def __init__(self) -> None:
        pygame.init()
        self.surface = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.DOUBLEBUF)
        pygame.display.set_caption("Expanse // Tactical")
        self.theme = load_theme()
        self.clock = GameClock()
        self.world = first_contact.build()
        self.renderer = Renderer(self.surface, self.theme)
        self.controller = Controller(self.clock, self.world)
        self.audio = AudioEngine()
        self.pg_clock = pygame.time.Clock()
        self.running = False
        self.show_help = False

    def run(self) -> None:
        self.running = True
        while self.running:
            real_dt = self.pg_clock.tick(TARGET_FPS) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F4 and (event.mod & pygame.KMOD_ALT):
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.world.outcome is not None:
                    self.running = False
                    break
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                    self.show_help = not self.show_help
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN:
                    scope = self.renderer.scope
                    if scope.rect.collidepoint(event.pos):
                        # Wheel scrolls are buttons 4/5 (wheel up/down) in pygame.
                        if event.button == 4:
                            scope.zoom_by(1.25)
                        elif event.button == 5:
                            scope.zoom_by(0.8)
                        else:
                            world_pt = scope.screen_to_world(event.pos)
                            self.controller.on_scope_click(event.button, world_pt)
                    continue
                if self.controller.handle_key(event):
                    continue
            # Keyboard zoom [ / ]
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFTBRACKET]:
                self.renderer.scope.zoom_by(0.98)
            if keys[pygame.K_RIGHTBRACKET]:
                self.renderer.scope.zoom_by(1.02)
            # Advance sim
            ticks = self.clock.advance(real_dt)
            for _ in range(ticks):
                self.world.step(SIM_DT)
            self.audio.tick(self.world)
            # Cursor in world coords (only if over scope)
            cursor_world = None
            if self.renderer.scope.rect.collidepoint(mouse_pos):
                cursor_world = self.renderer.scope.screen_to_world(mouse_pos)
            # Render
            self.renderer.draw(
                self.world, self.clock,
                prompt=self.controller.prompt,
                cursor_world=cursor_world,
                show_help=self.show_help,
            )
            pygame.display.flip()
        self.audio.shutdown()
        pygame.quit()


def run() -> None:
    App().run()
