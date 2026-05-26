from __future__ import annotations

import math
import random
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

WIDTH, HEIGHT = 1280, 720
FPS = 60
SAMPLE_RATE = 22050

WHITE = (235, 238, 230)
BLACK = (8, 10, 12)
RED = (210, 43, 43)
GOLD = (221, 184, 79)
CYAN = (70, 210, 220)
GREEN = (72, 190, 106)
GREY = (50, 55, 59)
DARK = (22, 24, 26)
STONE = (86, 83, 76)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def length(v: pygame.Vector2) -> float:
    return math.hypot(v.x, v.y)


def safe_normalize(v: pygame.Vector2) -> pygame.Vector2:
    if v.length_squared() <= 0.001:
        return pygame.Vector2(1, 0)
    return v.normalize()


def load_image(name: str, size: tuple[int, int]) -> pygame.Surface:
    image = pygame.image.load(ASSETS / name).convert_alpha()
    return pygame.transform.smoothscale(image, size)


def make_random_music() -> pygame.mixer.Sound | None:
    if not pygame.mixer.get_init():
        return None
    rng = random.Random()
    root = rng.choice([55, 58.27, 61.74, 65.41, 73.42])
    scales = [
        [0, 2, 3, 7, 8, 10],
        [0, 1, 5, 7, 8, 11],
        [0, 3, 5, 6, 7, 10],
    ]
    scale = rng.choice(scales)
    tempo = rng.choice([92, 104, 116])
    beat = 60 / tempo
    bars = 16
    seconds = bars * beat * 4
    count = int(seconds * SAMPLE_RATE)
    samples = array("h", [0]) * count

    def add_tone(start: float, duration: float, freq: float, volume: float, wave: str = "sine") -> None:
        start_i = int(start * SAMPLE_RATE)
        end_i = min(count, int((start + duration) * SAMPLE_RATE))
        if start_i >= count:
            return
        fade = max(1, int(0.025 * SAMPLE_RATE))
        for i in range(start_i, end_i):
            t = (i - start_i) / SAMPLE_RATE
            env = min(1.0, (i - start_i) / fade, (end_i - i) / fade)
            if wave == "saw":
                raw = 2 * ((t * freq) % 1) - 1
            elif wave == "square":
                raw = 1 if math.sin(2 * math.pi * freq * t) >= 0 else -1
            else:
                raw = math.sin(2 * math.pi * freq * t)
            samples[i] = int(clamp(samples[i] + raw * volume * env * 32767, -32767, 32767))

    for bar in range(bars):
        base_time = bar * beat * 4
        degree = rng.choice(scale)
        bass = root * (2 ** (degree / 12))
        add_tone(base_time, beat * 3.8, bass, 0.18, "saw")
        add_tone(base_time + beat * 2, beat * 1.6, bass * 0.5, 0.16, "sine")
        for step in range(4):
            if rng.random() < 0.78:
                note = root * 2 * (2 ** (rng.choice(scale) / 12))
                add_tone(base_time + step * beat, beat * rng.choice([0.35, 0.5, 0.75]), note, 0.09, "square")
        for pulse in range(8):
            if pulse in (0, 4) or rng.random() < 0.25:
                add_tone(base_time + pulse * beat / 2, 0.055, rng.choice([82, 98, 123]), 0.20, "sine")

    return pygame.mixer.Sound(buffer=samples)


@dataclass
class Attack:
    windup: float
    active: float
    recovery: float
    reach: float
    arc: float
    damage: int
    posture: int
    red_flash: bool = False

    @property
    def total(self) -> float:
        return self.windup + self.active + self.recovery


