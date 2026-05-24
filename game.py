import pygame
import math
import random
import os
import sys

try:
    import pytmx
except ImportError:
    print("Установи pytmx: py -3.11 -m pip install pytmx")
    raise

# medieval dungeon

pygame.init()

info = pygame.display.Info()
W, H = info.current_w, info.current_h
screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
pygame.display.set_caption("Medieval Dungeon")

# цвета
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GOLD = (255, 215, 0)
RED = (220, 50, 50)
GREEN = (0, 200, 0)
GRAY = (60, 60, 60)

# пути к файлам
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ASSET_DIR = os.path.join(BASE_DIR, "assets")
MAP_DIR = os.path.join(BASE_DIR, "maps")

# настройки экрана и карты
TILED_TILE = 16        # тайл в Tiled 16x16
TILE = 32              # в игре рисуем тайлы 32x32
MAP_SCALE = TILE / TILED_TILE

ZOOM = 2
VIEW_W = int(W / ZOOM)
VIEW_H = int(H / ZOOM)
world_surf = pygame.Surface((VIEW_W, VIEW_H))

# настройки игрока
PLAYER_SIZE = 48
PLAYER_SPEED = 2.8
DASH_SPEED = 8
DASH_TIME_MAX = 6
DASH_COOLDOWN_MAX = 45
TRAIL_LIFE = 18
ATTACK_RANGE = 120

# настройки босса
BOSS_SIZE = PLAYER_SIZE * 3
BOSS_MAX_HP = 2000

# шрифты
font = pygame.font.SysFont(None, 22)
font_big = pygame.font.SysFont(None, 40)
font_small = pygame.font.SysFont(None, 18)

# спрайты

def load_img(path, size=None):
    img = pygame.image.load(os.path.join(ASSET_DIR, path)).convert_alpha()
    if size:
        img = pygame.transform.scale(img, size)
    return img

def load_frames(folder, name, count, size=48):
    frames = []
    for i in range(count):
        path = os.path.join(ASSET_DIR, folder, f"{name}_f{i}.png")
        img = pygame.image.load(path).convert_alpha()
        if isinstance(size, int):
            img = pygame.transform.scale(img, (size, size))
        else:
            img = pygame.transform.scale(img, size)
        frames.append(img)
    return frames

# Игрок
knight_idle = load_frames("heroes/knight", "knight_idle_anim", 6, 48)
knight_run = load_frames("heroes/knight", "knight_run_anim", 6, 48)

# Враги
goblin_idle = load_frames("enemies/goblin", "goblin_idle_anim", 6, 40)
goblin_run = load_frames("enemies/goblin", "goblin_run_anim", 6, 40)
slime_idle = load_frames("enemies/slime", "slime_idle_anim", 6, 40)
slime_run = load_frames("enemies/slime", "slime_run_anim", 6, 40)
bat_frames = load_frames("enemies/flying creature", "fly_anim", 4, 36)

# Объекты и эффекты
torch_frames = load_frames("props_itens", "torch_anim", 6, (32, 32))
chest_closed_frames = load_frames("props_itens", "chest_closed_anim", 8, (32, 32))
chest_open_img = load_img("props_itens/chest_open.png", (32, 32))
door_closed_img = load_img("tiles/wall/door_closed.png", (64, 64))
door_open_frames = load_frames("tiles/wall", "door_anim_opening", 14, (64, 64))
door_open_img = load_img("tiles/wall/door_fullyopen.png", (64, 64))
slash_frames = load_frames("effects (new)", "slash_effect_anim", 3, (80, 80))

boss_idle = load_frames("enemies/slime", "slime_idle_anim", 6, BOSS_SIZE)
boss_run = load_frames("enemies/slime", "slime_run_anim", 6, BOSS_SIZE)

# карты

map_data = {}
map_collision = {}
map_objects = {}
map_width = {}
map_height = {}

def load_map(name, file_name):
    tmx = pytmx.load_pygame(os.path.join(MAP_DIR, file_name))
    map_data[name] = tmx
    map_width[name] = tmx.width * TILE
    map_height[name] = tmx.height * TILE

# Загружаем collision слой
    blocks = []
    for layer in tmx.layers:
        if isinstance(layer, pytmx.TiledTileLayer):
            lname = layer.name.lower()
            if "collision" in lname or "collisium" in lname:
                for x, y, gid in layer:
                    if gid:
                        blocks.append(pygame.Rect(x * TILE, y * TILE, TILE, TILE))
    map_collision[name] = blocks

# Загружаем object layers
    objects = {}
    for layer in tmx.layers:
        if isinstance(layer, pytmx.TiledObjectGroup):
            layer_name = layer.name.lower()
            objects[layer_name] = []
            for obj in layer:
                rect = pygame.Rect(
                    int(obj.x * MAP_SCALE),
                    int(obj.y * MAP_SCALE),
                    max(1, int((obj.width or 16) * MAP_SCALE)),
                    max(1, int((obj.height or 16) * MAP_SCALE)),
                )
                objects[layer_name].append(rect)
    map_objects[name] = objects

def first_object(room_name, object_name, default_rect=None):
    object_name = object_name.lower()
    if object_name in map_objects[room_name] and len(map_objects[room_name][object_name]) > 0:
        return map_objects[room_name][object_name][0]
    return default_rect

def all_objects(room_name, name1, name2=None):
    result = []
    if name1.lower() in map_objects[room_name]:
        result += map_objects[room_name][name1.lower()]
    if name2 and name2.lower() in map_objects[room_name]:
        result += map_objects[room_name][name2.lower()]
    return result

def draw_map(room_name, cam_x, cam_y):
    tmx = map_data[room_name]
    for layer in tmx.visible_layers:
        if not isinstance(layer, pytmx.TiledTileLayer):
            continue

        lname = layer.name.lower()
        if "collision" in lname or "collisium" in lname:
            continue

        for x, y, gid in layer:
            if gid == 0:
                continue
            tile = tmx.get_tile_image_by_gid(gid)
            if tile:
                tile = pygame.transform.scale(tile, (TILE, TILE))
                world_surf.blit(tile, (x * TILE - cam_x, y * TILE - cam_y))

# карты
load_map("hub", "room11.tmx")
load_map("corridor", "koridor.tmx")
load_map("arena", "room1.tmx")
load_map("boss", "boss.tmx")

# объекты на картах
hub_chest = first_object("hub", "chest", pygame.Rect(200, 200, 32, 32))
hub_door = first_object("hub", "door", pygame.Rect(200, 400, 64, 64))

