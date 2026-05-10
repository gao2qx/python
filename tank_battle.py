"""
Tank Battle (坦克大战) - A classic NES-style tank game built with pygame.
"""
import pygame
import random
import math
from enum import Enum, IntEnum

# ============================================================
# Constants
# ============================================================
CELL_SIZE = 24
MAP_COLS = 26
MAP_ROWS = 26
PLAY_WIDTH = MAP_COLS * CELL_SIZE   # 624
PLAY_HEIGHT = MAP_ROWS * CELL_SIZE  # 624
PANEL_WIDTH = 176
SCREEN_WIDTH = PLAY_WIDTH + PANEL_WIDTH  # 800
SCREEN_HEIGHT = PLAY_HEIGHT              # 624
TANK_SIZE = 44
HALF_TANK = TANK_SIZE // 2
BULLET_SIZE = 6
FPS = 60

PLAYER_SPEED = 3.0
ENEMY_SPEEDS = [1.2, 2.2, 1.2, 1.0]  # basic, fast, power, armor
BULLET_SPEED = 6.0
SHOOT_COOLDOWN = 28
ENEMY_SHOOT_COOLDOWN = 90
SPAWN_FLASH_DURATION = 60
SHIELD_TIME = 150
MAX_PLAYER_BULLETS = 2
MAX_ENEMY_BULLETS = 1
MAX_ENEMIES_ON_SCREEN = 6
ENEMIES_PER_LEVEL = 20
PLAYER_LIVES = 3

SPAWN_INTERVAL = 120  # frames between enemy spawns

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (120, 120, 120)
DARK_GRAY = (80, 80, 80)
LIGHT_GRAY = (180, 180, 180)
BROWN = (160, 100, 40)
YELLOW = (255, 240, 0)
GOLD = (255, 200, 0)
SILVER = (192, 192, 192)
RED = (255, 50, 50)
ORANGE = (255, 165, 0)
GREEN = (80, 220, 80)
DARK_GREEN = (30, 130, 30)
CYAN = (0, 200, 255)
DARK_BG = (40, 40, 40)
PANEL_BG = (60, 60, 60)
STEEL_COLOR = (160, 160, 180)
STEEL_HIGHLIGHT = (200, 200, 220)