class Fighter:
    def __init__(
        self,
        name: str,
        pos: tuple[float, float],
        radius: int,
        hp: int,
        posture_max: int,
        color: tuple[int, int, int],
        portrait: pygame.Surface | None = None,
    ) -> None:
        self.name = name
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2()
        self.radius = radius
        self.hp = hp
        self.max_hp = hp
        self.posture = 0
        self.posture_max = posture_max
        self.color = color
        self.portrait = portrait
        self.facing = pygame.Vector2(1, 0)
        self.attack: Attack | None = None
        self.attack_timer = 0.0
        self.cooldown = 0.0
        self.hit_done = False
        self.parry_timer = 0.0
        self.parry_cooldown = 0.0
        self.stagger = 0.0
        self.invuln = 0.0
        self.alive = True
        self.flash = 0.0

    def start_attack(self, attack: Attack, facing: pygame.Vector2) -> bool:
        if self.cooldown > 0 or self.attack or self.stagger > 0 or not self.alive:
            return False
        self.attack = attack
        self.attack_timer = 0
        self.hit_done = False
        self.cooldown = attack.total + 0.08
        self.facing = safe_normalize(facing)
        return True

    def start_parry(self) -> bool:
        if self.parry_cooldown > 0 or self.stagger > 0 or not self.alive:
            return False
        self.parry_timer = 0.18
        self.parry_cooldown = 0.48
        return True

    def take_damage(self, damage: int, posture: int, knockback: pygame.Vector2 | None = None) -> None:
        if self.invuln > 0 or not self.alive:
            return
        self.hp -= damage
        self.posture = clamp(self.posture + posture, 0, self.posture_max)
        self.flash = 0.16
        if knockback:
            self.pos += knockback
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def update_timers(self, dt: float) -> None:
        self.cooldown = max(0, self.cooldown - dt)
        self.parry_timer = max(0, self.parry_timer - dt)
        self.parry_cooldown = max(0, self.parry_cooldown - dt)
        self.stagger = max(0, self.stagger - dt)
        self.invuln = max(0, self.invuln - dt)
        self.flash = max(0, self.flash - dt)
        if self.attack:
            self.attack_timer += dt
            if self.attack_timer >= self.attack.total:
                self.attack = None

    def attack_phase(self) -> str:
        if not self.attack:
            return "idle"
        if self.attack_timer < self.attack.windup:
            return "windup"
        if self.attack_timer < self.attack.windup + self.attack.active:
            return "active"
        return "recovery"

    def draw(self, surf: pygame.Surface, camera: pygame.Vector2) -> None:
        p = self.pos - camera
        color = WHITE if self.flash > 0 else self.color
        pygame.draw.circle(surf, (0, 0, 0), p + pygame.Vector2(4, 6), self.radius)
        pygame.draw.circle(surf, color, p, self.radius)
        if self.portrait:
            rect = self.portrait.get_rect(center=(int(p.x), int(p.y - self.radius - 30)))
            surf.blit(self.portrait, rect)
        tip = p + self.facing * (self.radius + 18)
        pygame.draw.line(surf, BLACK, p, tip, 4)
        if self.parry_timer > 0:
            pygame.draw.circle(surf, CYAN, p, self.radius + 12, 3)
        if self.attack:
            attack = self.attack
            phase = self.attack_phase()
            if phase == "windup":
                ring = RED if attack.red_flash else GOLD
                pygame.draw.circle(surf, ring, p, int(self.radius + 10 + 12 * math.sin(self.attack_timer * 40)), 3)
            elif phase == "active":
                end = p + self.facing * attack.reach
                pygame.draw.line(surf, RED, p, end, 9)


class Player(Fighter):
    def __init__(self, portrait: pygame.Surface) -> None:
        super().__init__("Hero", (460, 1280), 22, 110, 100, (210, 215, 220), portrait)
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.kills = 0

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper, mouse_world: pygame.Vector2, walls: list[pygame.Rect]) -> None:
        self.update_timers(dt)
        self.dash_timer = max(0, self.dash_timer - dt)
        self.dash_cooldown = max(0, self.dash_cooldown - dt)
        self.facing = safe_normalize(mouse_world - self.pos)
        if self.stagger > 0 or self.attack:
            return
        move = pygame.Vector2(
            (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0),
            (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0),
        )
        if move.length_squared() > 0:
            move = move.normalize()
        speed = 245 if self.dash_timer <= 0 else 620
        self.try_move(move * speed * dt, walls)

    def try_move(self, delta: pygame.Vector2, walls: list[pygame.Rect]) -> None:
        old = self.pos.copy()
        self.pos.x += delta.x
        if self.collides(walls):
            self.pos.x = old.x
        self.pos.y += delta.y
        if self.collides(walls):
            self.pos.y = old.y

    def collides(self, walls: list[pygame.Rect]) -> bool:
        point = pygame.Rect(int(self.pos.x - self.radius), int(self.pos.y - self.radius), self.radius * 2, self.radius * 2)
        return any(point.colliderect(w) for w in walls)

    def dash(self) -> None:
        if self.dash_cooldown <= 0 and self.stagger <= 0:
            self.dash_timer = 0.16
            self.dash_cooldown = 0.72
            self.invuln = 0.14


