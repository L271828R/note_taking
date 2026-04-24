#!/usr/bin/env python3
"""
Flappy Quiz — central pygame engine
Usage: python3 flappy-quiz.py --bank /path/to/questions.json [--title "My Quiz"]

questions.json format:
  { "title": "...", "questions": [ { "topic": "...", "q": "...",
    "opts": ["A","B","C","D"], "a": 0, "exp": "..." }, ... ] }
  OR a plain array of question objects.

Fields: topic (optional), q (required), opts (list of 4, required),
        a (int 0-3, required), exp (optional explanation string)
"""

import pygame
import sys
import random
import math
import json
import argparse
from pathlib import Path

pygame.init()

# ── Constants ─────────────────────────────────────────────────────────────────
W, H = 480, 680
FPS  = 60

BG_TOP    = (15,  20,  40)
BG_BOT    = (20,  30,  60)
PIPE_COL  = (80,  60, 160)
PIPE_RIM  = (120, 90, 200)
BIRD_COL  = (250, 200,  50)
BIRD_EYE  = ( 30,  30,  30)
BIRD_BEAK = (240, 120,  30)
GROUND_C  = ( 30,  25,  55)
WHITE     = (240, 240, 255)
GRAY      = (100, 110, 140)
GREEN     = ( 50, 220, 120)
RED       = (230,  70,  80)
INDIGO    = (100,  90, 210)
YELLOW    = (250, 200,  50)

GROUND_H         = 60
PIPE_W           = 70
GAP              = 180
PIPE_SPEED_INIT  = 2.5
GRAVITY          = 0.38
JUMP_V           = -7.5


# ── Helpers ───────────────────────────────────────────────────────────────────

def draw_gradient(surf, top_col, bot_col):
    for y in range(H):
        t = y / H
        r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (W, y))


