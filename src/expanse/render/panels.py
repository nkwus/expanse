from __future__ import annotations
from math import pi
import pygame

from . import theme as T
from . import draw


def draw_top_bar(surface, rect, font, sim_time, multiplier_label, real_time):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    draw.draw_text(surface, font, "EXPANSE // TACTICAL", (rect.x + 12, rect.centery), T.TEXT_HI, align="ml")
    draw.draw_text(surface, font, f">> {multiplier_label}", (rect.centerx, rect.centery), T.ACCENT, align="c")
    draw.draw_text(surface, font, f"SIM T+{_fmt_hms(sim_time)}", (rect.right - 220, rect.centery), T.TEXT, align="ml")
    draw.draw_text(surface, font, f"REAL {_fmt_hms(real_time)}", (rect.right - 12, rect.centery), T.TEXT_DIM, align="mr")


def draw_command_bar(surface, rect, font, prompt=None, cursor_world=None):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    text = prompt or "[Space] Pause  [1-4] Speed  [H] Hdg  [T] Thrust  [X] Cut  [B] Burn  [F] Fire  [P] PDC  [WASD] Pan  [C] Ctr  [F1] Help"
    draw.draw_text(surface, font, text, (rect.x + 12, rect.centery), T.TEXT, align="ml")
    if cursor_world is not None:
        label = f"{cursor_world.x / 1000:+.1f} km  {cursor_world.y / 1000:+.1f} km"
        draw.draw_text(surface, font, label, (rect.right - 12, rect.centery), T.TEXT_DIM, align="mr")


def draw_status_panel(surface, rect, font, ship):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    y = rect.y + 8
    lh = font.get_linesize() + 2
    draw.draw_text(surface, font, "=== OWNSHIP ===", (rect.x + 8, y), T.TEXT_DIM); y += lh
    if ship is None:
        draw.draw_text(surface, font, "no ownship", (rect.x + 8, y), T.STALE)
        return
    draw.draw_text(surface, font, ship.name, (rect.x + 8, y), T.OWNSHIP); y += lh * 2
    hp_pct = max(0, min(100, int(100 * ship.hull_hp / 1000.0)))
    draw.draw_text(surface, font, f"HULL   {ship.hull_hp:>5.0f}  ({hp_pct}%)", (rect.x + 8, y), T.TEXT); y += lh
    draw.draw_text(surface, font, f"DRIVE  {ship.drive.current_g:>4.1f}g / {ship.cmd_thrust_g:>4.1f}g", (rect.x + 8, y), T.TEXT); y += lh
    draw.draw_text(surface, font, f"CREW-G {ship.crew_g_tolerance:>4.1f}g max", (rect.x + 8, y), T.TEXT_DIM); y += lh
    hdg_deg = (ship.heading * 180.0 / pi) % 360.0
    draw.draw_text(surface, font, f"HDG    {hdg_deg:>5.1f}°", (rect.x + 8, y), T.TEXT); y += lh
    vel_mag = (ship.vel.x ** 2 + ship.vel.y ** 2) ** 0.5
    draw.draw_text(surface, font, f"VEL    {vel_mag / 1000:>5.2f} km/s", (rect.x + 8, y), T.TEXT); y += lh
    pos_lbl = f"{ship.pos.x / 1000:+.1f}, {ship.pos.y / 1000:+.1f} km"
    draw.draw_text(surface, font, f"POS    {pos_lbl}", (rect.x + 8, y), T.TEXT); y += lh
    ap_label = getattr(ship.autopilot, "label", None) if ship.autopilot is not None else None
    if ap_label:
        draw.draw_text(surface, font, f"AUTO   {ap_label}", (rect.x + 8, y), T.ACCENT); y += lh
    else:
        draw.draw_text(surface, font, "AUTO   --", (rect.x + 8, y), T.TEXT_DIM); y += lh
    y += lh
    mag = ship.magazine
    if mag is not None:
        tubes = "".join("R" if c <= 0.0 else "." for c in mag.tubes_cooldown_s)
        draw.draw_text(surface, font, f"TORP   {mag.torpedoes_remaining:>3d}  tubes {tubes}", (rect.x + 8, y), T.TEXT); y += lh
    if ship.pdcs:
        ready = sum(1 for p in ship.pdcs if p.cooldown_remaining_s <= 0.0)
        draw.draw_text(surface, font, f"PDC    {ready}/{len(ship.pdcs)} ready  {ship.pdc_mode}", (rect.x + 8, y), T.TEXT); y += lh


def draw_contact_panel(surface, rect, font, tracks=None, ownship=None, now: float = 0.0):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    y = rect.y + 8
    lh = font.get_linesize() + 2
    draw.draw_text(surface, font, "=== CONTACTS ===", (rect.x + 8, y), T.TEXT_DIM); y += lh
    draw.draw_text(surface, font, "TRK  CLS  RNG     BRG  AGE", (rect.x + 8, y), T.TEXT_DIM); y += lh
    if not tracks:
        draw.draw_text(surface, font, "  no contacts", (rect.x + 8, y), T.STALE)
        return
    for t in tracks:
        color = T.HOSTILE if t.confidence > 0.1 else T.STALE
        age = max(0.0, now - t.last_seen_time)
        cur = t.predict_pos(age) if ownship else t.last_seen_pos
        if ownship is not None:
            dx = cur.x - ownship.pos.x
            dy = cur.y - ownship.pos.y
            rng = (dx * dx + dy * dy) ** 0.5
            import math
            brg = (90.0 - math.degrees(math.atan2(dy, dx))) % 360.0
        else:
            rng = t.last_seen_pos.length()
            brg = 0.0
        cls = {"UNKNOWN": "???", "SHIP": "SHIP", "TORPEDO": "TORP"}.get(t.classification.name, "???")
        row = f"T{t.track_id:03d} {cls:4s} {rng/1000:>5.0f}km {brg:>4.0f}° {age:>4.0f}s"
        draw.draw_text(surface, font, row, (rect.x + 8, y), color); y += lh
        if y > rect.bottom - lh:
            break


def draw_event_log(surface, rect, font, events=None):
    pygame.draw.rect(surface, T.PANEL_BG, rect)
    pygame.draw.rect(surface, T.PANEL_BORDER, rect, 1)
    y = rect.y + 8
    lh = font.get_linesize() + 2
    draw.draw_text(surface, font, "=== EVENT LOG ===", (rect.x + 8, y), T.TEXT_DIM); y += lh
    if not events:
        draw.draw_text(surface, font, "  ...", (rect.x + 8, y), T.STALE)
        return
    # Show newest first, fit as many as rect allows
    max_rows = max(1, (rect.bottom - y) // lh)
    shown = events[-max_rows:][::-1]
    for e in shown:
        stamp = _fmt_hms(e.time)
        txt = f"T+{stamp}  {e.message}"
        # Truncate if too wide
        maxw = rect.width - 16
        while font.size(txt)[0] > maxw and len(txt) > 4:
            txt = txt[:-2]
        draw.draw_text(surface, font, txt, (rect.x + 8, y), T.TEXT); y += lh


def _fmt_hms(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