arena_chest = first_object("arena", "chest", pygame.Rect(400, 400, 32, 32))
arena_exit_door = first_object("arena", "door exit", pygame.Rect(400, 400, 64, 64))
arena_player_spawn = first_object("arena", "player", pygame.Rect(map_width["arena"] // 2, 60, 32, 32))

boss_player_spawn = first_object("boss", "player", pygame.Rect(map_width["boss"] // 2, 60, 32, 32))
boss_spawn_rect = first_object("boss", "boss", pygame.Rect(map_width["boss"] // 2, map_height["boss"] // 2, 32, 32))

# переменные игры
# В этой версии состояние игры хранится в обычных переменных,
# а не в огромном словаре game["..."]

screen_mode = "menu"       # menu или game
current_room = "hub"
running = True

# Игрок
player_x = 0
player_y = 0
player_hp = 1
player_max_hp = 1
player_damage = 5
saved_damage = 5
player_dir = 1
player_moving = False
player_anim_frame = 0
player_anim_timer = 0
player_hit_flash = 0
player_knockback_x = 0
player_knockback_y = 0

# Камера
cam_x = 0
cam_y = 0

# Dash
dash_time = 0
dash_cooldown = 0
dash_dx = 0
dash_dy = 0
dash_trails = []

# Атака
attack_cooldown = 0
slash_active = False
slash_frame = 0
slash_timer = 0
slash_x = 0
slash_y = 0
slash_angle = 0

# Общие игровые состояния
keys_count = 0
god_mode = False
game_over = False
victory = False
loot_msg = ""
loot_msg_timer = 0

# Хаб
hub_chest_opened = False
hub_chest_frame = 0
hub_chest_timer = 0
hub_door_state = "closed"      # closed / opening / open
hub_door_frame = 0
hub_door_timer = 0

# Арена
arena_wave = 0
arena_enemies = []
arena_chest_open = False
arena_chest_looted = False
arena_chest_frame = 0
arena_chest_timer = 0
arena_chest_countdown = 0
arena_spawn_timer = 0
arena_waiting_wave = 0

# Босс
boss = None
boss_spawned = False
boss_spawn_timer = 0
boss_minions = []
boss_summon_timer = 60 * 5

# Анимации объектов
torch_frame = 0
torch_timer = 0

# Награды за волны
wave_hp_bonus = [1, 1, 1, 1]
wave_damage_bonus = [5, 10, 10, 10]
wave_key_bonus = [0, 0, 0, 1]
wave_message = [
    "+1 сердце, +5 урона!",
    "+1 сердце, +10 урона!",
    "+1 сердце, +10 урона!",
    "+1 сердце, +10 урона, КЛЮЧ!",
]

# простые вспомогательные функции

def reset_game():
    global screen_mode, current_room, running
    global player_x, player_y, player_hp, player_max_hp, player_damage, saved_damage
    global player_dir, player_moving, player_anim_frame, player_anim_timer
    global player_hit_flash, player_knockback_x, player_knockback_y
    global cam_x, cam_y, dash_time, dash_cooldown, dash_dx, dash_dy, dash_trails
    global attack_cooldown, slash_active, slash_frame, slash_timer, slash_x, slash_y, slash_angle
    global keys_count, god_mode, game_over, victory, loot_msg, loot_msg_timer
    global hub_chest_opened, hub_chest_frame, hub_chest_timer, hub_door_state, hub_door_frame, hub_door_timer
    global arena_wave, arena_enemies, arena_chest_open, arena_chest_looted, arena_chest_frame, arena_chest_timer
    global arena_chest_countdown, arena_spawn_timer, arena_waiting_wave
    global boss, boss_spawned, boss_spawn_timer, boss_minions, boss_summon_timer
    global torch_frame, torch_timer

    screen_mode = "menu"
    current_room = "hub"

    player_x = map_width["hub"] // 2 - PLAYER_SIZE // 2
    player_y = map_height["hub"] // 2 - PLAYER_SIZE // 2 + 40
    player_hp = 1
    player_max_hp = 1
    player_damage = 5
    saved_damage = 5
    player_dir = 1
    player_moving = False
    player_anim_frame = 0
    player_anim_timer = 0
    player_hit_flash = 0
    player_knockback_x = 0
    player_knockback_y = 0

    cam_x = 0
    cam_y = 0

    dash_time = 0
    dash_cooldown = 0
    dash_dx = 0
    dash_dy = 0
    dash_trails = []

    attack_cooldown = 0
    slash_active = False
    slash_frame = 0
    slash_timer = 0
    slash_x = 0
    slash_y = 0
    slash_angle = 0

    keys_count = 0
    god_mode = False
    game_over = False
    victory = False
    loot_msg = ""
    loot_msg_timer = 0

    hub_chest_opened = False
    hub_chest_frame = 0
    hub_chest_timer = 0
    hub_door_state = "closed"
    hub_door_frame = 0
    hub_door_timer = 0

    arena_wave = 0
    arena_enemies = []
    arena_chest_open = False
    arena_chest_looted = False
    arena_chest_frame = 0
    arena_chest_timer = 0
    arena_chest_countdown = 0
    arena_spawn_timer = 0
    arena_waiting_wave = 0

    boss = None
    boss_spawned = False
    boss_spawn_timer = 0
    boss_minions = []
    boss_summon_timer = 60 * 5

    torch_frame = 0
    torch_timer = 0

    clamp_camera()

def animate(frames, timer, frame, speed=8, dt=1):
    timer += dt
    while timer >= speed:
        timer -= speed
        frame = (frame + 1) % len(frames)
    return timer, frame

def player_rect(x=None, y=None):
    if x is None:
        x = player_x
    if y is None:
        y = player_y
    return pygame.Rect(int(x) + 12, int(y) + 16, PLAYER_SIZE - 24, PLAYER_SIZE - 20)

def is_near(rect, distance=70):
    px = player_x + PLAYER_SIZE // 2
    py = player_y + PLAYER_SIZE // 2
    return math.hypot(px - rect.centerx, py - rect.centery) < distance

def clamp_camera():
    global cam_x, cam_y
    if map_width[current_room] <= VIEW_W:
        cam_x = -(VIEW_W - map_width[current_room]) / 2
    else:
        cam_x = max(0, min(cam_x, map_width[current_room] - VIEW_W))

    if map_height[current_room] <= VIEW_H:
        cam_y = -(VIEW_H - map_height[current_room]) / 2
    else:
        cam_y = max(0, min(cam_y, map_height[current_room] - VIEW_H))

def draw_heart(surface, x, y, filled=True, scale=2):
    color = WHITE if filled else (70, 80, 85)
    pattern = ["01100110", "11111111", "11111111", "01111110", "00111100", "00011000"]
    pygame.draw.rect(surface, BLACK, (x - scale, y - scale, 8 * scale + 2 * scale, 6 * scale + 2 * scale))
    for row, line in enumerate(pattern):
        for col, pixel in enumerate(line):
            if pixel == "1":
                pygame.draw.rect(surface, color, (x + col * scale, y + row * scale, scale, scale))

def draw_hp_bar(surface, x, y, w, h, hp, max_hp, color=RED):
    pygame.draw.rect(surface, GRAY, (x, y, w, h))
    if max_hp > 0:
        pygame.draw.rect(surface, color, (x, y, int(w * hp / max_hp), h))
    pygame.draw.rect(surface, WHITE, (x, y, w, h), 1)

# collision и переходы между комнатами

def is_blocked(new_x, new_y):
    test_rect = player_rect(new_x, new_y)

# Не выпускаем игрока за карту
    if test_rect.left < 0 or test_rect.top < 0:
        return True
    if test_rect.right > map_width[current_room] or test_rect.bottom > map_height[current_room]:
        return True

# Стены / collision слой
    for block in map_collision[current_room]:
# Хаб: если дверь открыта, коллизия в зоне двери не работает
        if current_room == "hub" and hub_door_state == "open":
            if block.colliderect(hub_door.inflate(16, 16)):
                continue

# Коридор: пропускаем верхний и нижний проход
        if current_room == "corridor":
            top_passage = pygame.Rect(map_width["corridor"] // 2 - 40, 0, 80, 60)
            bottom_passage = pygame.Rect(map_width["corridor"] // 2 - 50, map_height["corridor"] - 70, 100, 80)
            if block.colliderect(top_passage) or block.colliderect(bottom_passage):
                continue

# Арена: если выход к боссу открыт, не блокируем дверь
        if current_room == "arena" and arena_exit_door and (keys_count > 0 or arena_wave >= 5):
            if block.colliderect(arena_exit_door.inflate(20, 20)):
                continue

# Босс-комната: пропускаем верхний вход
        if current_room == "boss":
            top_passage = pygame.Rect(map_width["boss"] // 2 - 60, 0, 120, 80)
            if block.colliderect(top_passage):
                continue

        if test_rect.colliderect(block):
            return True

# Сундук в хабе блокирует игрока пока не открыт
    if current_room == "hub" and not hub_chest_opened:
        if test_rect.colliderect(hub_chest.inflate(-4, -4)):
            return True

# Дверь в хабе блокирует игрока пока не открыта
    if current_room == "hub" and hub_door_state != "open":
        if test_rect.colliderect(hub_door.inflate(-4, -4)):
            return True

# Сундук арены блокирует, когда закрыт/появился
    if current_room == "arena" and not arena_chest_open:
        if test_rect.colliderect(arena_chest.inflate(-4, -4)):
            return True

# Выходная дверь арены закрыта до ключа/прохождения волн
    if current_room == "arena" and arena_exit_door:
        if keys_count <= 0 and arena_wave < 5:
            if test_rect.colliderect(arena_exit_door.inflate(-4, -4)):
                return True

    return False

def move_player_with_collision(move_x, move_y, dt):
    global player_x, player_y

    new_x = player_x + move_x * dt
    if not is_blocked(new_x, player_y):
        player_x = new_x

    new_y = player_y + move_y * dt
    if not is_blocked(player_x, new_y):
        player_y = new_y

def switch_room(new_room, x, y):
    global current_room, player_x, player_y, cam_x, cam_y, dash_time, dash_trails
    current_room = new_room
    player_x = float(x)
    player_y = float(y)
    dash_time = 0
    dash_trails = []
    cam_x = 0
    cam_y = 0
    clamp_camera()

def check_room_transitions():
    global arena_wave, arena_waiting_wave, arena_spawn_timer, arena_enemies
    global arena_chest_open, arena_chest_looted, player_hp, loot_msg, loot_msg_timer
    global keys_count, boss_spawn_timer, boss_minions, boss_summon_timer

    rect = player_rect()

# Хаб -> коридор
    if current_room == "hub" and hub_door_state == "open":
        if rect.colliderect(hub_door.inflate(20, 28)):
            if rect.centery >= hub_door.centery:
                switch_room("corridor", map_width["corridor"] / 2 - PLAYER_SIZE / 2, 40)

# Коридор -> хаб / арена
    elif current_room == "corridor":
        if rect.top <= 32:
            switch_room("hub", hub_door.centerx - PLAYER_SIZE / 2, map_height["hub"] - PLAYER_SIZE - 10)

        if rect.bottom >= map_height["corridor"] - 32:
            sx = arena_player_spawn.centerx - PLAYER_SIZE // 2
            sy = arena_player_spawn.centery - PLAYER_SIZE // 2
            switch_room("arena", sx, sy)

            if arena_wave == 0:
                arena_wave = 1
                arena_waiting_wave = 1
                arena_spawn_timer = 60 * 5
                arena_enemies = []
                arena_chest_open = False
                arena_chest_looted = False
                player_hp = player_max_hp
                loot_msg = "Приготовься..."
                loot_msg_timer = 120

# Арена -> коридор / босс
    elif current_room == "arena":
        if rect.top <= 8:
            switch_room("corridor", map_width["corridor"] / 2 - PLAYER_SIZE / 2, map_height["corridor"] - PLAYER_SIZE - 60)

        if arena_exit_door and (keys_count > 0 or arena_wave >= 5):
            if rect.colliderect(arena_exit_door.inflate(28, 28)):
                if keys_count > 0:
                    keys_count -= 1
                sx = boss_player_spawn.centerx - PLAYER_SIZE // 2
                sy = boss_player_spawn.centery - PLAYER_SIZE // 2
                switch_room("boss", sx, sy)
                player_hp = player_max_hp
                boss_spawn_timer = 60 * 5
                boss_minions = []
                boss_summon_timer = 60 * 5
                loot_msg = "Босс появится через 5 секунд..."
                loot_msg_timer = 180

# Босс -> арена
    elif current_room == "boss":
        if rect.top <= 8:
            switch_room("arena", map_width["arena"] / 2 - PLAYER_SIZE / 2, map_height["arena"] - PLAYER_SIZE - 60)

# враги и босс

def make_enemy(enemy_type, x, y, hp=None):
    if enemy_type == "goblin":
        size = 40
        speed = random.uniform(1.0, 2.0)
        hp = hp or random.randint(75, 120)
        damage = 1
        cooldown = 60
        windup = 24
        stop = 38
        attack_dist = 48
        knockback = 8
    elif enemy_type == "slime":
        size = 40
        speed = random.uniform(0.5, 0.9)
        hp = hp or random.randint(150, 200)
        damage = 2
        cooldown = 90
        windup = 35
        stop = 35
        attack_dist = 45
        knockback = 12
    else:  # bat
        size = 36
        speed = random.uniform(2.8, 3.8)
        hp = hp or random.randint(30, 50)
        damage = 1
        cooldown = 30
        windup = 10
        stop = 30
        attack_dist = 40
        knockback = 4

    return {
        "type": enemy_type,
        "x": float(x),
        "y": float(y),
        "hp": hp,
        "max_hp": hp,
        "speed": speed,
        "size": size,
        "damage": damage,
        "cooldown_max": cooldown,
        "windup_max": windup,
        "stop": stop,
        "attack_dist": attack_dist,
        "knockback_power": knockback,
        "alive": True,
        "dir": 1,
        "anim_frame": 0,
        "anim_timer": 0,
        "hit_flash": 0,
        "attacking": False,
        "attack_cooldown": random.randint(0, 30),
        "attack_windup": 0,
        "knockback_x": 0,
        "knockback_y": 0,
    }

def make_wave():
    enemies = []
    count = random.randint(7, 10)
    center_x = map_width["arena"] // 2
    center_y = map_height["arena"] // 2
    enemy_pool = ["goblin", "goblin", "goblin", "slime", "bat"]

    for i in range(count):
        enemy_type = random.choice(enemy_pool)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.randint(120, 250)
        x = max(80, min(center_x + math.cos(angle) * dist, map_width["arena"] - 80))
        y = max(80, min(center_y + math.sin(angle) * dist, map_height["arena"] - 80))
        enemies.append(make_enemy(enemy_type, x, y))

    return enemies

def enemy_frames(enemy):
    if enemy["type"] == "goblin":
        return goblin_idle if enemy["attacking"] else goblin_run
    if enemy["type"] == "slime":
        return slime_idle if enemy["attacking"] else slime_run
    return bat_frames

def update_enemy(enemy, dt):
    global player_hp, player_hit_flash, player_knockback_x, player_knockback_y

    enemy["attack_cooldown"] = max(0, enemy["attack_cooldown"] - dt)
    enemy["attack_windup"] = max(0, enemy["attack_windup"] - dt)

# Если врага откинуло после удара
    if abs(enemy["knockback_x"]) > 0.1 or abs(enemy["knockback_y"]) > 0.1:
        enemy["attacking"] = False
        enemy["x"] += enemy["knockback_x"] * dt
        enemy["y"] += enemy["knockback_y"] * dt
        enemy["x"] = max(80, min(enemy["x"], map_width[current_room] - 80))
        enemy["y"] = max(80, min(enemy["y"], map_height[current_room] - 80))
        enemy["knockback_x"] *= 0.7 ** dt
        enemy["knockback_y"] *= 0.7 ** dt
    else:
# Двигается к игроку
        enemy_cx = enemy["x"] + enemy["size"] // 2
        enemy_cy = enemy["y"] + enemy["size"] // 2
        player_cx = player_x + PLAYER_SIZE // 2
        player_cy = player_y + PLAYER_SIZE // 2
        dx = player_cx - enemy_cx
        dy = player_cy - enemy_cy
        dist = math.hypot(dx, dy)

        enemy["attacking"] = False
        if dist > enemy["stop"]:
            enemy["x"] += (dx / dist) * enemy["speed"] * dt
            enemy["y"] += (dy / dist) * enemy["speed"] * dt
            enemy["dir"] = 1 if dx > 0 else -1
            enemy["attack_windup"] = 0
        else:
# Стоит рядом и готовит удар
            enemy["attacking"] = True
            enemy["dir"] = 1 if dx > 0 else -1
            if dist < enemy["attack_dist"] and enemy["attack_cooldown"] <= 0:
                if enemy["attack_windup"] <= 0:
                    enemy["attack_windup"] = enemy["windup_max"]
                elif enemy["attack_windup"] <= dt:
                    if not god_mode:
                        player_hp -= enemy["damage"]
                        player_hit_flash = 10
                    else:
                        player_hit_flash = 4
                    enemy["attack_cooldown"] = enemy["cooldown_max"]
                    enemy["attack_windup"] = 0
                    if dist > 0:
                        player_knockback_x = (dx / dist) * 4
                        player_knockback_y = (dy / dist) * 4

    if enemy["hit_flash"] > 0:
        enemy["hit_flash"] = max(0, enemy["hit_flash"] - dt)

    frames = enemy_frames(enemy)
    enemy["anim_timer"], enemy["anim_frame"] = animate(frames, enemy["anim_timer"], enemy["anim_frame"], dt=dt)

def make_boss():
    return {
        "x": float(boss_spawn_rect.centerx - BOSS_SIZE // 2),
        "y": float(boss_spawn_rect.centery - BOSS_SIZE // 2),
        "hp": BOSS_MAX_HP,
        "max_hp": BOSS_MAX_HP,
        "speed": 1.25,
        "alive": True,
        "dir": 1,
        "anim_frame": 0,
        "anim_timer": 0,
        "hit_flash": 0,
        "attacking": False,
        "attack_cooldown": 0,
        "attack_windup": 0,
        "knockback_x": 0,
        "knockback_y": 0,
    }

def update_boss(dt):
    global player_hp, player_hit_flash, player_knockback_x, player_knockback_y

    if boss is None or not boss["alive"]:
        return

    boss["attack_cooldown"] = max(0, boss["attack_cooldown"] - dt)
    boss["attack_windup"] = max(0, boss["attack_windup"] - dt)

    if abs(boss["knockback_x"]) > 0.1 or abs(boss["knockback_y"]) > 0.1:
        boss["x"] += boss["knockback_x"] * dt
        boss["y"] += boss["knockback_y"] * dt
        boss["x"] = max(80, min(boss["x"], map_width["boss"] - BOSS_SIZE - 80))
        boss["y"] = max(80, min(boss["y"], map_height["boss"] - BOSS_SIZE - 80))
        boss["knockback_x"] *= 0.7 ** dt
        boss["knockback_y"] *= 0.7 ** dt
    else:
        boss_cx = boss["x"] + BOSS_SIZE // 2
        boss_cy = boss["y"] + BOSS_SIZE // 2
        player_cx = player_x + PLAYER_SIZE // 2
        player_cy = player_y + PLAYER_SIZE // 2
        dx = player_cx - boss_cx
        dy = player_cy - boss_cy
        dist = math.hypot(dx, dy)

        boss["attacking"] = False
        if dist > 75:
            boss["x"] += (dx / dist) * boss["speed"] * dt
            boss["y"] += (dy / dist) * boss["speed"] * dt
            boss["dir"] = 1 if dx > 0 else -1
            boss["attack_windup"] = 0
        else:
            boss["attacking"] = True
            boss["dir"] = 1 if dx > 0 else -1
            if dist < 105 and boss["attack_cooldown"] <= 0:
                if boss["attack_windup"] <= 0:
                    boss["attack_windup"] = 40
                elif boss["attack_windup"] <= dt:
                    if not god_mode:
                        player_hp -= 3
                        player_hit_flash = 10
                    else:
                        player_hit_flash = 4
                    boss["attack_cooldown"] = 60
                    boss["attack_windup"] = 0
                    if dist > 0:
                        player_knockback_x = (dx / dist) * 6
                        player_knockback_y = (dy / dist) * 6

    if boss["hit_flash"] > 0:
        boss["hit_flash"] = max(0, boss["hit_flash"] - dt)

    frames = boss_idle if boss["attacking"] else boss_run
    boss["anim_timer"], boss["anim_frame"] = animate(frames, boss["anim_timer"], boss["anim_frame"], dt=dt)

def summon_boss_minions():
    global boss_minions, loot_msg, loot_msg_timer
    if boss is None:
        return

    count = random.randint(2, 5)
    boss_cx = boss["x"] + BOSS_SIZE // 2
    boss_cy = boss["y"] + BOSS_SIZE // 2

    for i in range(count):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.randint(70, 130)
        x = max(80, min(boss_cx + math.cos(angle) * dist, map_width["boss"] - 120))
        y = max(80, min(boss_cy + math.sin(angle) * dist, map_height["boss"] - 120))
        boss_minions.append(make_enemy("slime", x, y, hp=200))

    loot_msg = f"Босс призвал слаймов: {count}!"
    loot_msg_timer = 90

# отрисовка объектов

def draw_chest(cam_x_int, cam_y_int, rect, opened, frame):
    img = chest_open_img if opened else chest_closed_frames[frame % len(chest_closed_frames)]
    img = pygame.transform.scale(img, (rect.width, rect.height))
    world_surf.blit(img, (rect.x - cam_x_int, rect.y - cam_y_int))

def draw_door(cam_x_int, cam_y_int, rect, state, frame):
    if state == "closed":
        img = door_closed_img
    elif state == "opening":
        img = door_open_frames[min(frame, len(door_open_frames) - 1)]
    else:
        img = door_open_img

    img = pygame.transform.scale(img, (rect.width, rect.height))
    world_surf.blit(img, (rect.x - cam_x_int, rect.y - cam_y_int))

def draw_enemy(cam_x_int, cam_y_int, enemy):
    frames = enemy_frames(enemy)
    frame = frames[enemy["anim_frame"] % len(frames)]

    if enemy["dir"] == -1:
        frame = pygame.transform.flip(frame, True, False)

    if enemy["hit_flash"] > 0:
        white = frame.copy()
        white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        frame = white
    elif enemy["attack_windup"] > 0:
        warning = frame.copy()
        warning.fill((80, 80, 80), special_flags=pygame.BLEND_RGB_ADD)
        frame = warning

    world_surf.blit(frame, (enemy["x"] - cam_x_int, enemy["y"] - cam_y_int))

def draw_boss(cam_x_int, cam_y_int):
    if boss is None or not boss["alive"]:
        return

    frames = boss_idle if boss["attacking"] else boss_run
    frame = frames[boss["anim_frame"] % len(frames)]

    if boss["dir"] == -1:
        frame = pygame.transform.flip(frame, True, False)

    if boss["hit_flash"] > 0:
        white = frame.copy()
        white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        frame = white
    elif boss["attack_windup"] > 0:
        warning = frame.copy()
        warning.fill((80, 80, 80), special_flags=pygame.BLEND_RGB_ADD)
        frame = warning

    bx = boss["x"] - cam_x_int
    by = boss["y"] - cam_y_int
    world_surf.blit(frame, (bx, by))
    draw_hp_bar(world_surf, int(bx), int(by) - 12, BOSS_SIZE, 8, boss["hp"], boss["max_hp"], RED)

# меню, управление, атака

def handle_attack(mx, my):
    global attack_cooldown, slash_active, slash_frame, slash_timer, slash_x, slash_y, slash_angle
    global boss, victory

    attack_cooldown = 30

    px = player_x + PLAYER_SIZE // 2
    py = player_y + PLAYER_SIZE // 2
    angle = math.atan2(my - py, mx - px)

    slash_active = True
    slash_frame = 0
    slash_timer = 0
    slash_x = px + math.cos(angle) * 75 - 40
    slash_y = py + math.sin(angle) * 75 - 40
    slash_angle = math.degrees(angle)

# Удар по врагам арены
    if current_room == "arena":
        for enemy in arena_enemies:
            hit_enemy(enemy, px, py, angle)

# Удар по мини-слаймам и боссу
    if current_room == "boss":
        for enemy in boss_minions:
            hit_enemy(enemy, px, py, angle)

        if boss and boss["alive"]:
            dx = boss["x"] + BOSS_SIZE // 2 - px
            dy = boss["y"] + BOSS_SIZE // 2 - py
            dist = math.hypot(dx, dy)
            if dist < ATTACK_RANGE + BOSS_SIZE // 2:
                enemy_angle = math.atan2(dy, dx)
                diff = abs(math.atan2(math.sin(enemy_angle - angle), math.cos(enemy_angle - angle)))
                if diff < math.pi / 2:
                    boss["hp"] -= player_damage
                    boss["hit_flash"] = 10
                    if dist > 0:
                        boss["knockback_x"] = (dx / dist) * 4
                        boss["knockback_y"] = (dy / dist) * 4
                    if boss["hp"] <= 0:
                        boss["alive"] = False
                        victory = True

def hit_enemy(enemy, px, py, attack_angle):
    if not enemy["alive"]:
        return

    dx = enemy["x"] - px
    dy = enemy["y"] - py
    dist = math.hypot(dx, dy)

    if dist < ATTACK_RANGE:
        enemy_angle = math.atan2(dy, dx)
        diff = abs(math.atan2(math.sin(enemy_angle - attack_angle), math.cos(enemy_angle - attack_angle)))
        if diff < math.pi / 2:
            enemy["hp"] -= player_damage
            enemy["hit_flash"] = 10
            if dist > 0:
                enemy["knockback_x"] = (dx / dist) * 8
                enemy["knockback_y"] = (dy / dist) * 8
            if enemy["hp"] <= 0:
                enemy["alive"] = False

def interact():
    global hub_chest_opened, player_max_hp, player_hp, player_damage, keys_count
    global loot_msg, loot_msg_timer, hub_door_state, hub_door_frame, hub_door_timer
    global arena_chest_open, arena_chest_looted

# Сундук хаба
    if current_room == "hub" and not hub_chest_opened and is_near(hub_chest):
        hub_chest_opened = True
        player_max_hp += 3
        player_hp = player_max_hp
        player_damage += 20
        keys_count += 1
        loot_msg = "+3 сердца, +20 урона, ключ!"
        loot_msg_timer = 180
        return

# Дверь хаба
    if current_room == "hub" and hub_door_state == "closed" and is_near(hub_door, 90):
        if keys_count > 0:
            keys_count -= 1
            hub_door_state = "opening"
            hub_door_frame = 0
            hub_door_timer = 0
            loot_msg = "Дверь открывается..."
            loot_msg_timer = 120
        else:
            loot_msg = "Нужен ключ!"
            loot_msg_timer = 90
        return

# Сундук арены
    if current_room == "arena" and arena_chest_open and not arena_chest_looted and is_near(arena_chest, 80):
        index = arena_wave - 1
        if 0 <= index < 4:
            player_max_hp += wave_hp_bonus[index]
            player_hp = player_max_hp
            player_damage += wave_damage_bonus[index]
            keys_count += wave_key_bonus[index]
            loot_msg = wave_message[index]
            loot_msg_timer = 200
        arena_chest_looted = True
        arena_chest_open = False

# обновление игры

def update_player(dt, mx, my):
    global player_x, player_y, player_dir, player_moving, player_anim_frame, player_anim_timer
    global dash_time, dash_cooldown, dash_trails, player_knockback_x, player_knockback_y
    global cam_x, cam_y

    keys = pygame.key.get_pressed()
    dx = 0
    dy = 0
    player_moving = False

    if keys[pygame.K_w] or keys[pygame.K_UP]:
        dy = -1
        player_moving = True
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        dy = 1
        player_moving = True
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        dx = -1
        player_moving = True
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        dx = 1
        player_moving = True

    if dx != 0 and dy != 0:
        dx *= 0.707
        dy *= 0.707

    move_x = dx * PLAYER_SPEED
    move_y = dy * PLAYER_SPEED

# Рывок
    if dash_time > 0:
        move_x += dash_dx * DASH_SPEED
        move_y += dash_dy * DASH_SPEED
        dash_time = max(0, dash_time - dt)
        dash_trails.append({"x": player_x, "y": player_y, "dir": player_dir, "life": TRAIL_LIFE})

    dash_cooldown = max(0, dash_cooldown - dt)

# След рывка исчезает
    for trail in dash_trails:
        trail["life"] -= dt
    dash_trails = [trail for trail in dash_trails if trail["life"] > 0]

# Отталкивание игрока от удара
    if abs(player_knockback_x) > 0.05 or abs(player_knockback_y) > 0.05:
        move_x += player_knockback_x
        move_y += player_knockback_y
        player_knockback_x *= 0.72 ** dt
        player_knockback_y *= 0.72 ** dt

    move_player_with_collision(move_x, move_y, dt)
    check_room_transitions()

# Камера плавно следует за игроком
    target_x = player_x - VIEW_W // 2 + PLAYER_SIZE // 2
    target_y = player_y - VIEW_H // 2 + PLAYER_SIZE // 2
    smooth = 1 - (1 - 0.1) ** dt
    cam_x += (target_x - cam_x) * smooth
    cam_y += (target_y - cam_y) * smooth
    clamp_camera()

# Направление игрока к мышке
    player_dir = 1 if mx >= player_x + PLAYER_SIZE // 2 else -1

    frames = knight_run if player_moving else knight_idle
    player_anim_timer, player_anim_frame = animate(frames, player_anim_timer, player_anim_frame, dt=dt)

def update_common_animations(dt):
    global torch_timer, torch_frame, hub_chest_timer, hub_chest_frame
    global hub_door_timer, hub_door_frame, hub_door_state
    global slash_timer, slash_frame, slash_active
    global attack_cooldown, loot_msg_timer, player_hit_flash

    torch_timer, torch_frame = animate(torch_frames, torch_timer, torch_frame, speed=8, dt=dt)

    if current_room == "hub" and not hub_chest_opened:
        hub_chest_timer, hub_chest_frame = animate(chest_closed_frames, hub_chest_timer, hub_chest_frame, speed=10, dt=dt)

    if hub_door_state == "opening":
        hub_door_timer += dt
        if hub_door_timer >= 4:
            hub_door_timer = 0
            hub_door_frame += 1
            if hub_door_frame >= len(door_open_frames):
                hub_door_state = "open"

    if slash_active:
        slash_timer += dt
        if slash_timer >= 5:
            slash_timer = 0
            slash_frame += 1
            if slash_frame >= len(slash_frames):
                slash_active = False

    attack_cooldown = max(0, attack_cooldown - dt)
    loot_msg_timer = max(0, loot_msg_timer - dt)
    player_hit_flash = max(0, player_hit_flash - dt)

def update_arena(dt):
    global arena_wave, arena_waiting_wave, arena_spawn_timer, arena_enemies
    global arena_chest_open, arena_chest_looted, arena_chest_countdown, arena_chest_timer, arena_chest_frame
    global player_hp, loot_msg, loot_msg_timer

    if current_room != "arena" or arena_wave <= 0:
        return

# Ждём таймер перед новой волной
    if arena_spawn_timer > 0:
        arena_spawn_timer = max(0, arena_spawn_timer - dt)
        if arena_spawn_timer <= 0 and arena_waiting_wave > 0:
            arena_wave = arena_waiting_wave
            arena_enemies = make_wave()
            arena_waiting_wave = 0
            arena_chest_open = False
            arena_chest_looted = False
            player_hp = player_max_hp
            loot_msg = f"Волна {arena_wave}!"
            loot_msg_timer = 90

# Обновляем врагов
    if arena_spawn_timer <= 0:
        for enemy in arena_enemies:
            if enemy["alive"]:
                update_enemy(enemy, dt)

    alive_count = sum(1 for enemy in arena_enemies if enemy["alive"])

# Волна закончилась — появляется сундук
    if arena_spawn_timer <= 0 and len(arena_enemies) > 0 and alive_count == 0:
        if not arena_chest_open and not arena_chest_looted and arena_wave <= 4:
            arena_chest_open = True
            arena_chest_looted = False
            arena_chest_countdown = 60 * 10

# Сундук арены живёт 10 секунд
    if arena_chest_open and not arena_chest_looted:
        arena_chest_timer, arena_chest_frame = animate(chest_closed_frames, arena_chest_timer, arena_chest_frame, speed=10, dt=dt)
        arena_chest_countdown = max(0, arena_chest_countdown - dt)
        if arena_chest_countdown <= 0:
            arena_chest_open = False
            arena_chest_looted = True

# После сундука запускаем следующую волну
    if arena_chest_looted and alive_count == 0 and arena_spawn_timer <= 0:
        if arena_wave < 4:
            arena_waiting_wave = arena_wave + 1
            arena_spawn_timer = 60 * 5
            arena_enemies = []
            arena_chest_open = False
            arena_chest_looted = False
            player_hp = player_max_hp
            loot_msg = "Следующая волна через 5 секунд..."
            loot_msg_timer = 180
        elif arena_wave == 4:
            arena_wave = 5
            arena_enemies = []
            arena_chest_open = False
            arena_chest_looted = False
            player_hp = player_max_hp
            loot_msg = "Ключ получен. Иди к боссу!"
            loot_msg_timer = 180

def update_boss_room(dt):
    global boss, boss_spawned, boss_spawn_timer, boss_summon_timer, boss_minions
    global player_hp, loot_msg, loot_msg_timer

    if current_room != "boss":
        return

# Таймер появления босса
    if not boss_spawned and boss is None:
        if boss_spawn_timer > 0:
            boss_spawn_timer = max(0, boss_spawn_timer - dt)
        else:
            boss = make_boss()
            boss_spawned = True
            player_hp = player_max_hp
            loot_msg = "СЛАЙМ-КОРОЛЬ появился!"
            loot_msg_timer = 120

# Обновление босса
    if boss and boss["alive"]:
        update_boss(dt)

# Раз в 5 секунд босс призывает мини-слаймов
        boss_summon_timer = max(0, boss_summon_timer - dt)
        if boss_summon_timer <= 0:
            boss_summon_timer = 60 * 5
            summon_boss_minions()

# Мини-слаймы босса
    for enemy in boss_minions:
        if enemy["alive"]:
            update_enemy(enemy, dt)
    boss_minions = [enemy for enemy in boss_minions if enemy["alive"]]

# отрисовка всей игры

def draw_game():
    cam_x_int = int(cam_x)
    cam_y_int = int(cam_y)

    world_surf.fill(BLACK)
    draw_map(current_room, cam_x_int, cam_y_int)

# Двери
    if current_room == "hub":
        draw_door(cam_x_int, cam_y_int, hub_door, hub_door_state, hub_door_frame)
    if current_room == "arena" and arena_exit_door:
        door_state = "open" if keys_count > 0 or arena_wave >= 5 else "closed"
        draw_door(cam_x_int, cam_y_int, arena_exit_door, door_state, 0)

# Сундуки
    if current_room == "hub":
        draw_chest(cam_x_int, cam_y_int, hub_chest, hub_chest_opened, hub_chest_frame)
    if current_room == "arena":
        chest_is_open = (not arena_chest_open and arena_chest_looted)
        draw_chest(cam_x_int, cam_y_int, arena_chest, chest_is_open, arena_chest_frame)

# Факелы
    for torch in all_objects(current_room, "torch", "факел"):
        img = pygame.transform.scale(torch_frames[torch_frame % len(torch_frames)], (max(16, torch.width), max(16, torch.height)))
        world_surf.blit(img, (torch.x - cam_x_int, torch.y - cam_y_int))

# Враги арены
    if current_room == "arena":
        for enemy in arena_enemies:
            if enemy["alive"]:
                draw_enemy(cam_x_int, cam_y_int, enemy)

# Враги босса
    if current_room == "boss":
        for enemy in boss_minions:
            if enemy["alive"]:
                draw_enemy(cam_x_int, cam_y_int, enemy)
        draw_boss(cam_x_int, cam_y_int)

    draw_hints(cam_x_int, cam_y_int)
    draw_player(cam_x_int, cam_y_int)
    draw_slash(cam_x_int, cam_y_int)

    zoomed = pygame.transform.scale(world_surf, (W, H))
    screen.blit(zoomed, (0, 0))
    draw_ui()

def draw_player(cam_x_int, cam_y_int):
    frames = knight_run if player_moving else knight_idle
    frame = frames[player_anim_frame]

# След рывка
    for trail in dash_trails:
        ghost = frame.copy()
        if trail["dir"] == -1:
            ghost = pygame.transform.flip(ghost, True, False)
        ghost.set_alpha(int(120 * trail["life"] / TRAIL_LIFE))
        world_surf.blit(ghost, (trail["x"] - cam_x_int, trail["y"] - cam_y_int))

# Игрок
    if player_dir == -1:
        frame = pygame.transform.flip(frame, True, False)
    if player_hit_flash > 0:
        white = frame.copy()
        white.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        frame = white
    world_surf.blit(frame, (player_x - cam_x_int, player_y - cam_y_int))

def draw_slash(cam_x_int, cam_y_int):
    if slash_active and slash_frame < len(slash_frames):
        img = slash_frames[slash_frame]
        img = pygame.transform.rotate(img, -slash_angle)
        world_surf.blit(img, (slash_x - cam_x_int, slash_y - cam_y_int))

def draw_hints(cam_x_int, cam_y_int):
    if current_room == "hub" and not hub_chest_opened and is_near(hub_chest):
        text = font_small.render("E — открыть сундук", True, GOLD)
        world_surf.blit(text, (hub_chest.x - cam_x_int - 20, hub_chest.y - cam_y_int - 22))

    if current_room == "hub" and hub_door_state == "closed" and is_near(hub_door, 90):
        text_line = "E — открыть дверь" if keys_count > 0 else "Нужен ключ!"
        text = font_small.render(text_line, True, GOLD)
        world_surf.blit(text, (hub_door.x - cam_x_int - 20, hub_door.y - cam_y_int - 22))

    if current_room == "arena" and arena_chest_open and not arena_chest_looted and is_near(arena_chest, 90):
        sec = math.ceil(arena_chest_countdown / 60)
        text = font_small.render(f"E — лут ({sec}с)", True, GOLD)
        world_surf.blit(text, (arena_chest.x - cam_x_int - 20, arena_chest.y - cam_y_int - 22))

def draw_ui():
# Сердца
    for i in range(player_max_hp):
        draw_heart(screen, 12 + i * 22, H - 34, filled=i < player_hp, scale=2)

# Волны арены
    if current_room == "arena" and arena_wave > 0:
        alive_count = sum(1 for enemy in arena_enemies if enemy["alive"])
        if arena_spawn_timer > 0 and arena_waiting_wave > 0:
            sec = max(1, math.ceil(arena_spawn_timer / 60))
            text = font_big.render(f"Волна {arena_waiting_wave} через {sec}...", True, GOLD)
        else:
            text = font.render(f"Волна {min(arena_wave, 4)}/4   Врагов: {alive_count}", True, WHITE)
        screen.blit(text, (W // 2 - text.get_width() // 2, 10))

# Босс
    if current_room == "boss" and boss_spawn_timer > 0 and boss is None:
        sec = max(1, math.ceil(boss_spawn_timer / 60))
        text = font_big.render(f"Босс через {sec}...", True, GOLD)
        screen.blit(text, (W // 2 - text.get_width() // 2, 20))

    if current_room == "boss" and boss and boss["alive"]:
        draw_hp_bar(screen, W // 2 - 200, 20, 400, 16, boss["hp"], boss["max_hp"], RED)
        text = font.render("СЛАЙМ-КОРОЛЬ", True, WHITE)
        screen.blit(text, (W // 2 - text.get_width() // 2, 40))

# Информация
    info = font_small.render(f"Урон:{player_damage}  Ключи:{keys_count}  Комната:{current_room}", True, WHITE)
    screen.blit(info, (10, H - 55))

    if god_mode:
        text = font.render("GOD MODE", True, GOLD)
        screen.blit(text, (10, 10))

    if loot_msg_timer > 0:
        text = font_big.render(loot_msg, True, GOLD)
        screen.blit(text, (W // 2 - text.get_width() // 2, H // 2 - 50))

    if game_over:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        text = font_big.render("GAME OVER", True, RED)
        screen.blit(text, (W // 2 - text.get_width() // 2, H // 2 - 50))
        text2 = font.render("R — рестарт   ESC — выход", True, WHITE)
        screen.blit(text2, (W // 2 - text2.get_width() // 2, H // 2 + 10))

    if victory:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        text = font_big.render("ТЫ ВЫИГРАЛ!", True, GOLD)
        screen.blit(text, (W // 2 - text.get_width() // 2, H // 2 - 70))
        text2 = font.render("Слайм-Король повержен", True, WHITE)
        screen.blit(text2, (W // 2 - text2.get_width() // 2, H // 2 - 25))
        text3 = font.render("R — играть снова   ESC — выход", True, WHITE)
        screen.blit(text3, (W // 2 - text3.get_width() // 2, H // 2 + 25))

    hint = font_small.render(
        "WASD — движение   ПКМ — рывок   ЛКМ — атака   E — действие   O — god mode   R — рестарт   ESC — выход",
        True,
        (120, 120, 120),
    )
    screen.blit(hint, (W // 2 - hint.get_width() // 2, H - 12))

def draw_menu():
    screen.fill((8, 8, 12))

    start_button = pygame.Rect(W // 2 - 130, H // 2 - 20, 260, 55)
    exit_button = pygame.Rect(W // 2 - 130, H // 2 + 50, 260, 55)

    title = font_big.render("MEDIEVAL DUNGEON", True, GOLD)
    subtitle = font.render("Пиксельный dungeon crawler", True, WHITE)
    screen.blit(title, (W // 2 - title.get_width() // 2, H // 2 - 150))
    screen.blit(subtitle, (W // 2 - subtitle.get_width() // 2, H // 2 - 105))

    mouse_pos = pygame.mouse.get_pos()
    for rect, text in [(start_button, "НАЧАТЬ"), (exit_button, "ВЫХОД")]:
        hover = rect.collidepoint(mouse_pos)
        color = (95, 85, 55) if hover else (60, 60, 70)
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, GOLD, rect, 2, border_radius=8)
        label = font_big.render(text, True, WHITE)
        screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

    hint = font_small.render("Наведи мышкой и нажми ЛКМ", True, (150, 150, 150))
    screen.blit(hint, (W // 2 - hint.get_width() // 2, H // 2 + 130))

# запуск игры

reset_game()
clock = pygame.time.Clock()

while running:
    dt = clock.tick(144) / (1000 / 60)
    dt = min(dt, 3)

    mouse_x_screen, mouse_y_screen = pygame.mouse.get_pos()
    mouse_x = cam_x + mouse_x_screen / ZOOM
    mouse_y = cam_y + mouse_y_screen / ZOOM

    start_button = pygame.Rect(W // 2 - 130, H // 2 - 20, 260, 55)
    exit_button = pygame.Rect(W // 2 - 130, H // 2 + 50, 260, 55)

# события
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_r:
                reset_game()
                screen_mode = "game"
            if event.key == pygame.K_o and screen_mode == "game":
                god_mode = not god_mode
                if god_mode:
                    saved_damage = player_damage
                    player_damage = 10000
                    player_hp = player_max_hp
                    loot_msg = "GOD MODE ON"
                else:
                    player_damage = saved_damage
                    loot_msg = "GOD MODE OFF"
                loot_msg_timer = 120

# Меню
        if screen_mode == "menu":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_button.collidepoint(mouse_x_screen, mouse_y_screen):
                    screen_mode = "game"
                elif exit_button.collidepoint(mouse_x_screen, mouse_y_screen):
                    running = False
            continue

        if game_over or victory:
            continue

# Dash на ПКМ
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if dash_cooldown <= 0:
                px = player_x + PLAYER_SIZE // 2
                py = player_y + PLAYER_SIZE // 2
                angle = math.atan2(mouse_y - py, mouse_x - px)
                dash_time = DASH_TIME_MAX
                dash_cooldown = DASH_COOLDOWN_MAX
                dash_dx = math.cos(angle)
                dash_dy = math.sin(angle)

# Атака ЛКМ или пробел
        attack_pressed = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1) or (
            event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
        )
        if attack_pressed and attack_cooldown <= 0:
            handle_attack(mouse_x, mouse_y)

# Взаимодействие E
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            interact()

# логика
    if screen_mode == "game" and not game_over and not victory:
        update_player(dt, mouse_x, mouse_y)
        update_common_animations(dt)
        update_arena(dt)
        update_boss_room(dt)

        if player_hp <= 0:
            player_hp = 0
            game_over = True

# отрисовка
    if screen_mode == "menu":
        draw_menu()
    else:
        draw_game()

    pygame.display.flip()

pygame.quit()