class Enemy(Fighter):
    def __init__(
        self,
        name: str,
        pos: tuple[float, float],
        hp: int,
        posture: int,
        color: tuple[int, int, int],
        portrait: pygame.Surface | None,
        boss: bool = False,
    ) -> None:
        super().__init__(name, pos, 25 if boss else 17, hp, posture, color, portrait)
        self.boss = boss
        self.ai_timer = random.uniform(0.3, 1.0)
        self.phase = 1
        self.speed = 120 if boss else 160

    def update(self, dt: float, player: Player, walls: list[pygame.Rect]) -> None:
        self.update_timers(dt)
        if not self.alive or self.stagger > 0:
            return
        to_player = player.pos - self.pos
        dist = max(1, to_player.length())
        self.facing = to_player / dist
        if self.hp < self.max_hp * 0.62:
            self.phase = 2
        if self.hp < self.max_hp * 0.32:
            self.phase = 3
        if self.attack:
            return

        self.ai_timer -= dt
        desired = 98 if self.boss else 70
        if dist > desired:
            self.try_move(self.facing * self.speed * dt, walls)
        elif dist < desired * 0.65:
            self.try_move(-self.facing * self.speed * 0.75 * dt, walls)

        if self.ai_timer <= 0:
            self.ai_timer = random.uniform(0.6, 1.2) / self.phase
            if dist < (150 if self.boss else 92):
                self.start_attack(self.choose_attack(), self.facing)

    def choose_attack(self) -> Attack:
        if not self.boss:
            return random.choice(
                [
                    Attack(0.34, 0.11, 0.36, 68, 0.8, 8, 14),
                    Attack(0.56, 0.13, 0.44, 78, 0.9, 14, 22, True),
                ]
            )
        pool = [
            Attack(0.42, 0.12, 0.38, 92, 0.75, 14, 18),
            Attack(0.58, 0.13, 0.48, 116, 0.68, 23, 30, True),
        ]
        if self.phase >= 2:
            pool.append(Attack(0.28, 0.10, 0.30, 88, 0.9, 11, 16))
        if self.phase >= 3:
            pool.append(Attack(0.72, 0.16, 0.52, 138, 0.55, 34, 45, True))
        return random.choice(pool)

    def try_move(self, delta: pygame.Vector2, walls: list[pygame.Rect]) -> None:
        old = self.pos.copy()
        self.pos.x += delta.x
        if self.collides(walls):
            self.pos.x = old.x
        self.pos.y += delta.y
        if self.collides(walls):
            self.pos.y = old.y

    def collides(self, walls: list[pygame.Rect]) -> bool:
        box = pygame.Rect(int(self.pos.x - self.radius), int(self.pos.y - self.radius), self.radius * 2, self.radius * 2)
        return any(box.colliderect(w) for w in walls)


