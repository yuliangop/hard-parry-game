from __future__ import annotations

import math
import random
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from ursina import (
    Audio,
    Button,
    DirectionalLight,
    Entity,
    Sky,
    Text,
    Ursina,
    Vec2,
    Vec3,
    application,
    camera,
    color,
    destroy,
    held_keys,
    invoke,
    load_texture,
    mouse,
    scene,
    time,
    window,
)


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MUSIC_FILE = ASSETS / "procedural_3d_theme.wav"
SAMPLE_RATE = 22050
application.asset_folder = ROOT


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def flat(v: Vec3) -> Vec3:
    return Vec3(v.x, 0, v.z)


def length_xz(a: Vec3, b: Vec3) -> float:
    d = a - b
    return math.sqrt(d.x * d.x + d.z * d.z)


def normalized_xz(v: Vec3) -> Vec3:
    d = math.sqrt(v.x * v.x + v.z * v.z)
    if d <= 0.001:
        return Vec3(0, 0, 1)
    return Vec3(v.x / d, 0, v.z / d)


def yaw_to_dir(yaw: float) -> Vec3:
    r = math.radians(yaw)
    return Vec3(math.sin(r), 0, math.cos(r))


def dir_to_yaw(v: Vec3) -> float:
    return math.degrees(math.atan2(v.x, v.z))


def generate_music(path: Path) -> None:
    rng = random.Random()
    root = rng.choice([49.0, 55.0, 61.74, 65.41])
    scale = rng.choice([[0, 2, 3, 7, 8, 10], [0, 1, 5, 7, 8, 11], [0, 3, 5, 6, 7, 10]])
    tempo = rng.choice([88, 96, 108])
    beat = 60 / tempo
    bars = 20
    seconds = bars * beat * 4
    count = int(seconds * SAMPLE_RATE)
    samples = array("h", [0]) * count

    def add(start: float, duration: float, freq: float, volume: float, wave_name: str) -> None:
        start_i = int(start * SAMPLE_RATE)
        end_i = min(count, int((start + duration) * SAMPLE_RATE))
        fade = max(1, int(0.03 * SAMPLE_RATE))
        for i in range(start_i, end_i):
            t = (i - start_i) / SAMPLE_RATE
            env = min(1, (i - start_i) / fade, (end_i - i) / fade)
            if wave_name == "saw":
                raw = 2 * ((freq * t) % 1) - 1
            elif wave_name == "pulse":
                raw = 1 if math.sin(freq * t * math.tau) > 0.35 else -0.65
            else:
                raw = math.sin(freq * t * math.tau)
            samples[i] = int(clamp(samples[i] + raw * volume * env * 32767, -32767, 32767))

    for bar in range(bars):
        base = bar * beat * 4
        degree = random.choice(scale)
        bass = root * (2 ** (degree / 12))
        add(base, beat * 3.8, bass, 0.18, "saw")
        add(base + beat * 2, beat * 1.7, bass * 0.5, 0.15, "sine")
        for step in range(8):
            if rng.random() < 0.55:
                note = root * 2 * (2 ** (rng.choice(scale) / 12))
                add(base + step * beat / 2, beat * 0.28, note, 0.075, "pulse")
        for hit in (0, 3, 4, 7):
            add(base + hit * beat / 2, 0.045, rng.choice([73, 82, 98]), 0.20, "sine")

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(samples.tobytes())


@dataclass
class Strike:
    windup: float
    active: float
    recover: float
    reach: float
    damage: int
    posture: int
    perilous: bool = False

    @property
    def total(self) -> float:
        return self.windup + self.active + self.recover