def wrap_text(text, font, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        if font.size(test)[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def draw_wrapped(surf, text, font, color, x, y, max_w, center=False):
    lines = wrap_text(text, font, max_w)
    lh = font.get_height() + 2
    for i, line in enumerate(lines):
        s = font.render(line, True, color)
        rx = x - s.get_width() // 2 if center else x
        surf.blit(s, (rx, y + i * lh))
    return len(lines) * lh


# ── Bird ──────────────────────────────────────────────────────────────────────

class Bird:
    R = 18

    def __init__(self):
        self.x = 100
        self.y = H // 2
        self.vy = 0
        self.alive = True
        self.flap_timer = 0

    def jump(self):
        self.vy = JUMP_V
        self.flap_timer = 8

    def update(self):
        self.vy += GRAVITY
        self.y += self.vy
        if self.flap_timer > 0:
            self.flap_timer -= 1
        if self.y + self.R >= H - GROUND_H:
            self.y = H - GROUND_H - self.R
            self.alive = False

    def draw(self, surf):
        pygame.draw.circle(surf, BIRD_COL, (int(self.x), int(self.y)), self.R)
        wing_y = self.y + (4 if self.flap_timer > 0 else 8)
        pygame.draw.ellipse(surf, (210, 160, 30),
                            (int(self.x) - 14, int(wing_y) - 5, 20, 10))
        ex, ey = int(self.x) + 7, int(self.y) - 5
        pygame.draw.circle(surf, WHITE, (ex, ey), 6)
        pygame.draw.circle(surf, BIRD_EYE, (ex + 1, ey), 3)
        bx, by = int(self.x) + self.R - 2, int(self.y) + 2
        pygame.draw.polygon(surf, BIRD_BEAK,
                            [(bx, by), (bx + 10, by + 3), (bx, by + 6)])

    def get_rect(self):
        return pygame.Rect(self.x - self.R + 4, self.y - self.R + 4,
                           (self.R - 4) * 2, (self.R - 4) * 2)


# ── Pipe ──────────────────────────────────────────────────────────────────────

class Pipe:
    def __init__(self, x, gap_y, speed):
        self.x = x
        self.gap_y = gap_y
        self.speed = speed
        self.passed = False
        self.question = None

    def update(self):
        self.x -= self.speed

    def draw(self, surf):
        top_h = self.gap_y - GAP // 2
        bot_y = self.gap_y + GAP // 2
        bot_h = H - GROUND_H - bot_y
        pygame.draw.rect(surf, PIPE_COL, (self.x, 0, PIPE_W, top_h))
        pygame.draw.rect(surf, PIPE_RIM, (self.x - 5, top_h - 20, PIPE_W + 10, 20))
        pygame.draw.rect(surf, PIPE_COL, (self.x, bot_y, PIPE_W, bot_h))
        pygame.draw.rect(surf, PIPE_RIM, (self.x - 5, bot_y, PIPE_W + 10, 20))

    def get_rects(self):
        top_h = self.gap_y - GAP // 2
        bot_y = self.gap_y + GAP // 2
        return (pygame.Rect(self.x, 0, PIPE_W, top_h),
                pygame.Rect(self.x, bot_y, PIPE_W, H - GROUND_H - bot_y))


# ── Stars ─────────────────────────────────────────────────────────────────────

class Stars:
    def __init__(self, n=60):
        self.stars = [(random.randint(0, W), random.randint(0, H - GROUND_H),
                       random.random()) for _ in range(n)]

    def draw(self, surf, t):
        for x, y, phase in self.stars:
            bright = int(100 + 80 * math.sin(t * 0.04 + phase * 6))
            pygame.draw.circle(surf, (bright, bright, bright + 30), (x, y), 1)


# ── Quiz overlay ──────────────────────────────────────────────────────────────

class QuizOverlay:
    PANEL_W = 440
    PANEL_H = 390

    def __init__(self, question, fonts):
        self.q = question
        self.fonts = fonts
        self.answered = False
        self.correct  = False
        self.selected = -1
        self.timer    = 0
        self._build_rects()

    def _build_rects(self):
        px = (W - self.PANEL_W) // 2
        py = (H - self.PANEL_H) // 2
        self.panel_rect = pygame.Rect(px, py, self.PANEL_W, self.PANEL_H)
        self.opt_rects  = []
        oy = py + 160
        for i in range(4):
            self.opt_rects.append(
                pygame.Rect(px + 16, oy + i * 48, self.PANEL_W - 32, 40))

    def handle_click(self, pos):
        if self.answered:
            return
        for i, r in enumerate(self.opt_rects):
            if r.collidepoint(pos):
                self.selected = i
                self.answered = True
                self.correct  = (i == self.q["a"])
                self.timer    = FPS * 2

    def update(self):
        if self.answered:
            self.timer -= 1

    @property
    def done(self):
        return self.answered and self.timer <= 0

    def draw(self, surf):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        surf.blit(dim, (0, 0))

        px, py = self.panel_rect.x, self.panel_rect.y
        panel = pygame.Surface((self.PANEL_W, self.PANEL_H), pygame.SRCALPHA)
        panel.fill((20, 22, 45, 240))
        pygame.draw.rect(panel, INDIGO, (0, 0, self.PANEL_W, self.PANEL_H), 2, border_radius=14)
        surf.blit(panel, (px, py))

        fsm  = self.fonts["sm"]
        fmed = self.fonts["med"]

        topic = self.q.get("topic", "")
        if topic:
            badge = fsm.render(topic, True, (160, 140, 255))
            surf.blit(badge, (px + 16, py + 12))

        draw_wrapped(surf, self.q["q"], fsm, WHITE,
                     px + 16, py + (34 if topic else 18), self.PANEL_W - 32)

        letters   = "ABCD"
        opt_colors = [INDIGO, (130, 60, 200), (180, 50, 140), (200, 130, 30)]
        for i, (r, opt) in enumerate(zip(self.opt_rects, self.q["opts"])):
            bg, border, tc = (30, 28, 55), (60, 55, 110), WHITE
            if self.answered:
                if i == self.q["a"]:
                    bg, border, tc = (20, 70, 40), GREEN, GREEN
                elif i == self.selected:
                    bg, border, tc = (70, 20, 30), RED, RED
            pygame.draw.rect(surf, bg,     r, border_radius=8)
            pygame.draw.rect(surf, border, r, 1, border_radius=8)
            lbl = fsm.render(f"{letters[i]}.", True, opt_colors[i])
            surf.blit(lbl, (r.x + 10, r.y + 10))
            draw_wrapped(surf, opt, fsm, tc, r.x + 34, r.y + 10, r.w - 44)

        if self.answered:
            fb_y = py + self.PANEL_H - 60
            if self.correct:
                fb = fmed.render("✓ Correct! +1 life bonus", True, GREEN)
            else:
                fb = fmed.render("✗ Wrong — no bonus", True, RED)
            surf.blit(fb, (px + self.PANEL_W // 2 - fb.get_width() // 2, fb_y))

            exp = self.q.get("exp", "")
            if exp:
                draw_wrapped(surf, exp, fsm, GRAY,
                             px + 16, fb_y + 28, self.PANEL_W - 32)


# ── Particles ─────────────────────────────────────────────────────────────────

class Particle:
    def __init__(self, x, y, col):
        self.x, self.y = x, y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-5, 0)
        self.life = random.randint(20, 40)
        self.col  = col

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.2
        self.life -= 1

    def draw(self, surf):
        r = max(1, self.life // 10)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.col, max(0, min(255, self.life * 6))), (r, r), r)
        surf.blit(s, (int(self.x) - r, int(self.y) - r))


# ── Game ──────────────────────────────────────────────────────────────────────

class Game:
    PIPE_INTERVAL = 160

    def __init__(self, questions, title):
        self.all_questions = questions
        self.title         = title
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(f"Flappy Quiz — {title}")
        self.clock = pygame.time.Clock()
        self.fonts = {
            "sm":  pygame.font.SysFont("Arial", 14),
            "med": pygame.font.SysFont("Arial", 17, bold=True),
            "lg":  pygame.font.SysFont("Arial", 24, bold=True),
            "xl":  pygame.font.SysFont("Arial", 38, bold=True),
        }
        self.stars  = Stars()
        self.q_pool = questions[:]
        random.shuffle(self.q_pool)
        self.q_idx  = 0
        self._reset()

    def _next_q(self):
        q = self.q_pool[self.q_idx % len(self.q_pool)]
        self.q_idx += 1
        if self.q_idx % len(self.q_pool) == 0:
            random.shuffle(self.q_pool)
        return q

    def _reset(self):
        self.bird        = Bird()
        self.pipes       = []
        self.particles   = []
        self.score       = 0
        self.lives       = 3
        self.pipe_speed  = PIPE_SPEED_INIT
        self.next_pipe_x = W + 80
        self.quiz        = None
        self.frame       = 0
        self.state       = "start"

    def _spawn_pipe(self):
        gap_y = random.randint(H // 4, H - GROUND_H - H // 4)
        p = Pipe(self.next_pipe_x, gap_y, self.pipe_speed)
        p.question = self._next_q()
        self.pipes.append(p)
        self.next_pipe_x = (self.pipes[-1].x + self.PIPE_INTERVAL
                            + random.randint(0, 60))

    def _burst(self, x, y, col, n=18):
        for _ in range(n):
            self.particles.append(Particle(x, y, col))

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    if self.state == "start":
                        self.state = "playing"
                    elif self.state == "playing" and not self.quiz:
                        self.bird.jump()
                    elif self.state == "dead":
                        self._reset(); self.state = "playing"
                if event.key == pygame.K_r and self.state == "dead":
                    self._reset()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.quiz:
                    self.quiz.handle_click(event.pos)
                elif self.state == "start":
                    self.state = "playing"
                elif self.state == "playing":
                    self.bird.jump()
                elif self.state == "dead":
                    self._reset(); self.state = "playing"

    def _update(self):
        if self.state != "playing":
            return
        self.frame += 1

        if self.quiz:
            self.quiz.update()
            if self.quiz.done:
                if self.quiz.correct:
                    self.lives = min(self.lives + 1, 5)
                    self._burst(self.bird.x, self.bird.y, (80, 220, 120))
                self.quiz = None
            return

        self.bird.update()

        if not self.pipes or self.pipes[-1].x < W - self.PIPE_INTERVAL:
            self._spawn_pipe()

        for p in self.pipes:
            p.update()
            if not p.passed and p.x + PIPE_W < self.bird.x:
                p.passed = True
                self.score += 1
                self._burst(self.bird.x, self.bird.y, YELLOW, 12)
                self.quiz = QuizOverlay(p.question, self.fonts)
                if self.score % 5 == 0:
                    self.pipe_speed = min(PIPE_SPEED_INIT + self.score * 0.08, 6.0)
                    for pp in self.pipes:
                        pp.speed = self.pipe_speed
            if self.bird.alive:
                rt, rb = p.get_rects()
                if self.bird.get_rect().colliderect(rt) or \
                   self.bird.get_rect().colliderect(rb):
                    self.bird.alive = False

        self.pipes = [p for p in self.pipes if p.x + PIPE_W > -10]

        for pt in self.particles:
            pt.update()
        self.particles = [pt for pt in self.particles if pt.life > 0]

        if not self.bird.alive:
            self._burst(self.bird.x, self.bird.y, RED, 24)
            self.lives -= 1
            if self.lives <= 0:
                self.state = "dead"
            else:
                self.bird = Bird()

    def _draw_hud(self):
        sc = self.fonts["lg"].render(str(self.score), True, WHITE)
        self.screen.blit(sc, (W // 2 - sc.get_width() // 2, 18))
        for i in range(self.lives):
            pygame.draw.circle(self.screen, YELLOW, (16 + i * 24, 18), 8)
            pygame.draw.circle(self.screen, (200, 150, 20), (16 + i * 24, 18), 8, 2)
        sp = self.fonts["sm"].render(f"spd {self.pipe_speed:.1f}", True, GRAY)
        self.screen.blit(sp, (W - sp.get_width() - 10, 10))

    def _draw_ground(self):
        pygame.draw.rect(self.screen, GROUND_C, (0, H - GROUND_H, W, GROUND_H))
        pygame.draw.line(self.screen, INDIGO, (0, H - GROUND_H), (W, H - GROUND_H), 2)

    def _draw_start(self):
        t = self.fonts["xl"].render("Flappy Quiz", True, YELLOW)
        self.screen.blit(t, (W // 2 - t.get_width() // 2, H // 3 - 40))
        sub = self.fonts["med"].render(self.title, True, (160, 140, 255))
        self.screen.blit(sub, (W // 2 - sub.get_width() // 2, H // 3 + 14))
        for i, txt in enumerate([
            "SPACE / Click to flap",
            "Answer questions to earn extra lives!",
            "Press SPACE or click to start",
        ]):
            col = (100, 200, 160) if i == 2 else GRAY
            s = self.fonts["sm"].render(txt, True, col)
            self.screen.blit(s, (W // 2 - s.get_width() // 2, H // 2 + 10 + i * 28))

    def _draw_dead(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        go = self.fonts["xl"].render("Game Over", True, RED)
        self.screen.blit(go, (W // 2 - go.get_width() // 2, H // 3 - 20))
        sc = self.fonts["lg"].render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(sc, (W // 2 - sc.get_width() // 2, H // 3 + 44))
        r = self.fonts["med"].render("SPACE / Click to retry", True, GRAY)
        self.screen.blit(r, (W // 2 - r.get_width() // 2, H // 2 + 10))

    def run(self):
        bg = pygame.Surface((W, H))
        draw_gradient(bg, BG_TOP, BG_BOT)

        while True:
            self._handle_events()
            self._update()

            self.screen.blit(bg, (0, 0))
            self.stars.draw(self.screen, self.frame)
            for p in self.pipes:
                p.draw(self.screen)
            self._draw_ground()
            for pt in self.particles:
                pt.draw(self.screen)
            if self.state in ("playing", "dead"):
                self.bird.draw(self.screen)
            if self.state == "start":
                self._draw_start()
            elif self.state == "playing":
                self._draw_hud()
                if self.quiz:
                    self.quiz.draw(self.screen)
            elif self.state == "dead":
                self._draw_hud()
                self._draw_dead()

            pygame.display.flip()
            self.clock.tick(FPS)


# ── Entry point ───────────────────────────────────────────────────────────────

def load_questions(bank_path: str):
    path = Path(bank_path)
    if not path.exists():
        print(f"Error: question bank not found: {bank_path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return "Quiz", data
    title = data.get("title", "Quiz")
    return title, data.get("questions", [])


def main():
    parser = argparse.ArgumentParser(description="Flappy Quiz engine")
    parser.add_argument("--bank",  required=True, help="Path to questions.json")
    parser.add_argument("--title", default=None,  help="Override quiz title")
    args = parser.parse_args()

    title, questions = load_questions(args.bank)
    if args.title:
        title = args.title
    if not questions:
        print("No questions found in the question bank.", file=sys.stderr)
        sys.exit(1)

    Game(questions, title).run()


if __name__ == "__main__":
    main()