class Game:
    def __init__(self) -> None:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Hard Parry Game")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)
        self.big_font = pygame.font.SysFont("consolas", 54, bold=True)
        self.assets = {
            "hero": load_image("hero.jpg", (46, 56)),
            "ma": load_image("boss_ma.jpg", (58, 58)),
            "cat": load_image("boss_cat.jpg", (58, 58)),
            "wolf": load_image("boss_wolf.webp", (58, 58)),
        }
        self.music = make_random_music()
        if self.music:
            self.music.set_volume(0.32)
            self.music.play(loops=-1)
        self.restart()

    def restart(self) -> None:
        self.player = Player(self.assets["hero"])
        self.camera = pygame.Vector2()
        self.world = pygame.Rect(0, 0, 2200, 1800)
        self.walls = [
            pygame.Rect(250, 300, 520, 90),
            pygame.Rect(1000, 240, 90, 520),
            pygame.Rect(1390, 910, 560, 90),
            pygame.Rect(430, 930, 300, 120),
            pygame.Rect(820, 1360, 650, 80),
            pygame.Rect(1760, 380, 90, 360),
        ]
        self.bosses = [
            Enemy("Boss Ma", (520, 420), 150, 110, (132, 88, 62), self.assets["ma"], True),
            Enemy("Chair Cat", (1730, 520), 170, 120, (204, 145, 65), self.assets["cat"], True),
            Enemy("Wolf King", (1570, 1270), 210, 145, (52, 55, 58), self.assets["wolf"], True),
        ]
        self.enemies: list[Enemy] = []
        self.spawn_timer = 1.5
        self.message = "Deflect, break posture, survive."
        self.message_timer = 4.0
        self.game_over = False
        self.victory = False

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r and (self.game_over or self.victory):
                    self.restart()
                if event.key == pygame.K_f:
                    self.player.start_parry()
                if event.key == pygame.K_SPACE:
                    self.player.dash()
            if event.type == pygame.MOUSEBUTTONDOWN and not (self.game_over or self.victory):
                mouse = pygame.mouse.get_pressed()
                mouse_world = pygame.Vector2(pygame.mouse.get_pos()) + self.camera
                if mouse[0]:
                    self.player.start_attack(Attack(0.16, 0.10, 0.26, 82, 0.86, 13, 20), mouse_world - self.player.pos)
                if mouse[2]:
                    self.player.start_parry()

    def update(self, dt: float) -> None:
        if self.game_over or self.victory:
            return
        keys = pygame.key.get_pressed()
        mouse_world = pygame.Vector2(pygame.mouse.get_pos()) + self.camera
        self.player.update(dt, keys, mouse_world, self.walls)
        self.player.pos.x = clamp(self.player.pos.x, 40, self.world.width - 40)
        self.player.pos.y = clamp(self.player.pos.y, 40, self.world.height - 40)
        active_enemies = [e for e in self.bosses + self.enemies if e.alive]
        for enemy in active_enemies:
            enemy.update(dt, self.player, self.walls)
        self.resolve_attacks(active_enemies)
        self.cleanup_and_spawn(dt)
        self.camera.x = clamp(self.player.pos.x - WIDTH / 2, 0, self.world.width - WIDTH)
        self.camera.y = clamp(self.player.pos.y - HEIGHT / 2, 0, self.world.height - HEIGHT)
        self.message_timer = max(0, self.message_timer - dt)
        if not self.player.alive:
            self.game_over = True
        if all(not b.alive for b in self.bosses):
            self.victory = True

    def resolve_attacks(self, enemies: list[Enemy]) -> None:
        if self.player.attack and self.player.attack_phase() == "active" and not self.player.hit_done:
            for enemy in enemies:
                if self.in_attack_cone(self.player, enemy):
                    enemy.take_damage(self.player.attack.damage, self.player.attack.posture, self.player.facing * 18)
                    if enemy.posture >= enemy.posture_max:
                        enemy.take_damage(34 if enemy.boss else 999, -enemy.posture_max)
                        enemy.stagger = 1.0
                        self.flash_message(f"Execution: {enemy.name}")
                    self.player.hit_done = True
                    break

        for enemy in enemies:
            if enemy.attack and enemy.attack_phase() == "active" and not enemy.hit_done:
                if self.in_attack_cone(enemy, self.player):
                    if self.player.parry_timer > 0:
                        enemy.posture = clamp(enemy.posture + enemy.attack.posture * 1.75, 0, enemy.posture_max)
                        enemy.stagger = 0.45 if not enemy.boss else 0.32
                        enemy.hit_done = True
                        self.player.posture = max(0, self.player.posture - 12)
                        self.flash_message("Perfect deflect!")
                    else:
                        self.player.take_damage(enemy.attack.damage, enemy.attack.posture, enemy.facing * 22)
                        enemy.hit_done = True

    def in_attack_cone(self, attacker: Fighter, target: Fighter) -> bool:
        if not attacker.attack:
            return False
        delta = target.pos - attacker.pos
        dist = delta.length()
        if dist > attacker.attack.reach + target.radius:
            return False
        direction = safe_normalize(delta)
        dot = clamp(attacker.facing.dot(direction), -1, 1)
        angle = math.acos(dot)
        return angle < attacker.attack.arc

    def cleanup_and_spawn(self, dt: float) -> None:
        before = len(self.enemies)
        self.enemies = [e for e in self.enemies if e.alive]
        self.player.kills += before - len(self.enemies)
        live_bosses = sum(1 for b in self.bosses if b.alive)
        max_mobs = 3 + live_bosses
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len(self.enemies) < max_mobs:
            self.spawn_timer = random.uniform(1.7, 3.2)
            pos = random.choice([(290, 580), (1170, 390), (1890, 1080), (680, 1500), (1840, 250)])
            self.enemies.append(Enemy("Ash Guard", pos, 36, 55, (126, 126, 118), None))

    def flash_message(self, text: str) -> None:
        self.message = text
        self.message_timer = 1.2

    def draw(self) -> None:
        self.screen.fill((30, 34, 31))
        self.draw_map()
        for enemy in self.enemies + self.bosses:
            if enemy.alive:
                enemy.draw(self.screen, self.camera)
        if self.player.alive:
            self.player.draw(self.screen, self.camera)
        self.draw_ui()
        pygame.display.flip()

    def draw_map(self) -> None:
        offset = -self.camera
        tile = 80
        for x in range(0, self.world.width, tile):
            for y in range(0, self.world.height, tile):
                rect = pygame.Rect(x + offset.x, y + offset.y, tile - 2, tile - 2)
                c = (42, 47, 42) if (x // tile + y // tile) % 2 == 0 else (36, 41, 37)
                pygame.draw.rect(self.screen, c, rect)
        for wall in self.walls:
            pygame.draw.rect(self.screen, STONE, wall.move(offset))
            pygame.draw.rect(self.screen, (40, 39, 35), wall.move(offset), 3)
        for shrine in [(455, 1255), (1565, 330), (1780, 1310)]:
            p = pygame.Vector2(shrine) + offset
            pygame.draw.circle(self.screen, GOLD, p, 16)
            pygame.draw.circle(self.screen, BLACK, p, 16, 2)

    def draw_ui(self) -> None:
        self.bar(24, 22, 340, 18, self.player.hp / self.player.max_hp, RED, "HP")
        self.bar(24, 48, 340, 14, 1 - self.player.posture / self.player.posture_max, CYAN, "POSTURE")
        cd = 1 - self.player.parry_cooldown / 0.48
        self.bar(24, 70, 190, 10, cd, GOLD, "PARRY")
        y = 104
        for boss in self.bosses:
            if boss.alive:
                self.bar(24, y, 285, 12, boss.hp / boss.max_hp, (180, 48, 48), boss.name)
                self.bar(24, y + 16, 285, 8, boss.posture / boss.posture_max, GOLD, "break")
                y += 36
        if self.message_timer > 0:
            text = self.font.render(self.message, True, WHITE)
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2, 34)))
        hint = self.font.render("WASD move | LMB attack | RMB/F parry | Space dash | R restart", True, (190, 195, 190))
        self.screen.blit(hint, (WIDTH - hint.get_width() - 24, HEIGHT - 34))
        if self.game_over or self.victory:
            title = "VICTORY" if self.victory else "DEATH"
            subtitle = "Press R to challenge again"
            t = self.big_font.render(title, True, GOLD if self.victory else RED)
            s = self.font.render(subtitle, True, WHITE)
            self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 34)))
            self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 28)))

    def bar(self, x: int, y: int, w: int, h: int, ratio: float, color: tuple[int, int, int], label: str) -> None:
        ratio = clamp(ratio, 0, 1)
        pygame.draw.rect(self.screen, BLACK, (x - 2, y - 2, w + 4, h + 4))
        pygame.draw.rect(self.screen, GREY, (x, y, w, h))
        pygame.draw.rect(self.screen, color, (x, y, int(w * ratio), h))
        text = self.font.render(label, True, WHITE)
        self.screen.blit(text, (x + w + 10, y - 4))


if __name__ == "__main__":
    Game().run()