class CharacterModel(Entity):
    def __init__(self, name: str, palette: dict[str, color.Color], portrait: str | None, beast: bool = False) -> None:
        super().__init__()
        self.name = name
        self.palette = palette
        self.beast = beast
        self.parts: list[Entity] = []
        if beast:
            self._beast()
        else:
            self._humanoid()
        self.intent_ring = Entity(parent=self, model="cube", color=color.rgba(255, 60, 50, 0), scale=(1.25, 0.025, 1.25), y=0.035)
        if portrait:
            self.portrait = Entity(parent=self, model="quad", texture=load_texture(portrait, folder=ASSETS), scale=(0.72, 0.72), y=2.45, z=-0.05, billboard=True)

    def cube(self, scale: tuple[float, float, float], pos: tuple[float, float, float], c: color.Color) -> Entity:
        e = Entity(parent=self, model="cube", color=c, scale=scale, position=pos)
        self.parts.append(e)
        return e

    def sphere(self, scale: tuple[float, float, float], pos: tuple[float, float, float], c: color.Color) -> Entity:
        e = Entity(parent=self, model="sphere", color=c, scale=scale, position=pos)
        self.parts.append(e)
        return e

    def _humanoid(self) -> None:
        body = self.palette["body"]
        cloth = self.palette["cloth"]
        skin = self.palette["skin"]
        metal = self.palette["metal"]
        self.cube((0.55, 0.95, 0.32), (0, 1.05, 0), body)
        self.sphere((0.38, 0.42, 0.35), (0, 1.78, 0), skin)
        self.cube((0.16, 0.72, 0.16), (-0.42, 1.06, 0), cloth)
        self.cube((0.16, 0.72, 0.16), (0.42, 1.06, 0), cloth)
        self.cube((0.19, 0.82, 0.18), (-0.18, 0.38, 0), cloth)
        self.cube((0.19, 0.82, 0.18), (0.18, 0.38, 0), cloth)
        self.cube((0.08, 1.35, 0.08), (0.66, 1.13, 0.18), metal).rotation_z = 18
        self.cube((0.55, 0.08, 0.08), (0, 1.42, -0.2), color.rgb(30, 30, 30))

    def _beast(self) -> None:
        body = self.palette["body"]
        accent = self.palette["cloth"]
        self.sphere((0.72, 0.46, 0.45), (0, 0.72, 0), body)
        self.sphere((0.42, 0.34, 0.36), (0, 1.2, 0.5), body)
        self.cube((0.12, 0.42, 0.10), (-0.22, 1.52, 0.48), accent).rotation_z = -18
        self.cube((0.12, 0.42, 0.10), (0.22, 1.52, 0.48), accent).rotation_z = 18
        for x in (-0.34, 0.34):
            for z in (-0.22, 0.28):
                self.cube((0.16, 0.54, 0.16), (x, 0.3, z), body)
        self.cube((0.14, 0.14, 0.72), (0, 0.86, -0.62), accent).rotation_x = -25

    def set_attack_flash(self, amount: float, perilous: bool) -> None:
        if amount <= 0:
            self.intent_ring.color = color.rgba(255, 60, 50, 0)
            return
        self.intent_ring.color = color.rgba(255, 40, 30, int(120 + 100 * amount)) if perilous else color.rgba(255, 196, 60, int(85 + 90 * amount))
        self.intent_ring.scale = (1.15 + amount * 0.35, 0.025, 1.15 + amount * 0.35)