class Dir(IntEnum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3


DIR_VECTORS = {
    Dir.UP: (0, -1),
    Dir.DOWN: (0, 1),
    Dir.LEFT: (-1, 0),
    Dir.RIGHT: (1, 0),
}


class GameState(Enum):
    MENU = 0
    PLAYING = 1
    LEVEL_TRANSITION = 2
    GAME_OVER = 3
    VICTORY = 4


# ============================================================
# Map
# ============================================================
class Map:
    def __init__(self):
        self.grid = [[0] * MAP_COLS for _ in range(MAP_ROWS)]
        self.cell_rects = {}  # cache rects for rendering

    def load_level(self, level_data):
        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                self.grid[row][col] = int(level_data[row][col])

    def get_cell(self, row, col):
        if 0 <= row < MAP_ROWS and 0 <= col < MAP_COLS:
            return self.grid[row][col]
        return 2  # treat out-of-bounds as steel

    def set_cell(self, row, col, value):
        if 0 <= row < MAP_ROWS and 0 <= col < MAP_COLS:
            self.grid[row][col] = value

    def _cells_in_rect(self, rect):
        left = max(0, rect.left // CELL_SIZE)
        right = min(MAP_COLS - 1, max(0, (rect.right - 1) // CELL_SIZE))
        top = max(0, rect.top // CELL_SIZE)
        bottom = min(MAP_ROWS - 1, max(0, (rect.bottom - 1) // CELL_SIZE))
        return left, right, top, bottom

    def rect_collides_wall(self, rect):
        left, right, top, bottom = self._cells_in_rect(rect)
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if self.grid[row][col] > 0:
                    return True
        return False

    def bullet_hits_wall(self, rect):
        left, right, top, bottom = self._cells_in_rect(rect)
        hits = []
        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if self.grid[row][col] > 0:
                    hits.append((row, col))
        return hits

    def render(self, surface):
        sx = CELL_SIZE
        for row in range(MAP_ROWS):
            for col in range(MAP_COLS):
                v = self.grid[row][col]
                if v == 0:
                    continue
                x, y = col * CELL_SIZE, row * CELL_SIZE
                if v == 1:  # brick
                    pygame.draw.rect(surface, BROWN, (x, y, CELL_SIZE, CELL_SIZE))
                    # brick pattern
                    mid = CELL_SIZE // 2
                    pygame.draw.line(surface, (120, 70, 20), (x, y + mid), (x + CELL_SIZE, y + mid), 1)
                    pygame.draw.line(surface, (120, 70, 20), (x + mid, y), (x + mid, y + mid), 1)
                    pygame.draw.line(surface, (120, 70, 20), (x, y + mid), (x + mid, y + mid), 1)
                elif v == 2:  # steel
                    pygame.draw.rect(surface, STEEL_COLOR, (x, y, CELL_SIZE, CELL_SIZE))
                    # steel highlight
                    pygame.draw.rect(surface, STEEL_HIGHLIGHT, (x + 2, y + 2, 8, 8))
                    pygame.draw.rect(surface, STEEL_HIGHLIGHT, (x + 14, y + 2, 8, 8))
                    pygame.draw.rect(surface, STEEL_HIGHLIGHT, (x + 2, y + 14, 8, 8))
                    pygame.draw.rect(surface, STEEL_HIGHLIGHT, (x + 14, y + 14, 8, 8))


# ============================================================
# Tank surface cache
# ============================================================
def create_tank_surface(body_color, tread_color, barrel_color):
    """Create 4 directional surfaces for a tank."""
    size = TANK_SIZE
    half = TANK_SIZE // 2
    eighth = TANK_SIZE // 8
    surfaces = {}
    for d in Dir:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        # Body
        pygame.draw.rect(surf, body_color, (eighth, eighth, size - 2 * eighth, size - 2 * eighth))
        # Treads (perpendicular to movement)
        if d in (Dir.UP, Dir.DOWN):
            pygame.draw.rect(surf, tread_color, (0, 0, eighth + 2, size))
            pygame.draw.rect(surf, tread_color, (size - eighth - 2, 0, eighth + 2, size))
            # tread lines
            for i in range(0, size, 6):
                pygame.draw.line(surf, DARK_GRAY, (0, i), (eighth, i), 1)
                pygame.draw.line(surf, DARK_GRAY, (size - eighth - 2, i), (size, i), 1)
        else:
            pygame.draw.rect(surf, tread_color, (0, 0, size, eighth + 2))
            pygame.draw.rect(surf, tread_color, (0, size - eighth - 2, size, eighth + 2))
            for i in range(0, size, 6):
                pygame.draw.line(surf, DARK_GRAY, (i, 0), (i, eighth), 1)
                pygame.draw.line(surf, DARK_GRAY, (i, size - eighth - 2), (i, size), 1)
        # Turret cap
        pygame.draw.circle(surf, body_color, (half, half), eighth + 2)
        pygame.draw.circle(surf, tread_color, (half, half), eighth)
        # Barrel
        bx, by = DIR_VECTORS[d]
        end_x = half + bx * (half + 2)
        end_y = half + by * (half + 2)
        pygame.draw.line(surf, barrel_color, (half, half), (end_x, end_y), 5)
        # Rotate the surface to match direction
        angle = {Dir.UP: 0, Dir.RIGHT: -90, Dir.DOWN: 180, Dir.LEFT: 90}[d]
        rotated = pygame.transform.rotate(surf, angle)
        surfaces[d] = rotated
    return surfaces


# ============================================================
# Tank base class
# ============================================================
class Tank:
    def __init__(self, x, y, direction, speed, body_color, tread_color, barrel_color):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.speed = speed
        self.alive = True
        self.frozen = False  # during spawn flash, can't move or shoot
        self.surfaces = create_tank_surface(body_color, tread_color, barrel_color)
        self.rect = pygame.Rect(0, 0, TANK_SIZE, TANK_SIZE)
        self._update_rect()

    def _update_rect(self):
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)

    def get_barrel_tip(self):
        bx, by = DIR_VECTORS[self.direction]
        return self.x + bx * (HALF_TANK + 6), self.y + by * (HALF_TANK + 6)

    def collides_tank(self, other):
        return self.rect.colliderect(other.rect)

    def move(self, dx, dy, game_map, all_tanks):
        if not self.alive or self.frozen:
            return
        old_x, old_y = self.x, self.y

        # Try X movement
        test_rect = pygame.Rect(0, 0, TANK_SIZE, TANK_SIZE)
        test_rect.centerx = int(self.x + dx)
        test_rect.centery = int(self.y)
        if (not game_map.rect_collides_wall(test_rect)
                and self._in_bounds(test_rect)
                and not self._collides_any_tank(test_rect, all_tanks)):
            self.x += dx

        # Try Y movement
        test_rect.centerx = int(self.x)
        test_rect.centery = int(self.y + dy)
        if (not game_map.rect_collides_wall(test_rect)
                and self._in_bounds(test_rect)
                and not self._collides_any_tank(test_rect, all_tanks)):
            self.y += dy

        self._update_rect()

    def _in_bounds(self, rect):
        return (0 <= rect.left and rect.right <= PLAY_WIDTH
                and 0 <= rect.top and rect.bottom <= PLAY_HEIGHT)

    def _collides_any_tank(self, rect, all_tanks):
        for t in all_tanks:
            if t is not self and t.alive and rect.colliderect(t.rect):
                return True
        return False

    def render(self, surface):
        if not self.alive:
            return
        surf = self.surfaces[self.direction]
        rect = surf.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(surf, rect)


# ============================================================
# Player Tank
# ============================================================
class PlayerTank(Tank):
    def __init__(self, x, y):
        super().__init__(x, y, Dir.UP, PLAYER_SPEED, YELLOW, GOLD, CYAN)
        self.lives = PLAYER_LIVES
        self.shield_timer = SHIELD_TIME
        self.shoot_cooldown = 0
        self.spawn_x = x
        self.spawn_y = y

    def handle_input(self, keys):
        if not self.alive:
            return

        dx, dy = 0.0, 0.0
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.direction = Dir.UP
            dy = -self.speed
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.direction = Dir.DOWN
            dy = self.speed
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.direction = Dir.LEFT
            dx = -self.speed
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.direction = Dir.RIGHT
            dx = self.speed

        return dx, dy

    def wants_to_shoot(self, keys):
        return (keys[pygame.K_SPACE] or keys[pygame.K_j]) and self.shoot_cooldown <= 0

    def die(self):
        self.alive = False
        self.lives -= 1
        self.shield_timer = 60  # respawn delay before reappearing

    def respawn(self, game_map, all_tanks):
        if self.lives <= 0:
            return False
        self.x = self.spawn_x
        self.y = self.spawn_y
        self.direction = Dir.UP
        self.alive = True
        self.shield_timer = SHIELD_TIME
        self.shoot_cooldown = 0
        self._update_rect()
        # Ensure spawn point is clear (push nearby enemies away)
        for t in all_tanks:
            if t is not self and t.alive and self.rect.colliderect(t.rect):
                t.x += TANK_SIZE * 2
                t._update_rect()
        return True

    def update_timers(self):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        if self.shield_timer > 0:
            self.shield_timer -= 1

    def render(self, surface):
        if not self.alive:
            return
        super().render(surface)
        # Shield effect
        if self.shield_timer > 0 and self.shield_timer % 8 < 4:
            pygame.draw.circle(surface, CYAN, (int(self.x), int(self.y)),
                               HALF_TANK + 4, 3)


# ============================================================
# Enemy Tank
# ============================================================
ENEMY_CONFIGS = [
    {"name": "basic", "body": SILVER, "tread": LIGHT_GRAY, "barrel": WHITE,
     "speed": ENEMY_SPEEDS[0], "health": 1, "points": 100},
    {"name": "fast", "body": RED, "tread": (180, 30, 30), "barrel": WHITE,
     "speed": ENEMY_SPEEDS[1], "health": 1, "points": 200},
    {"name": "power", "body": ORANGE, "tread": (200, 120, 0), "barrel": WHITE,
     "speed": ENEMY_SPEEDS[2], "health": 1, "points": 300},
    {"name": "armor", "body": GREEN, "tread": DARK_GREEN, "barrel": WHITE,
     "speed": ENEMY_SPEEDS[3], "health": 4, "points": 400},
]


class EnemyTank(Tank):
    def __init__(self, x, y, enemy_type=0):
        cfg = ENEMY_CONFIGS[enemy_type]
        super().__init__(x, y, Dir.DOWN, cfg["speed"], cfg["body"], cfg["tread"], cfg["barrel"])
        self.enemy_type = enemy_type
        self.health = cfg["health"]
        self.max_health = cfg["health"]
        self.points_value = cfg["points"]
        self.flash_timer = SPAWN_FLASH_DURATION
        self.frozen = True
        self.ai_timer = random.randint(20, 80)
        self.shoot_cooldown = random.randint(30, ENEMY_SHOOT_COOLDOWN)
        self.stuck_timer = 0
        self.prev_pos = (x, y)

    def update_timers(self):
        if self.flash_timer > 0:
            self.flash_timer -= 1
            if self.flash_timer == 0:
                self.frozen = False
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

    def ai_decision(self, game_map, all_tanks, player):
        if not self.alive or self.frozen:
            return

        self.ai_timer -= 1

        # Check if stuck
        cur = (self.x, self.y)
        if abs(cur[0] - self.prev_pos[0]) < 0.5 and abs(cur[1] - self.prev_pos[1]) < 0.5:
            self.stuck_timer += 1
        else:
            self.stuck_timer = 0
        self.prev_pos = cur

        # Force direction change if stuck
        if self.stuck_timer > 40:
            self._pick_new_direction(game_map, all_tanks, force=True)
            self.stuck_timer = 0
            self.ai_timer = random.randint(15, 40)
            return

        if self.ai_timer <= 0:
            # 60% keep direction, 40% change
            if random.random() < 0.4 or self._is_blocked(self.direction, game_map, all_tanks):
                self._pick_new_direction(game_map, all_tanks)
            self.ai_timer = random.randint(20, 80)

    def _is_blocked(self, d, game_map, all_tanks):
        dx, dy = DIR_VECTORS[d]
        test_rect = pygame.Rect(0, 0, TANK_SIZE, TANK_SIZE)
        test_rect.centerx = int(self.x + dx * TANK_SIZE)
        test_rect.centery = int(self.y + dy * TANK_SIZE)
        return (game_map.rect_collides_wall(test_rect)
                or self._collides_any_tank(test_rect, all_tanks)
                or not self._in_bounds(test_rect))

    def _pick_new_direction(self, game_map, all_tanks, force=False):
        # Exclude reverse direction
        reverse = (self.direction + 2) % 4
        candidates = [d for d in Dir if d != reverse]
        valid = [d for d in candidates if not self._is_blocked(d, game_map, all_tanks)]
        if valid:
            self.direction = random.choice(valid)
        elif not self._is_blocked(reverse, game_map, all_tanks):
            self.direction = reverse

    def wants_to_shoot(self):
        if self.frozen or self.shoot_cooldown > 0:
            return False
        return random.random() < 0.3

    def take_damage(self):
        self.health -= 1
        if self.health <= 0:
            self.alive = False
            return True
        # Flash white to show damage
        return False

    def render(self, surface):
        if not self.alive:
            return
        # Flash during spawn
        if self.flash_timer > 0 and self.flash_timer % 8 < 4:
            return
        super().render(surface)
        # Health bar for armor type
        if self.max_health > 1 and self.health < self.max_health:
            bw = TANK_SIZE
            bh = 4
            bx = int(self.x - bw // 2)
            by = int(self.y - HALF_TANK - 8)
            pygame.draw.rect(surface, RED, (bx, by, bw, bh))
            pygame.draw.rect(surface, GREEN, (bx, by, int(bw * self.health / self.max_health), bh))


# ============================================================
# Bullet
# ============================================================
class Bullet:
    def __init__(self, x, y, direction, owner):
        self.x = float(x)
        self.y = float(y)
        self.direction = direction
        self.owner = owner  # 'player' or 'enemy'
        self.alive = True

    def update(self):
        dx, dy = DIR_VECTORS[self.direction]
        self.x += dx * BULLET_SPEED
        self.y += dy * BULLET_SPEED
        # Check bounds
        if (self.x < 0 or self.x > PLAY_WIDTH
                or self.y < 0 or self.y > PLAY_HEIGHT):
            self.alive = False

    @property
    def rect(self):
        h = BULLET_SIZE
        return pygame.Rect(int(self.x - h // 2), int(self.y - h // 2), h, h)

    def render(self, surface):
        if not self.alive:
            return
        r = self.rect
        pygame.draw.rect(surface, WHITE, r)
        pygame.draw.rect(surface, (255, 255, 200), r.inflate(-2, -2))


# ============================================================
# Base (Eagle)
# ============================================================
class Base:
    BASE_COL = 12
    BASE_ROW = 24
    BASE_SIZE = CELL_SIZE * 2  # 2x2 cells

    def __init__(self):
        self.x = (self.BASE_COL + 1) * CELL_SIZE  # center of 2x2
        self.y = (self.BASE_ROW + 1) * CELL_SIZE
        self.destroyed = False

    @property
    def rect(self):
        return pygame.Rect(self.BASE_COL * CELL_SIZE, self.BASE_ROW * CELL_SIZE,
                           self.BASE_SIZE, self.BASE_SIZE)

    def render(self, surface):
        if self.destroyed:
            # Draw ruined base
            pygame.draw.rect(surface, DARK_GRAY, self.rect)
            pygame.draw.rect(surface, (30, 30, 30), self.rect.inflate(-4, -4))
            return
        rx, ry = self.rect.topleft
        s = self.BASE_SIZE
        # Base platform
        pygame.draw.rect(surface, DARK_GRAY, self.rect)
        pygame.draw.rect(surface, GRAY, self.rect.inflate(-2, -2))
        # Eagle symbol
        cx, cy = rx + s // 2, ry + s // 2
        # Body
        pygame.draw.circle(surface, GOLD, (cx, cy), 12)
        # Head
        pygame.draw.circle(surface, GOLD, (cx, cy - 14), 6)
        # Beak (triangle)
        pts = [(cx, cy - 20), (cx + 8, cy - 14), (cx, cy - 8)]
        pygame.draw.polygon(surface, ORANGE, pts)
        # Wings
        lwing = [(cx - 12, cy + 4), (cx - 22, cy - 6), (cx - 8, cy - 2)]
        rwing = [(cx + 12, cy + 4), (cx + 22, cy - 6), (cx + 8, cy - 2)]
        pygame.draw.polygon(surface, GOLD, lwing)
        pygame.draw.polygon(surface, GOLD, rwing)
        # Eye
        pygame.draw.circle(surface, BLACK, (cx + 3, cy - 15), 2)


# ============================================================
# Explosion
# ============================================================
class Explosion:
    def __init__(self, x, y, size="small"):
        self.x = x
        self.y = y
        self.size = size
        self.frame = 0
        if size == "huge":
            self.max_frames = 40
        elif size == "large":
            self.max_frames = 24
        else:
            self.max_frames = 16

    def update(self):
        self.frame += 1
        return self.frame < self.max_frames

    def finished(self):
        return self.frame >= self.max_frames

    def render(self, surface):
        progress = self.frame / self.max_frames
        if progress < 0.3:
            color = WHITE
            r = int(6 + progress * 20)
        elif progress < 0.6:
            color = YELLOW
            r = int(14 + progress * 16)
        elif progress < 0.85:
            color = ORANGE
            r = int(18 + progress * 10)
        else:
            color = RED
            r = int(22 - progress * 15)
        if self.size == "large":
            r = int(r * 1.4)
        elif self.size == "huge":
            r = int(r * 2.0)
        if r > 0:
            pygame.draw.circle(surface, color, (int(self.x), int(self.y)), r)
            if r > 6:
                pygame.draw.circle(surface, (40, 40, 40), (int(self.x), int(self.y)), max(2, r - 4))


# ============================================================
# Spawner
# ============================================================
SPAWN_POINTS = [
    (CELL_SIZE * 1, CELL_SIZE * 1),     # left
    (CELL_SIZE * 13, CELL_SIZE * 1),    # center
    (CELL_SIZE * 25, CELL_SIZE * 1),    # right
]


class Spawner:
    def __init__(self, level_num):
        self.enemies_remaining = ENEMIES_PER_LEVEL
        self.enemies_per_level = ENEMIES_PER_LEVEL
        self.spawn_timer = 60  # initial delay
        self.spawn_points = SPAWN_POINTS
        self.spawn_queue = self._generate_queue(level_num)

    def _generate_queue(self, level_num):
        # Weighted random with increasing difficulty
        weights = [50, 25, 15, 10]
        if level_num >= 2:
            weights = [40, 25, 20, 15]
        if level_num >= 3:
            weights = [30, 25, 25, 20]
        if level_num >= 4:
            weights = [20, 30, 25, 25]
        if level_num >= 5:
            weights = [15, 25, 30, 30]

        types = [0, 1, 2, 3]
        queue = random.choices(types, weights=weights, k=ENEMIES_PER_LEVEL)
        return queue

    def update(self, enemy_tanks, all_bullets_by_owner):
        self.spawn_timer -= 1

        if self.spawn_timer > 0:
            return None
        if len(self.spawn_queue) == 0:
            return None

        active = [t for t in enemy_tanks if t.alive]
        if len(active) >= MAX_ENEMIES_ON_SCREEN:
            return None

        # Try random spawn points
        pts = list(range(3))
        random.shuffle(pts)
        spawn_rect = pygame.Rect(0, 0, TANK_SIZE, TANK_SIZE)

        for pt_idx in pts:
            sx, sy = self.spawn_points[pt_idx]
            spawn_rect.center = (int(sx), int(sy))
            # Check if any tank occupies this point
            if any(t.alive and t.rect.colliderect(spawn_rect) for t in enemy_tanks):
                continue
            # Also check player
            enemy_type = self.spawn_queue.pop(0)
            enemy = EnemyTank(sx, sy, enemy_type)
            enemy._update_rect()
            self.spawn_timer = SPAWN_INTERVAL
            return enemy

        return None  # all points occupied, wait


# ============================================================
# HUD
# ============================================================
class HUD:
    def __init__(self):
        self.font_large = pygame.font.Font(None, 36)
        self.font_med = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)

    def render(self, surface, game):
        surface.fill(PANEL_BG)
        x = 10
        y = 20

        # Title
        title = self.font_large.render("TANK BATTLE", True, WHITE)
        surface.blit(title, (x, y))
        y += 45

        # Level
        lvl_text = self.font_med.render(f"Level: {game.current_level}", True, WHITE)
        surface.blit(lvl_text, (x, y))
        y += 30

        # Score
        score_text = self.font_med.render(f"Score: {game.score}", True, YELLOW)
        surface.blit(score_text, (x, y))
        y += 35

        # Lives
        lives_text = self.font_med.render("Lives:", True, WHITE)
        surface.blit(lives_text, (x, y))
        y += 25
        for i in range(game.player.lives):
            lx = x + i * 28
            pygame.draw.rect(surface, YELLOW, (lx, y, 20, 20))
            pygame.draw.line(surface, CYAN, (lx + 10, y + 10), (lx + 10, y - 4), 4)
        y += 40

        # Enemies remaining
        rem_text = self.font_med.render("Enemies:", True, WHITE)
        surface.blit(rem_text, (x, y))
        y += 30

        # Draw small enemy icons for remaining count
        rem = game.spawner.enemies_remaining + len([e for e in game.enemies if e.alive])
        cols = 2
        for i in range(min(rem, 20)):
            ex = x + (i % cols) * 22
            ey = y + (i // cols) * 18
            pygame.draw.rect(surface, SILVER, (ex, ey, 16, 14))
            pygame.draw.line(surface, WHITE, (ex + 8, ey + 7), (ex + 8, ey - 2), 3)

        # Controls hint
        y = surface.get_height() - 120
        hints = ["Controls:", "", "Arrow/WASD: Move", "Space/J: Shoot", "Enter: Start"]
        for hint in hints:
            ht = self.font_small.render(hint, True, LIGHT_GRAY)
            surface.blit(ht, (x, y))
            y += 20


# ============================================================
# Levels
# ============================================================
def make_level(walls, base_bricks=True):
    """Convert a compact level description to full 26x26 strings.

    walls: list of (row, col, type) where type 1=brick, 2=steel
    """
    grid = [["0"] * MAP_COLS for _ in range(MAP_ROWS)]
    # Steel border
    for r in range(MAP_ROWS):
        grid[r][0] = "2"
        grid[r][MAP_COLS - 1] = "2"
    for c in range(MAP_COLS):
        grid[0][c] = "2"
        grid[MAP_ROWS - 1][c] = "2"
    # Leave spawn points and base area open
    for c in [0, 1, 12, 13, 24, 25]:
        for r in [0, 1]:
            grid[r][c] = "0"
    # Base area
    for r in [24, 25]:
        for c in [11, 12, 13, 14]:
            grid[r][c] = "0"
    # Apply walls
    for r, c, t in walls:
        if 0 <= r < MAP_ROWS and 0 <= c < MAP_COLS:
            grid[r][c] = str(t)
    # Brick protection around base
    if base_bricks:
        for r in [23, 24, 25]:
            for c in [11, 14]:
                if grid[r][c] == "0":
                    grid[r][c] = "1"
        for r in [23]:
            for c in [12, 13]:
                if grid[r][c] == "0":
                    grid[r][c] = "1"
    return ["".join(row) for row in grid]


def generate_level_1():
    walls = []
    for r in range(2, 23, 4):
        for c in range(2, 24, 4):
            walls.append((r, c, 1))
            walls.append((r, c + 1, 1))
            walls.append((r + 1, c, 1))
            walls.append((r + 1, c + 1, 1))
    # Some steel mixed in
    for r in [4, 12, 20]:
        for c in [6, 18]:
            walls.append((r, c, 2))
            walls.append((r, c + 1, 2))
            walls.append((r + 1, c, 2))
            walls.append((r + 1, c + 1, 2))
    return make_level(walls)


def generate_level_2():
    walls = []
    # Zigzag pattern
    for i in range(3, 22):
        walls.append((i, i, 1))
        walls.append((i, i + 1, 1))
        walls.append((i, 25 - i, 1))
        walls.append((i, 24 - i, 1))
    # Steel clusters
    for r in [6, 12, 18]:
        for c in [6, 18]:
            walls.append((r, c, 2))
            walls.append((r, c + 1, 2))
    return make_level(walls)


def generate_level_3():
    walls = []
    # Horizontal rows with gaps
    for r in [4, 8, 12, 16, 20]:
        for c in range(2, 24):
            if c % 6 != 0:
                walls.append((r, c, 1))
    # Steel pillars
    for r in [3, 7, 11, 15, 19]:
        for c in [4, 12, 20]:
            walls.append((r, c, 2))
            walls.append((r + 1, c, 2))
    return make_level(walls)


def generate_level_4():
    walls = []
    # Maze-like layout
    # Vertical corridors
    for c in [5, 13, 20]:
        for r in range(2, 22, 2):
            walls.append((r, c, 2))
    # Horizontal connectors
    for r in [5, 11, 17]:
        for c in range(2, 24):
            if c not in [5, 13, 20]:
                walls.append((r, c, 1))
    return make_level(walls)


def generate_level_5():
    walls = []
    # Dense fortification
    for r in range(2, 23):
        for c in range(2, 24):
            if (r % 3 == 0 and c % 3 == 0) or (r % 3 == 1 and c % 3 == 1):
                t = 2 if (r + c) % 6 == 0 else 1
                walls.append((r, c, t))
    # Clear some paths
    for r in range(2, 23, 3):
        for c in range(2, 24, 6):
            walls = [w for w in walls if not (w[0] == r and w[1] == c)]
    return make_level(walls)


LEVELS = [
    generate_level_1(),
    generate_level_2(),
    generate_level_3(),
    generate_level_4(),
    generate_level_5(),
]


# ============================================================
# Main Game Class
# ============================================================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Tank Battle - 坦克大战")
        self.clock = pygame.time.Clock()
        self.play_surface = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT))
        self.panel_surface = pygame.Surface((PANEL_WIDTH, PLAY_HEIGHT))
        self.running = True
        self.state = GameState.MENU
        self.score = 0
        self.current_level = 1
        self.transition_timer = 0

        # Game objects (created in start_level)
        self.game_map = Map()
        self.player = None
        self.enemies = []
        self.bullets = []
        self.explosions = []
        self.base = Base()
        self.spawner = None
        self.hud = HUD()

        # Font for menu
        self.menu_font_large = pygame.font.Font(None, 56)
        self.menu_font = pygame.font.Font(None, 28)

    def start_level(self, level_num):
        self.current_level = level_num
        level_data = LEVELS[min(level_num - 1, len(LEVELS) - 1)]
        self.game_map.load_level(level_data)
        self.base = Base()
        self.explosions = []

        # Player spawn: above the base (base at rows 24-25, player at row 22)
        px = (MAP_COLS // 2) * CELL_SIZE
        py = (MAP_ROWS - 4) * CELL_SIZE

        if self.player is None:
            self.player = PlayerTank(px, py)
        else:
            self.player.x = px
            self.player.y = py
            self.player.direction = Dir.UP
            self.player.alive = True
            self.player.shield_timer = SHIELD_TIME
            self.player.shoot_cooldown = 0
            self.player._update_rect()

        self.enemies = []
        self.bullets = []
        self.spawner = Spawner(level_num)
        self.state = GameState.PLAYING

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if self.state == GameState.MENU:
                        self.score = 0
                        self.player = None
                        self.start_level(1)
                    elif self.state == GameState.GAME_OVER:
                        self.score = 0
                        self.player = None
                        self.start_level(1)
                    elif self.state == GameState.VICTORY:
                        self.score = 0
                        self.player = None
                        self.start_level(1)

    def update(self):
        if self.state != GameState.PLAYING and self.state != GameState.LEVEL_TRANSITION:
            return

        if self.state == GameState.LEVEL_TRANSITION:
            self.transition_timer -= 1
            if self.transition_timer <= 0:
                self.start_level(self.current_level + 1)
            return

        keys = pygame.key.get_pressed()

        # Player input and movement
        if self.player.alive:
            dx, dy = self.player.handle_input(keys)
            all_tanks = [self.player] + self.enemies
            self.player.move(dx, dy, self.game_map, all_tanks)
            self.player.update_timers()

            # Shooting
            if self.player.wants_to_shoot(keys):
                bullet_count = sum(1 for b in self.bullets if b.owner == 'player' and b.alive)
                if bullet_count < MAX_PLAYER_BULLETS:
                    bx, by = self.player.get_barrel_tip()
                    self.bullets.append(Bullet(bx, by, self.player.direction, 'player'))
                    self.player.shoot_cooldown = SHOOT_COOLDOWN

        # Respawn player if dead
        if not self.player.alive and self.player.lives > 0:
            self.player.shield_timer -= 1
            if self.player.shield_timer <= 0:
                all_tanks = [self.player] + self.enemies
                self.player.respawn(self.game_map, all_tanks)

        # Update enemy AI and movement
        all_tanks = [self.player] + self.enemies
        for enemy in self.enemies:
            if enemy.alive:
                enemy.update_timers()
                enemy.ai_decision(self.game_map, all_tanks, self.player)
                edx, edy = DIR_VECTORS[enemy.direction]
                edx *= enemy.speed
                edy *= enemy.speed
                enemy.move(edx, edy, self.game_map, all_tanks)

                # Enemy shooting
                if enemy.wants_to_shoot():
                    bullet_count = sum(1 for b in self.bullets if b.owner == 'enemy' and b.alive)
                    if bullet_count < MAX_ENEMY_BULLETS * MAX_ENEMIES_ON_SCREEN:
                        bx, by = enemy.get_barrel_tip()
                        self.bullets.append(Bullet(bx, by, enemy.direction, 'enemy'))
                        enemy.shoot_cooldown = ENEMY_SHOOT_COOLDOWN

        # Update bullets
        for b in self.bullets:
            b.update()
        self.bullets = [b for b in self.bullets if b.alive]

        # Bullet-wall collisions
        for b in self.bullets:
            if not b.alive:
                continue
            hits = self.game_map.bullet_hits_wall(b.rect)
            for row, col in hits:
                if self.game_map.grid[row][col] == 1:  # brick
                    self.game_map.grid[row][col] = 0
                    cx = col * CELL_SIZE + CELL_SIZE // 2
                    cy = row * CELL_SIZE + CELL_SIZE // 2
                    self.explosions.append(Explosion(cx, cy, "small"))
                    b.alive = False
                elif self.game_map.grid[row][col] == 2:  # steel
                    b.alive = False
                    cx = col * CELL_SIZE + CELL_SIZE // 2
                    cy = row * CELL_SIZE + CELL_SIZE // 2
                    self.explosions.append(Explosion(cx, cy, "small"))

        # Bullet-base collisions
        for b in self.bullets:
            if not b.alive:
                continue
            if b.rect.colliderect(self.base.rect):
                self.base.destroyed = True
                b.alive = False
                self.explosions.append(Explosion(self.base.x, self.base.y, "huge"))
                self.state = GameState.GAME_OVER
                break

        # Bullet-bullet collisions
        for i in range(len(self.bullets)):
            for j in range(i + 1, len(self.bullets)):
                b1, b2 = self.bullets[i], self.bullets[j]
                if b1.alive and b2.alive and b1.owner != b2.owner:
                    if b1.rect.colliderect(b2.rect):
                        b1.alive = False
                        b2.alive = False

        # Bullet-tank collisions
        for b in self.bullets:
            if not b.alive:
                continue
            if b.owner == 'player':
                for enemy in self.enemies:
                    if not enemy.alive or enemy.frozen:
                        continue
                    if b.rect.colliderect(enemy.rect):
                        destroyed = enemy.take_damage()
                        b.alive = False
                        if destroyed:
                            self.score += enemy.points_value
                            self.explosions.append(Explosion(enemy.x, enemy.y, "large"))
                        else:
                            self.explosions.append(Explosion(b.x, b.y, "small"))
                        break
            else:
                if self.player.alive and self.player.shield_timer <= 0:
                    if b.rect.colliderect(self.player.rect):
                        b.alive = False
                        self.explosions.append(Explosion(self.player.x, self.player.y, "large"))
                        self.player.die()
                        self.player.shield_timer = 60  # respawn delay

        # Update spawner
        new_enemy = self.spawner.update(self.enemies, self.bullets)
        if new_enemy is not None:
            self.enemies.append(new_enemy)

        # Update explosions
        for exp in self.explosions:
            exp.update()
        self.explosions = [e for e in self.explosions if not e.finished()]

        # Check win
        if self.spawner and len(self.spawner.spawn_queue) == 0:
            active_enemies = [e for e in self.enemies if e.alive]
            if len(active_enemies) == 0:
                if self.current_level < len(LEVELS):
                    self.state = GameState.LEVEL_TRANSITION
                    self.transition_timer = 90
                else:
                    self.state = GameState.VICTORY

        # Check lose (player out of lives)
        if self.player.lives <= 0 and not self.player.alive and self.player.shield_timer <= 0:
            if self.state != GameState.GAME_OVER:
                self.state = GameState.GAME_OVER

    def render(self):
        if self.state == GameState.MENU:
            self._render_menu()
            pygame.display.flip()
            return

        self.screen.fill(BLACK)
        self.play_surface.fill(BLACK)

        # Game surfaces
        self.game_map.render(self.play_surface)
        self.base.render(self.play_surface)
        for exp in self.explosions:
            exp.render(self.play_surface)
        for b in self.bullets:
            b.render(self.play_surface)
        for enemy in self.enemies:
            enemy.render(self.play_surface)
        self.player.render(self.play_surface)

        if self.state == GameState.LEVEL_TRANSITION:
            self._render_transition_overlay()
        elif self.state == GameState.GAME_OVER:
            self._render_game_over_overlay()
        elif self.state == GameState.VICTORY:
            self._render_victory_overlay()

        self.hud.render(self.panel_surface, self)

        self.screen.blit(self.play_surface, (0, 0))
        self.screen.blit(self.panel_surface, (PLAY_WIDTH, 0))
        pygame.display.flip()

    def _render_menu(self):
        self.screen.fill(BLACK)
        # Title
        title = self.menu_font_large.render("TANK BATTLE", True, YELLOW)
        tr = title.get_rect(centerx=SCREEN_WIDTH // 2, centery=200)
        self.screen.blit(title, tr)

        subtitle = self.menu_font_large.render("坦克大战", True, WHITE)
        sr = subtitle.get_rect(centerx=SCREEN_WIDTH // 2, centery=260)
        self.screen.blit(subtitle, sr)

        # Tank icon
        tank_surf = create_tank_surface(YELLOW, GOLD, CYAN)[Dir.UP]
        tr2 = tank_surf.get_rect(centerx=SCREEN_WIDTH // 2, centery=360)
        self.screen.blit(tank_surf, tr2)

        # Instructions
        inst = self.menu_font.render("Press ENTER to Start", True, WHITE)
        ir = inst.get_rect(centerx=SCREEN_WIDTH // 2, centery=440)
        self.screen.blit(inst, ir)

        inst2 = self.menu_font.render("Arrow Keys: Move  |  Space: Shoot", True, LIGHT_GRAY)
        ir2 = inst2.get_rect(centerx=SCREEN_WIDTH // 2, centery=480)
        self.screen.blit(inst2, ir2)

    def _render_transition_overlay(self):
        overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.play_surface.blit(overlay, (0, 0))
        txt = self.menu_font.render(f"Level {self.current_level + 1}", True, WHITE)
        tr = txt.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2))
        self.play_surface.blit(txt, tr)

    def _render_game_over_overlay(self):
        overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.play_surface.blit(overlay, (0, 0))
        txt = self.menu_font_large.render("GAME OVER", True, RED)
        tr = txt.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 - 20))
        self.play_surface.blit(txt, tr)
        txt2 = self.menu_font.render("Press ENTER to Retry", True, WHITE)
        tr2 = txt2.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 + 30))
        self.play_surface.blit(txt2, tr2)

    def _render_victory_overlay(self):
        overlay = pygame.Surface((PLAY_WIDTH, PLAY_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.play_surface.blit(overlay, (0, 0))
        txt = self.menu_font_large.render("VICTORY!", True, GREEN)
        tr = txt.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 - 20))
        self.play_surface.blit(txt, tr)
        txt2 = self.menu_font.render(f"Final Score: {self.score}", True, YELLOW)
        tr2 = txt2.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 + 25))
        self.play_surface.blit(txt2, tr2)
        txt3 = self.menu_font.render("Press ENTER to Play Again", True, WHITE)
        tr3 = txt3.get_rect(center=(PLAY_WIDTH // 2, PLAY_HEIGHT // 2 + 60))
        self.play_surface.blit(txt3, tr3)

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(FPS)
        pygame.quit()


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    game = Game()
    game.run()