class Fighter:
    def __init__(self, name: str, pos: Vec3, hp: int, posture_max: int, model: CharacterModel, boss: bool = False) -> None:
        self.name = name
        self.entity = model
        self.entity.position = pos
        self.hp = hp
        self.max_hp = hp
        self.posture = 0.0
        self.posture_max = posture_max
        self.boss = boss
        self.alive = True
        self.radius = 0.62 if boss else 0.46
        self.speed = 3.0 if boss else 3.8
        self.facing = Vec3(0, 0, 1)
        self.attack: Strike | None = None
        self.attack_t = 0.0
        self.hit_done = False
        self.cooldown = 0.0
        self.parry = 0.0
        self.parry_cd = 0.0
        self.dash_cd = 0.0
        self.stagger = 0.0
        self.intent = "watching"
        self.phase = 1

    @property
    def pos(self) -> Vec3:
        return self.entity.position

    @pos.setter
    def pos(self, value: Vec3) -> None:
        self.entity.position = value

    def start_attack(self, strike: Strike, direction: Vec3) -> bool:
        if self.attack or self.cooldown > 0 or self.stagger > 0 or not self.alive:
            return False
        self.attack = strike
        self.attack_t = 0
        self.hit_done = False
        self.cooldown = strike.total + 0.05
        self.face(direction)
        self.intent = "perilous strike" if strike.perilous else "slash"
        return True

    def face(self, direction: Vec3) -> None:
        self.facing = normalized_xz(direction)
        self.entity.rotation_y = dir_to_yaw(self.facing)

    def phase_name(self) -> str:
        if not self.attack:
            return "idle"
        if self.attack_t < self.attack.windup:
            return "windup"
        if self.attack_t < self.attack.windup + self.attack.active:
            return "active"
        return "recover"

    def tick(self, dt: float) -> None:
        self.cooldown = max(0, self.cooldown - dt)
        self.parry = max(0, self.parry - dt)
        self.parry_cd = max(0, self.parry_cd - dt)
        self.dash_cd = max(0, self.dash_cd - dt)
        self.stagger = max(0, self.stagger - dt)
        self.posture = max(0, self.posture - dt * (5 if self.boss else 10))
        if self.attack:
            self.attack_t += dt
            phase = self.phase_name()
            amount = 1 if phase == "active" else clamp(self.attack_t / max(0.01, self.attack.windup), 0, 1)
            self.entity.set_attack_flash(amount, self.attack.perilous)
            if self.attack_t >= self.attack.total:
                self.attack = None
                self.entity.set_attack_flash(0, False)
                self.intent = "recovering"
        else:
            self.entity.set_attack_flash(0, False)

    def damage(self, hp: int, posture: int, knock: Vec3 = Vec3(0, 0, 0)) -> None:
        self.hp -= hp
        self.posture = clamp(self.posture + posture, 0, self.posture_max)
        self.pos += knock
        self.entity.blink(color.white, duration=0.08)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            self.intent = "dead"
            self.entity.animate_scale(Vec3(1, 0.08, 1), duration=0.22)
            invoke(destroy, self.entity, delay=1.0)


class World:
    def __init__(self) -> None:
        self.walls: list[tuple[float, float, float, float]] = []
        self._build()

    def _block(self, x: float, z: float, sx: float, sz: float, h: float = 1.0) -> None:
        Entity(model="cube", color=color.rgb(92, 86, 75), position=(x, h / 2, z), scale=(sx, h, sz), collider="box")
        self.walls.append((x, z, sx / 2, sz / 2))

    def _build(self) -> None:
        Entity(model="plane", scale=(36, 1, 30), color=color.rgb(42, 50, 45), texture="white_cube", texture_scale=(18, 15), collider="box")
        for x in range(-16, 17, 4):
            Entity(model="cube", color=color.rgba(255, 255, 255, 18), position=(x, 0.011, -15), scale=(0.05, 0.02, 30))
        for z in range(-14, 15, 4):
            Entity(model="cube", color=color.rgba(255, 255, 255, 18), position=(-18, 0.012, z), scale=(36, 0.02, 0.05))
        self._block(-6, -4, 7, 0.7, 1.2)
        self._block(3.5, -5.5, 0.8, 7, 1.4)
        self._block(8, 4.5, 7, 0.8, 1.2)
        self._block(-8.5, 6, 4.5, 1, 1.4)
        self._block(12, -3, 1, 5, 1.1)
        for p in [(-11, -9), (0, 8), (12, 9)]:
            Entity(model="cube", color=color.gold, position=(p[0], 0.6, p[1]), scale=(0.7, 0.9, 0.7), collider="box")

    def blocked(self, p: Vec3, radius: float) -> bool:
        if p.x < -17 + radius or p.x > 17 - radius or p.z < -14 + radius or p.z > 14 - radius:
            return True
        for x, z, hx, hz in self.walls:
            if abs(p.x - x) < hx + radius and abs(p.z - z) < hz + radius:
                return True
        return False


class Game3D:
    def __init__(self) -> None:
        window.title = "Hard Parry Game 3D"
        window.borderless = False
        window.color = color.rgb(11, 13, 16)
        mouse.locked = True
        self.world = World()
        DirectionalLight(rotation=(45, -35, 45), color=color.rgb(245, 232, 210))
        Entity(model="sphere", color=color.rgba(120, 150, 180, 70), position=(0, 22, 0), scale=40)
        Sky(color=color.rgb(11, 15, 19))
        self.camera_yaw = 0.0
        self.camera_pitch = 18.0
        self.message_t = 0.0
        self.message = ""
        self.spawn_t = 2.0
        self.victory = False
        self.dead = False
        self.music = None
        self.player = self._make_player()
        self.bosses = self._make_bosses()
        self.mobs: list[Fighter] = []
        self.ui = self._make_ui()
        self._start_music()

    def _make_player(self) -> Fighter:
        model = CharacterModel(
            "hero",
            {"body": color.rgb(210, 215, 220), "cloth": color.rgb(62, 92, 120), "skin": color.rgb(202, 160, 126), "metal": color.azure},
            "hero.jpg",
        )
        return Fighter("Hero", Vec3(-10, 0, -9), 135, 110, model)

    def _make_bosses(self) -> list[Fighter]:
        return [
            Fighter("Master Ma", Vec3(-9, 0, 8), 190, 135, CharacterModel("ma", {"body": color.rgb(52, 43, 36), "cloth": color.gold, "skin": color.rgb(188, 126, 88), "metal": color.white}, "boss_ma.jpg"), True),
            Fighter("Chair Cat", Vec3(11, 0, -7), 210, 145, CharacterModel("cat", {"body": color.rgb(220, 146, 58), "cloth": color.rgb(245, 205, 92), "skin": color.rgb(220, 146, 58), "metal": color.white}, "boss_cat.jpg", beast=True), True),
            Fighter("Wolf King", Vec3(10, 0, 9), 250, 165, CharacterModel("wolf", {"body": color.rgb(35, 37, 39), "cloth": color.rgb(240, 112, 43), "skin": color.rgb(35, 37, 39), "metal": color.white}, "boss_wolf.png", beast=True), True),
        ]

    def _make_mob(self) -> Fighter:
        pos = random.choice([Vec3(-14, 0, 0), Vec3(0, 0, -12), Vec3(15, 0, 2), Vec3(-2, 0, 12)])
        model = CharacterModel("ash_guard", {"body": color.rgb(105, 107, 101), "cloth": color.rgb(75, 78, 76), "skin": color.rgb(160, 130, 105), "metal": color.rgb(180, 186, 185)}, None)
        return Fighter("Ash Guard", pos, 48, 55, model)

    def _make_ui(self) -> dict[str, object]:
        ui = {
            "hp": Button(parent=camera.ui, model="quad", color=color.rgb(150, 30, 35), origin=(-0.5, 0), position=(-0.86, 0.45), scale=(0.42, 0.025), disabled=True),
            "posture": Button(parent=camera.ui, model="quad", color=color.azure, origin=(-0.5, 0), position=(-0.86, 0.405), scale=(0.42, 0.018), disabled=True),
            "parry": Button(parent=camera.ui, model="quad", color=color.gold, origin=(-0.5, 0), position=(-0.86, 0.37), scale=(0.24, 0.012), disabled=True),
            "message": Text(parent=camera.ui, text="", origin=(0, 0), position=(0, 0.43), scale=1.25, color=color.white),
            "boss": Text(parent=camera.ui, text="", origin=(-0.5, 0.5), position=(-0.86, 0.31), scale=0.82, color=color.rgb(230, 226, 210)),
            "ai": Text(parent=camera.ui, text="", origin=(0.5, 0.5), position=(0.86, 0.42), scale=0.72, color=color.rgb(210, 230, 235)),
            "help": Text(parent=camera.ui, text="WASD move | Mouse camera | LMB attack | RMB/F parry | Space dash | R restart", origin=(0, 0), position=(0, -0.47), scale=0.72, color=color.rgb(190, 196, 188)),
            "end": Text(parent=camera.ui, text="", origin=(0, 0), position=(0, 0.02), scale=2.4, color=color.gold),
        }
        return ui

    def _start_music(self) -> None:
        generate_music(MUSIC_FILE)
        self.music = Audio(MUSIC_FILE, loop=True, autoplay=True, volume=0.35)

    def input(self, key: str) -> None:
        if key == "escape":
            mouse.locked = not mouse.locked
        if key in ("right mouse down", "f"):
            if self.player.parry_cd <= 0 and self.player.stagger <= 0:
                self.player.parry = 0.2
                self.player.parry_cd = 0.5
                self.flash("DEFLECT READY")
        if key == "left mouse down":
            self.player.start_attack(Strike(0.16, 0.11, 0.28, 1.45, 16, 24), self.player.facing)
        if key == "space" and self.player.dash_cd <= 0:
            self.player.dash_cd = 0.75
            self._try_move(self.player, self.player.facing * 2.2)
        if key == "r" and (self.dead or self.victory):
            self.restart()

    def restart(self) -> None:
        for f in self.bosses + self.mobs + [self.player]:
            if f.entity:
                destroy(f.entity)
        self.player = self._make_player()
        self.bosses = self._make_bosses()
        self.mobs = []
        self.dead = False
        self.victory = False
        self.flash("again")

    def flash(self, text: str, duration: float = 1.1) -> None:
        self.message = text
        self.message_t = duration

    def update(self) -> None:
        dt = time.dt
        if mouse.locked:
            self.camera_yaw += mouse.velocity[0] * 75
            self.camera_pitch = clamp(self.camera_pitch - mouse.velocity[1] * 55, 8, 42)
        if not self.dead and not self.victory:
            self._update_player(dt)
            self._update_ai(dt)
            self._resolve_hits()
            self._spawn(dt)
            self.dead = not self.player.alive
            self.victory = all(not b.alive for b in self.bosses)
        self._camera()
        self._ui()

    def _update_player(self, dt: float) -> None:
        self.player.tick(dt)
        forward = yaw_to_dir(self.camera_yaw)
        right = yaw_to_dir(self.camera_yaw + 90)
        move = Vec3(0, 0, 0)
        move += forward * (held_keys["w"] - held_keys["s"])
        move += right * (held_keys["d"] - held_keys["a"])
        if move.length() > 0 and not self.player.attack and self.player.stagger <= 0:
            move = move.normalized()
            self.player.face(move)
            self._try_move(self.player, move * self.player.speed * dt)

    def _update_ai(self, dt: float) -> None:
        living = [e for e in self.bosses + self.mobs if e.alive]
        for e in living:
            e.tick(dt)
            if e.hp < e.max_hp * 0.62:
                e.phase = 2
            if e.hp < e.max_hp * 0.30:
                e.phase = 3
            if e.attack or e.stagger > 0:
                continue
            delta = self.player.pos - e.pos
            dist = length_xz(self.player.pos, e.pos)
            e.face(delta)
            desired = 1.8 if e.boss else 1.25
            if dist > desired:
                e.intent = "closing distance"
                self._try_move(e, normalized_xz(delta) * e.speed * dt)
            elif dist < desired * 0.62:
                e.intent = "reset spacing"
                self._try_move(e, -normalized_xz(delta) * e.speed * 0.7 * dt)
            else:
                e.intent = "reading you"
            if dist < (2.65 if e.boss else 1.85) and random.random() < dt * (0.65 + e.phase * 0.45):
                e.start_attack(self._enemy_strike(e), delta)

    def _enemy_strike(self, e: Fighter) -> Strike:
        if not e.boss:
            return random.choice([Strike(0.36, 0.12, 0.40, 1.18, 12, 16), Strike(0.58, 0.12, 0.48, 1.35, 19, 26, True)])
        pool = [Strike(0.42, 0.13, 0.42, 1.65, 18, 22), Strike(0.64, 0.15, 0.52, 1.95, 28, 36, True)]
        if e.phase >= 2:
            pool.append(Strike(0.28, 0.10, 0.34, 1.55, 15, 20))
        if e.phase >= 3:
            pool.append(Strike(0.78, 0.18, 0.58, 2.25, 42, 52, True))
        return random.choice(pool)

    def _try_move(self, f: Fighter, delta: Vec3) -> None:
        old = Vec3(f.pos.x, f.pos.y, f.pos.z)
        f.pos += Vec3(delta.x, 0, 0)
        if self.world.blocked(f.pos, f.radius):
            f.pos = old
        old = Vec3(f.pos.x, f.pos.y, f.pos.z)
        f.pos += Vec3(0, 0, delta.z)
        if self.world.blocked(f.pos, f.radius):
            f.pos = old

    def _resolve_hits(self) -> None:
        all_enemies = [e for e in self.bosses + self.mobs if e.alive]
        if self.player.attack and self.player.phase_name() == "active" and not self.player.hit_done:
            for e in all_enemies:
                if self._in_range(self.player, e):
                    e.damage(self.player.attack.damage, self.player.attack.posture, self.player.facing * 0.35)
                    self.player.hit_done = True
                    if e.posture >= e.posture_max:
                        e.damage(45 if e.boss else 999, -999, self.player.facing * 0.75)
                        e.stagger = 1.1
                        self.flash(f"POSTURE BREAK: {e.name}")
                    break
        for e in all_enemies:
            if e.attack and e.phase_name() == "active" and not e.hit_done and self._in_range(e, self.player):
                if self.player.parry > 0:
                    e.posture = clamp(e.posture + e.attack.posture * 1.9, 0, e.posture_max)
                    e.stagger = 0.48 if not e.boss else 0.32
                    e.hit_done = True
                    self.player.posture = max(0, self.player.posture - 18)
                    self.flash("PERFECT DEFLECT")
                else:
                    self.player.damage(e.attack.damage, e.attack.posture, e.facing * 0.55)
                    e.hit_done = True

    def _in_range(self, attacker: Fighter, target: Fighter) -> bool:
        if not attacker.attack:
            return False
        delta = target.pos - attacker.pos
        dist = math.sqrt(delta.x * delta.x + delta.z * delta.z)
        if dist > attacker.attack.reach + target.radius:
            return False
        d = normalized_xz(delta)
        dot = clamp(attacker.facing.x * d.x + attacker.facing.z * d.z, -1, 1)
        return math.degrees(math.acos(dot)) < 58

    def _spawn(self, dt: float) -> None:
        self.mobs = [m for m in self.mobs if m.alive]
        self.spawn_t -= dt
        living_bosses = sum(1 for b in self.bosses if b.alive)
        if self.spawn_t <= 0 and len(self.mobs) < 2 + living_bosses:
            self.spawn_t = random.uniform(2.2, 3.8)
            self.mobs.append(self._make_mob())

    def _camera(self) -> None:
        back = yaw_to_dir(self.camera_yaw) * -7.2
        height = 3.3 + self.camera_pitch / 24
        camera.position = self.player.pos + back + Vec3(0, height, 0)
        camera.look_at(self.player.pos + Vec3(0, 1.25, 0))

    def _ui(self) -> None:
        hp = self.ui["hp"]
        posture = self.ui["posture"]
        parry = self.ui["parry"]
        hp.scale_x = 0.42 * self.player.hp / self.player.max_hp
        posture.scale_x = 0.42 * (1 - self.player.posture / self.player.posture_max)
        parry.scale_x = 0.24 * (1 - self.player.parry_cd / 0.5)
        living_bosses = [b for b in self.bosses if b.alive]
        boss_lines = []
        for b in living_bosses:
            boss_lines.append(f"{b.name:10} HP {b.hp:3}/{b.max_hp:<3}  posture {int(b.posture):3}/{b.posture_max}")
        self.ui["boss"].text = "\n".join(boss_lines)
        nearest = min([e for e in self.bosses + self.mobs if e.alive], key=lambda e: length_xz(e.pos, self.player.pos), default=None)
        if nearest:
            phase = nearest.phase_name().upper() if nearest.attack else nearest.intent
            self.ui["ai"].text = f"AI READOUT\nTarget: {nearest.name}\nIntent: {phase}\nPhase: {nearest.phase}\nDistance: {length_xz(nearest.pos, self.player.pos):.1f}m\nParry window: red/gold ring active"
        else:
            self.ui["ai"].text = "AI READOUT\nNo hostile target"
        if self.message_t > 0:
            self.message_t -= time.dt
            self.ui["message"].text = self.message
        else:
            self.ui["message"].text = ""
        self.ui["end"].text = "VICTORY - Press R" if self.victory else ("DEATH - Press R" if self.dead else "")


app = Ursina()
game = Game3D()


def input(key: str) -> None:
    game.input(key)


def update() -> None:
    game.update()


if __name__ == "__main__":
    app.run()
