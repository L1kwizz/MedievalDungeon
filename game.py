import pygame
import math
import random
import os

try:
    import pytmx
except ImportError:
    print("Установи pytmx: py -3.11 -m pip install pytmx")
    raise

pygame.init()

info = pygame.display.Info()
W, H = info.current_w, info.current_h
screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
pygame.display.set_caption("Medieval Dungeon")

BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
GOLD   = (255, 215, 0)
RED    = (220, 50,  50)
GREEN  = (0,   200, 0)

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PACK = os.path.join(BASE_DIR, "assets")

TILED_TILE = 16
TILE       = 32
MAP_SCALE  = TILE / TILED_TILE

PLAYER_SIZE  = 48
PLAYER_SPEED = 2.8
DASH_SPEED   = 8
DASH_TIME    = 6
DASH_COOLDOWN = 45
TRAIL_LIFE   = 18
ATTACK_RANGE = 120

ZOOM   = 2
VIEW_W = int(W / ZOOM)
VIEW_H = int(H / ZOOM)
world_surf = pygame.Surface((VIEW_W, VIEW_H))

font       = pygame.font.SysFont(None, 22)
font_big   = pygame.font.SysFont(None, 40)
font_small = pygame.font.SysFont(None, 18)

# ---------- загрузка спрайтов ----------

def load_img(rel, size=None):
    img = pygame.image.load(os.path.join(PACK, rel)).convert_alpha()
    if size:
        img = pygame.transform.scale(img, size)
    return img

def load_frames(folder, name, count, size=48):
    frames = []
    for i in range(count):
        img = pygame.image.load(os.path.join(PACK, folder, f"{name}_f{i}.png")).convert_alpha()
        img = pygame.transform.scale(img, (size, size) if isinstance(size, int) else size)
        frames.append(img)
    return frames

def load_frames_rect(folder, name, count, size):
    frames = []
    for i in range(count):
        img = pygame.image.load(os.path.join(PACK, folder, f"{name}_f{i}.png")).convert_alpha()
        img = pygame.transform.scale(img, size)
        frames.append(img)
    return frames

knight_idle  = load_frames("heroes/knight",          "knight_idle_anim", 6)
knight_run   = load_frames("heroes/knight",          "knight_run_anim",  6)
goblin_idle  = load_frames("enemies/goblin",         "goblin_idle_anim", 6, 40)
goblin_run   = load_frames("enemies/goblin",         "goblin_run_anim",  6, 40)
slime_idle   = load_frames("enemies/slime",          "slime_idle_anim",  6, 40)
slime_run    = load_frames("enemies/slime",          "slime_run_anim",   6, 40)
bat_frames   = load_frames("enemies/flying creature","fly_anim",         4, 36)
torch_frames = load_frames_rect("props_itens",       "torch_anim",       6, (32,32))

slash_frames = []
for _i in range(3):
    _img = pygame.image.load(os.path.join(PACK,"effects (new)",f"slash_effect_anim_f{_i}.png")).convert_alpha()
    slash_frames.append(pygame.transform.scale(_img,(80,80)))

chest_closed_frames = load_frames_rect("props_itens","chest_closed_anim", 8, (32,32))
chest_open_img      = load_img("props_itens/chest_open.png", (32,32))
door_closed_img     = load_img("tiles/wall/door_closed.png",   (64,64))
door_open_frames    = load_frames_rect("tiles/wall","door_anim_opening", 14, (64,64))
door_open_img       = load_img("tiles/wall/door_fullyopen.png", (64,64))

# Босс-слайм — большой (x3)
BOSS_SIZE = PLAYER_SIZE * 3
boss_idle = load_frames("enemies/slime","slime_idle_anim", 6, BOSS_SIZE)
boss_run  = load_frames("enemies/slime","slime_run_anim",  6, BOSS_SIZE)

# ---------- типы обычных врагов ----------

ENEMY_TYPES = {
    "goblin": dict(idle=goblin_idle, run=goblin_run, size=40,
                   hp_min=75,  hp_max=120, spd_min=1.0, spd_max=2.0,
                   dmg=1, atk_cd=60,  windup=24, stop=38, atk_dist=48, kb=8),
    "slime":  dict(idle=slime_idle,  run=slime_run,  size=40,
                   hp_min=150, hp_max=200, spd_min=0.5, spd_max=0.9,
                   dmg=2, atk_cd=90,  windup=35, stop=35, atk_dist=45, kb=12),
    "bat":    dict(idle=bat_frames,  run=bat_frames,  size=36,
                   hp_min=30,  hp_max=50,  spd_min=2.8, spd_max=3.8,
                   dmg=1, atk_cd=30,  windup=10, stop=30, atk_dist=40, kb=4),
}

# ---------- загрузка карт ----------

class Room:
    def __init__(self, name, fname):
        self.name = name
        path = os.path.join(BASE_DIR,"maps", fname)
        self.tmx = pytmx.load_pygame(path)
        self.world_w = int(self.tmx.width  * TILE)
        self.world_h = int(self.tmx.height * TILE)
        self.collision_rects = self._make_collision()
        self.objects         = self._read_objects()

    def _read_objects(self):
        objs = {}
        for layer in self.tmx.layers:
            if not isinstance(layer, pytmx.TiledObjectGroup):
                continue
            key = layer.name.lower()
            for obj in layer:
                r = pygame.Rect(int(obj.x*MAP_SCALE), int(obj.y*MAP_SCALE),
                                max(1,int((obj.width or 16)*MAP_SCALE)),
                                max(1,int((obj.height or 16)*MAP_SCALE)))
                objs.setdefault(key,[]).append(r)
        return objs

    def _make_collision(self):
        rects = []
        for layer in self.tmx.layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            if "collision" not in layer.name.lower() and "collisium" not in layer.name.lower():
                continue
            for x,y,gid in layer:
                if gid:
                    rects.append(pygame.Rect(x*TILE, y*TILE, TILE, TILE))
        return rects

    def first_obj(self, *names):
        for n in names:
            lst = self.objects.get(n.lower(),[])
            if lst: return lst[0]
        return None

    def all_obj(self, *names):
        res = []
        for n in names:
            res.extend(self.objects.get(n.lower(),[]))
        return res

    def draw(self, cam_x, cam_y):
        for layer in self.tmx.visible_layers:
            if not isinstance(layer, pytmx.TiledTileLayer):
                continue
            lname = layer.name.lower()
            if "collision" in lname or "collisium" in lname:
                continue
            for x,y,gid in layer:
                if not gid: continue
                tile = self.tmx.get_tile_image_by_gid(gid)
                if tile is None: continue
                world_surf.blit(pygame.transform.scale(tile,(TILE,TILE)),
                                (x*TILE - cam_x, y*TILE - cam_y))

rooms = {
    "hub":      Room("hub",      "room11.tmx"),
    "corridor": Room("corridor", "koridor.tmx"),
    "arena":    Room("arena",    "room1.tmx"),
    "boss":     Room("boss",     "boss.tmx"),
}

# Кешируем важные rect-ы
hub_chest_rect = rooms["hub"].first_obj("chest") or pygame.Rect(200,200,32,32)
hub_door_rect  = rooms["hub"].first_obj("door")  or pygame.Rect(200,400,64,64)

arena_chest_rect  = rooms["arena"].first_obj("chest") or pygame.Rect(400,400,32,32)
arena_door_in     = rooms["arena"].first_obj("door in")
arena_door_exit   = rooms["arena"].first_obj("door exit")

corridor_door_top = rooms["corridor"].first_obj("дверь верхняя","door top","door")
corridor_door_bot = rooms["corridor"].first_obj("дверь нижняя","door bottom","door exit")

boss_door_in   = rooms["boss"].first_obj("door in")
boss_spawn_pos = rooms["boss"].first_obj("player")
boss_spawn_rect= rooms["boss"].first_obj("boss") or pygame.Rect(400,400,32,32)

# ---------- волны арены ----------
# 4 волны, после каждой сундук на 10 сек
# Лут: волна1→+1hp+5dmg, волна2→+1hp+10dmg, волна3→+1hp+10dmg, волна4→+1hp+10dmg+ключ
WAVE_LOOT = [
    dict(hp=1, dmg=5,  key=0, msg="+1 сердце, +5 урона!"),
    dict(hp=1, dmg=10, key=0, msg="+1 сердце, +10 урона!"),
    dict(hp=1, dmg=10, key=0, msg="+1 сердце, +10 урона!"),
    dict(hp=1, dmg=10, key=1, msg="+1 сердце, +10 урона, КЛЮЧ!"),
]

def make_wave(wave_num):
    """Генерируем 7-10 случайных врагов вокруг центра арены"""
    count = random.randint(7, 10)
    cx = rooms["arena"].world_w // 2
    cy = rooms["arena"].world_h // 2
    enemies = []
    etype_pool = ["goblin","goblin","goblin","slime","bat"]
    for _ in range(count):
        etype = random.choice(etype_pool)
        t = ENEMY_TYPES[etype]
        angle = random.uniform(0, 2*math.pi)
        dist  = random.randint(120, 250)
        x = max(80, min(cx + math.cos(angle)*dist, rooms["arena"].world_w - 80))
        y = max(80, min(cy + math.sin(angle)*dist, rooms["arena"].world_h - 80))
        hp = random.randint(t["hp_min"], t["hp_max"])
        enemies.append({
            "type":etype,"x":float(x),"y":float(y),
            "hp":hp,"max_hp":hp,
            "speed":random.uniform(t["spd_min"],t["spd_max"]),
            "size":t["size"],"alive":True,
            "anim_frame":0,"anim_timer":0,"dir":1,
            "knockback_x":0.0,"knockback_y":0.0,
            "hit_flash":0,"attacking":False,
            "attack_cooldown":random.randint(0,30),"attack_windup":0,
        })
    return enemies

# ---------- вспомогательные функции ----------

def animate(frames, timer, frame, speed=8, dt=1):
    timer += dt
    while timer >= speed:
        timer -= speed
        frame = (frame+1) % len(frames)
    return timer, frame

def player_rect_at(x, y):
    return pygame.Rect(int(x)+12, int(y)+16, PLAYER_SIZE-24, PLAYER_SIZE-20)

def near(rect, px, py, dist=70):
    return math.hypot(px+PLAYER_SIZE//2 - rect.centerx,
                      py+PLAYER_SIZE//2 - rect.centery) < dist

def clamp_camera(g):
    room = rooms[g["room"]]
    if room.world_w <= VIEW_W:
        g["cam_x"] = -(VIEW_W - room.world_w)/2
    else:
        g["cam_x"] = max(0, min(g["cam_x"], room.world_w - VIEW_W))
    if room.world_h <= VIEW_H:
        g["cam_y"] = -(VIEW_H - room.world_h)/2
    else:
        g["cam_y"] = max(0, min(g["cam_y"], room.world_h - VIEW_H))

def is_blocked(x, y, g):
    room = rooms[g["room"]]
    rect = player_rect_at(x, y)
    if rect.left<0 or rect.top<0 or rect.right>room.world_w or rect.bottom>room.world_h:
        return True
    for blk in room.collision_rects:
        # Открытая дверь хаба — пропускаем коллизию в её зоне
        if g["room"]=="hub" and g["hub_door"]=="open" and blk.colliderect(hub_door_rect.inflate(16,16)):
            continue
        # Коридор — пропускаем верхний проход и нижний проход к арене
        if g["room"]=="corridor":
            top = pygame.Rect(room.world_w//2-40, 0, 80, 60)
            bot = pygame.Rect(room.world_w//2-50, room.world_h-70, 100, 80)
            if blk.colliderect(top) or blk.colliderect(bot):
                continue
        # Арена — если дверь к боссу уже доступна, не держим невидимую стену в её зоне
        if g["room"]=="arena" and arena_door_exit and (g["keys"]>0 or g["arena_wave"]>=5):
            if blk.colliderect(arena_door_exit.inflate(20,20)):
                continue
        # Босс-комната — пропускаем верхний вход, чтобы игрок не застревал на пороге
        if g["room"]=="boss":
            top = pygame.Rect(room.world_w//2-60, 0, 120, 80)
            if blk.colliderect(top):
                continue
        if rect.colliderect(blk):
            return True
    # Сундук хаба
    if g["room"]=="hub" and not g["hub_chest_opened"] and rect.colliderect(hub_chest_rect.inflate(-4,-4)):
        return True
    # Дверь хаба
    if g["room"]=="hub" and g["hub_door"]!="open" and rect.colliderect(hub_door_rect.inflate(-4,-4)):
        return True
    # Сундук арены (только пока не открыт)
    if g["room"]=="arena" and not g["arena_chest_open"] and rect.colliderect(arena_chest_rect.inflate(-4,-4)):
        return True
    # Выходная дверь арены закрыта, пока не пройдены волны и нет ключа
    if g["room"]=="arena" and arena_door_exit and (g["keys"]<=0 and g["arena_wave"]<5):
        if rect.colliderect(arena_door_exit.inflate(-4,-4)):
            return True
    return False

def move_with_collision(g, move_x, move_y, dt):
    nx = g["player_x"] + move_x*dt
    if not is_blocked(nx, g["player_y"], g):
        g["player_x"] = nx
    ny = g["player_y"] + move_y*dt
    if not is_blocked(g["player_x"], ny, g):
        g["player_y"] = ny

def switch_room(g, room_name, x, y):
    g["room"] = room_name
    g["player_x"] = float(x)
    g["player_y"] = float(y)
    g["dash_time"] = 0
    g["dash_trails"] = []
    g["cam_x"] = g["cam_y"] = 0.0
    clamp_camera(g)

def check_transitions(g):
    rect = player_rect_at(g["player_x"], g["player_y"])

    if g["room"] == "hub" and g["hub_door"] == "open":
        zone = hub_door_rect.inflate(20,28)
        if rect.colliderect(zone) and rect.centery >= hub_door_rect.centery:
            cor = rooms["corridor"]
            switch_room(g,"corridor", cor.world_w/2 - PLAYER_SIZE/2, 40)

    elif g["room"] == "corridor":
        if rect.top <= 32:
            hub = rooms["hub"]
            switch_room(g,"hub", hub_door_rect.centerx - PLAYER_SIZE/2, hub.world_h - PLAYER_SIZE - 10)
        arena = rooms["arena"]
        cor = rooms["corridor"]
        if rect.bottom >= cor.world_h - 32:
                player_obj = arena.first_obj("player")
                sx = player_obj.centerx - PLAYER_SIZE//2 if player_obj else arena.world_w//2 - PLAYER_SIZE//2
                sy = player_obj.centery  - PLAYER_SIZE//2 if player_obj else 60
                switch_room(g,"arena", sx, sy)
                if g["arena_wave"] == 0:
                    g["arena_wave"] = 1
                    g["arena_waiting_wave"] = 1
                    g["arena_spawn_timer"] = 60 * 5  # 5 секунд перед первой волной
                    g["arena_enemies"] = []
                    g["arena_chest_open"] = False
                    g["arena_chest_looted"] = False
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = "Приготовься..."
                    g["loot_msg_timer"] = 120

    elif g["room"] == "arena":
        if arena_door_in and rect.top <= 8:
            cor = rooms["corridor"]
            switch_room(g,"corridor", cor.world_w/2 - PLAYER_SIZE/2, cor.world_h - PLAYER_SIZE - 60)
        # Выход в комнату босса: после 4 волн и ключа. Без проверки "с какой стороны",
        # потому что в Tiled дверь может стоять и сверху, и снизу, а мы не хотим ловить невидимую бюрократию.
        if arena_door_exit and (g["keys"] > 0 or g["arena_wave"] >= 5):
            if rect.colliderect(arena_door_exit.inflate(28,28)):
                if g["keys"] > 0:
                    g["keys"] -= 1
                bsp = boss_spawn_pos
                sx = bsp.centerx - PLAYER_SIZE//2 if bsp else rooms["boss"].world_w//2 - PLAYER_SIZE//2
                sy = bsp.centery  - PLAYER_SIZE//2 if bsp else 60
                switch_room(g,"boss", sx, sy)
                g["player_hp"] = g["player_max_hp"]
                if not g["boss_spawned"] and g["boss"] is None:
                    g["boss_spawn_timer"] = 60 * 5  # 5 секунд перед боссом
                    g["boss_minions"] = []
                    g["boss_summon_timer"] = 60 * 5
                    g["loot_msg"] = "Босс появится через 5 секунд..."
                    g["loot_msg_timer"] = 180

    elif g["room"] == "boss":
        if boss_door_in and rect.top <= 8:
            arena = rooms["arena"]
            switch_room(g,"arena", arena.world_w//2 - PLAYER_SIZE//2, arena.world_h - PLAYER_SIZE - 60)

# ---------- boss ----------

def make_boss():
    r = boss_spawn_rect
    return {
        "x": float(r.centerx - BOSS_SIZE//2),
        "y": float(r.centery  - BOSS_SIZE//2),
        "hp": 2000, "max_hp": 2000,
        "speed": 1.25, "alive": True,
        "anim_frame":0,"anim_timer":0,"dir":1,
        "knockback_x":0.0,"knockback_y":0.0,
        "hit_flash":0,"attacking":False,
        "attack_cooldown":0,"attack_windup":0,
    }

def make_boss_minion(x, y):
    """Маленький слайм, которого призывает босс."""
    t = ENEMY_TYPES["slime"]
    return {
        "type":"slime",
        "x":float(x),"y":float(y),
        "hp":200,"max_hp":200,
        "speed":1.05,
        "size":t["size"],"alive":True,
        "anim_frame":0,"anim_timer":0,"dir":1,
        "knockback_x":0.0,"knockback_y":0.0,
        "hit_flash":0,"attacking":False,
        "attack_cooldown":random.randint(0,30),"attack_windup":0,
    }

# ---------- reset ----------

def reset_game():
    hub = rooms["hub"]
    return {
        "room": "hub",
        "player_x": float(hub.world_w//2 - PLAYER_SIZE//2),
        "player_y": float(hub.world_h//2 - PLAYER_SIZE//2 + 40),
        "player_hp":1,"player_max_hp":1,
        "player_dir":1,"player_damage":5,
        "saved_damage":5,
        "god_mode":False,
        "screen":"menu",  # menu/game
        "player_anim_frame":0,"player_anim_timer":0,
        "player_moving":False,
        "cam_x":0.0,"cam_y":0.0,
        "keys":0,

        # Hub
        "hub_chest_opened":False,
        "hub_chest_frame":0,"hub_chest_timer":0,
        "hub_door":"closed",  # closed/opening/open
        "hub_door_frame":0,"hub_door_timer":0,

        # Arena
        "arena_wave":0,          # 0=не начата, 1-4=волна, 5=все волны пройдены
        "arena_enemies":[],
        "arena_chest_open":False,
        "arena_chest_looted":False,
        "arena_chest_frame":0,"arena_chest_timer":0,
        "arena_chest_countdown":0,  # таймер 10 сек
        "arena_spawn_timer":0,      # задержка перед появлением волны
        "arena_waiting_wave":0,     # номер волны, которая появится после таймера

        # Boss
        "boss_spawned":False,
        "boss_spawn_timer":0,       # задержка перед появлением босса
        "boss": None,
        "boss_minions":[],         # мини-слаймы босса
        "boss_summon_timer":60*5,  # раз в 5 секунд призывает миников
        "boss_dead":False,

        # Общие
        "torch_frame":0,"torch_timer":0,
        "attack_cooldown":0,
        "slash_active":False,"slash_frame":0,
        "slash_timer":0,"slash_x":0.0,"slash_y":0.0,"slash_angle":0.0,
        "dash_cooldown":0,"dash_time":0,"dash_dx":0.0,"dash_dy":0.0,"dash_trails":[],
        "player_hit_flash":0,"player_knockback_x":0.0,"player_knockback_y":0.0,
        "loot_msg":"","loot_msg_timer":0,
        "game_over":False,"victory":False,
    }

# ---------- UI helpers ----------

def draw_heart(surface, x, y, filled=True, scale=2):
    color   = WHITE if filled else (70,80,85)
    pattern = ["01100110","11111111","11111111","01111110","00111100","00011000"]
    pygame.draw.rect(surface,BLACK,(x-scale,y-scale,8*scale+2*scale,6*scale+2*scale))
    for row,line in enumerate(pattern):
        for col,px in enumerate(line):
            if px=="1":
                pygame.draw.rect(surface,color,(x+col*scale,y+row*scale,scale,scale))

def draw_hp_bar(surface, x, y, w, h, cur, mx, color=RED):
    pygame.draw.rect(surface,(60,60,60),(x,y,w,h))
    if mx>0:
        pygame.draw.rect(surface,color,(x,y,int(w*cur/mx),h))
    pygame.draw.rect(surface,WHITE,(x,y,w,h),1)

# ---------- отрисовка объектов ----------

def draw_chest_obj(cam_x, cam_y, rect, opened, frame):
    img = chest_open_img if opened else chest_closed_frames[frame % len(chest_closed_frames)]
    img = pygame.transform.scale(img, (rect.width, rect.height))
    world_surf.blit(img, (rect.x - cam_x, rect.y - cam_y))

def draw_door(cam_x, cam_y, rect, state, frame):
    if state == "closed":
        img = pygame.transform.scale(door_closed_img,(rect.width,rect.height))
    elif state == "opening":
        idx = min(frame, len(door_open_frames)-1)
        img = pygame.transform.scale(door_open_frames[idx],(rect.width,rect.height))
    else:
        img = pygame.transform.scale(door_open_img,(rect.width,rect.height))
    world_surf.blit(img,(rect.x-cam_x, rect.y-cam_y))

def draw_enemy(cam_x, cam_y, enemy):
    t = ENEMY_TYPES[enemy["type"]]
    ex = enemy["x"] - cam_x
    ey = enemy["y"] - cam_y
    ef = (t["idle"] if enemy["attacking"] else t["run"])
    frame = ef[enemy["anim_frame"] % len(ef)]
    if enemy["dir"] == -1:
        frame = pygame.transform.flip(frame, True, False)
    if enemy["hit_flash"] > 0:
        w = frame.copy(); w.fill((255,255,255),special_flags=pygame.BLEND_RGB_MAX)
        world_surf.blit(w,(ex,ey))
    elif enemy.get("attack_windup",0) > 0:
        w = frame.copy(); w.fill((80,80,80),special_flags=pygame.BLEND_RGB_ADD)
        world_surf.blit(w,(ex,ey))
    else:
        world_surf.blit(frame,(ex,ey))

def draw_boss_entity(cam_x, cam_y, boss):
    ef = boss_idle if boss["attacking"] else boss_run
    frame = ef[boss["anim_frame"] % len(ef)]
    if boss["dir"] == -1:
        frame = pygame.transform.flip(frame, True, False)
    bx = boss["x"]-cam_x; by = boss["y"]-cam_y
    if boss["hit_flash"] > 0:
        w = frame.copy(); w.fill((255,255,255),special_flags=pygame.BLEND_RGB_MAX)
        world_surf.blit(w,(bx,by))
    elif boss.get("attack_windup",0) > 0:
        w = frame.copy(); w.fill((80,80,80),special_flags=pygame.BLEND_RGB_ADD)
        world_surf.blit(w,(bx,by))
    else:
        world_surf.blit(frame,(bx,by))
    # HP bar под боссом
    bw = BOSS_SIZE
    draw_hp_bar(world_surf, int(bx), int(by)-12, bw, 8, boss["hp"], boss["max_hp"], RED)

def update_enemy(enemy, g, dt):
    """Обновляет одного обычного врага."""
    t = ENEMY_TYPES[enemy["type"]]
    enemy["attack_cooldown"] = max(0, enemy["attack_cooldown"] - dt)
    enemy["attack_windup"]   = max(0, enemy.get("attack_windup",0) - dt)

    if abs(enemy["knockback_x"])>0.1 or abs(enemy["knockback_y"])>0.1:
        enemy["attacking"] = False
        enemy["x"] = max(80, min(enemy["x"]+enemy["knockback_x"]*dt, rooms[g["room"]].world_w-80))
        enemy["y"] = max(80, min(enemy["y"]+enemy["knockback_y"]*dt, rooms[g["room"]].world_h-80))
        decay = 0.7**dt
        enemy["knockback_x"] *= decay; enemy["knockback_y"] *= decay
    else:
        ecx = enemy["x"]+enemy["size"]//2; ecy = enemy["y"]+enemy["size"]//2
        pcx = g["player_x"]+PLAYER_SIZE//2; pcy = g["player_y"]+PLAYER_SIZE//2
        dx = pcx-ecx; dy = pcy-ecy
        dist = math.hypot(dx,dy)
        enemy["attacking"] = False
        if dist > t["stop"]:
            enemy["x"] += (dx/dist)*enemy["speed"]*dt
            enemy["y"] += (dy/dist)*enemy["speed"]*dt
            enemy["dir"] = 1 if dx>0 else -1
            enemy["attack_windup"] = 0
        else:
            enemy["attacking"] = True
            enemy["dir"] = 1 if dx>0 else -1
            if dist < t["atk_dist"] and enemy["attack_cooldown"] <= 0:
                if enemy.get("attack_windup",0) <= 0:
                    enemy["attack_windup"] = t["windup"]
                elif enemy["attack_windup"] <= dt:
                    if not g.get("god_mode", False):
                        g["player_hp"] -= t["dmg"]
                        g["player_hit_flash"] = 10
                    else:
                        g["player_hit_flash"] = 4
                    enemy["attack_cooldown"] = t["atk_cd"]
                    enemy["attack_windup"] = 0
                    if dist > 0:
                        g["player_knockback_x"] = (dx/dist)*4
                        g["player_knockback_y"] = (dy/dist)*4

    if enemy["hit_flash"] > 0:
        enemy["hit_flash"] = max(0, enemy["hit_flash"]-dt)

    ef = ENEMY_TYPES[enemy["type"]]["idle"] if enemy["attacking"] else ENEMY_TYPES[enemy["type"]]["run"]
    enemy["anim_timer"], enemy["anim_frame"] = animate(ef, enemy["anim_timer"], enemy["anim_frame"], dt=dt)

def update_boss(boss, g, dt):
    boss["attack_cooldown"] = max(0, boss["attack_cooldown"]-dt)
    boss["attack_windup"]   = max(0, boss.get("attack_windup",0)-dt)

    if abs(boss["knockback_x"])>0.1 or abs(boss["knockback_y"])>0.1:
        boss["x"] = max(80, min(boss["x"]+boss["knockback_x"]*dt, rooms["boss"].world_w-BOSS_SIZE-80))
        boss["y"] = max(80, min(boss["y"]+boss["knockback_y"]*dt, rooms["boss"].world_h-BOSS_SIZE-80))
        decay = 0.7**dt
        boss["knockback_x"] *= decay; boss["knockback_y"] *= decay
    else:
        bcx = boss["x"]+BOSS_SIZE//2; bcy = boss["y"]+BOSS_SIZE//2
        pcx = g["player_x"]+PLAYER_SIZE//2; pcy = g["player_y"]+PLAYER_SIZE//2
        dx = pcx-bcx; dy = pcy-bcy
        dist = math.hypot(dx,dy)
        boss["attacking"] = False
        stop = 75; atk_dist = 105
        if dist > stop:
            boss["x"] += (dx/dist)*boss["speed"]*dt
            boss["y"] += (dy/dist)*boss["speed"]*dt
            boss["dir"] = 1 if dx>0 else -1
            boss["attack_windup"] = 0
        else:
            boss["attacking"] = True
            boss["dir"] = 1 if dx>0 else -1
            if dist < atk_dist and boss["attack_cooldown"] <= 0:
                if boss.get("attack_windup",0) <= 0:
                    boss["attack_windup"] = 40
                elif boss["attack_windup"] <= dt:
                    if not g.get("god_mode", False):
                        g["player_hp"] -= 3
                        g["player_hit_flash"] = 10
                    else:
                        g["player_hit_flash"] = 4
                    boss["attack_cooldown"] = 60
                    boss["attack_windup"] = 0
                    if dist > 0:
                        g["player_knockback_x"] = (dx/dist)*6
                        g["player_knockback_y"] = (dy/dist)*6

    if boss["hit_flash"] > 0:
        boss["hit_flash"] = max(0, boss["hit_flash"]-dt)

    ef = boss_idle if boss["attacking"] else boss_run
    boss["anim_timer"], boss["anim_frame"] = animate(ef, boss["anim_timer"], boss["anim_frame"], dt=dt)

# ---------- MAIN ----------

g = reset_game()
clamp_camera(g)
clock = pygame.time.Clock()
running = True

while running:
    dt = clock.tick(144) / (1000/60)
    dt = min(dt, 3)

    mx_s, my_s = pygame.mouse.get_pos()
    mx = g["cam_x"] + mx_s / ZOOM
    my = g["cam_y"] + my_s / ZOOM

    start_button = pygame.Rect(W//2 - 130, H//2 - 20, 260, 55)
    exit_button  = pygame.Rect(W//2 - 130, H//2 + 50, 260, 55)

    # --- события ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_r:
                old_screen = g.get("screen", "game")
                g = reset_game(); clamp_camera(g)
                g["screen"] = old_screen if old_screen == "menu" else "game"
            if event.key == pygame.K_o and g.get("screen") == "game":
                g["god_mode"] = not g["god_mode"]
                if g["god_mode"]:
                    g["saved_damage"] = g["player_damage"]
                    g["player_damage"] = 10000
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = "GOD MODE ON"
                else:
                    g["player_damage"] = g.get("saved_damage", 5)
                    g["loot_msg"] = "GOD MODE OFF"
                g["loot_msg_timer"] = 120

        if g.get("screen") == "menu":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_button.collidepoint(mx_s, my_s):
                    g["screen"] = "game"
                elif exit_button.collidepoint(mx_s, my_s):
                    running = False
            continue

        if g["game_over"] or g["victory"]:
            continue

        # Рывок ПКМ
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if g["dash_cooldown"] <= 0:
                px = g["player_x"]+PLAYER_SIZE//2; py = g["player_y"]+PLAYER_SIZE//2
                a = math.atan2(my-py, mx-px)
                g["dash_time"]=DASH_TIME; g["dash_cooldown"]=DASH_COOLDOWN
                g["dash_dx"]=math.cos(a); g["dash_dy"]=math.sin(a)

        # Атака ЛКМ / Пробел
        attack = (event.type==pygame.MOUSEBUTTONDOWN and event.button==1) or \
                 (event.type==pygame.KEYDOWN and event.key==pygame.K_SPACE)

        if attack and g["attack_cooldown"] <= 0:
            g["attack_cooldown"] = 30
            px = g["player_x"]+PLAYER_SIZE//2; py = g["player_y"]+PLAYER_SIZE//2
            angle = math.atan2(my-py, mx-px)
            g["slash_active"]=True; g["slash_frame"]=0; g["slash_timer"]=0
            g["slash_x"]=px+math.cos(angle)*75-40
            g["slash_y"]=py+math.sin(angle)*75-40
            g["slash_angle"]=math.degrees(angle)

            # Попадание по обычным врагам (арена)
            if g["room"] == "arena":
                for en in g["arena_enemies"]:
                    if not en["alive"]: continue
                    dx=en["x"]-px; dy=en["y"]-py
                    dist=math.hypot(dx,dy)
                    if dist < ATTACK_RANGE:
                        ea = math.atan2(dy,dx)
                        diff = abs(math.atan2(math.sin(ea-angle),math.cos(ea-angle)))
                        if diff < math.pi/2:
                            en["hp"] -= g["player_damage"]
                            en["hit_flash"] = 10
                            if dist>0:
                                en["knockback_x"]=(dx/dist)*8
                                en["knockback_y"]=(dy/dist)*8
                            if en["hp"] <= 0: en["alive"]=False

            # Попадание по мини-слаймам и боссу
            if g["room"]=="boss":
                for en in g.get("boss_minions", []):
                    if not en["alive"]:
                        continue
                    dx=en["x"]-px; dy=en["y"]-py
                    dist=math.hypot(dx,dy)
                    if dist < ATTACK_RANGE:
                        ea=math.atan2(dy,dx)
                        diff=abs(math.atan2(math.sin(ea-angle),math.cos(ea-angle)))
                        if diff < math.pi/2:
                            en["hp"] -= g["player_damage"]
                            en["hit_flash"] = 10
                            if dist>0:
                                en["knockback_x"]=(dx/dist)*8
                                en["knockback_y"]=(dy/dist)*8
                            if en["hp"] <= 0:
                                en["alive"] = False

                if g["boss"] and g["boss"]["alive"]:
                    boss=g["boss"]
                    dx=boss["x"]+BOSS_SIZE//2-px; dy=boss["y"]+BOSS_SIZE//2-py
                    dist=math.hypot(dx,dy)
                    if dist < ATTACK_RANGE+BOSS_SIZE//2:
                        ea=math.atan2(dy,dx)
                        diff=abs(math.atan2(math.sin(ea-angle),math.cos(ea-angle)))
                        if diff < math.pi/2:
                            boss["hp"] -= g["player_damage"]
                            boss["hit_flash"]=10
                            if dist>0:
                                boss["knockback_x"]=(dx/dist)*4
                                boss["knockback_y"]=(dy/dist)*4
                            if boss["hp"]<=0:
                                boss["alive"]=False
                                g["boss_dead"]=True
                                g["victory"]=True

        # Взаимодействие E
        if event.type==pygame.KEYDOWN and event.key==pygame.K_e:
            # Сундук хаба
            if g["room"]=="hub" and not g["hub_chest_opened"] and near(hub_chest_rect,g["player_x"],g["player_y"]):
                g["hub_chest_opened"]=True
                g["player_max_hp"]+=3; g["player_hp"]=g["player_max_hp"]
                g["player_damage"]+=20; g["keys"]+=1
                g["loot_msg"]="+3 сердца, +20 урона, ключ!"; g["loot_msg_timer"]=180

            # Дверь хаба
            elif g["room"]=="hub" and g["hub_door"]=="closed" and near(hub_door_rect,g["player_x"],g["player_y"],90):
                if g["keys"]>0:
                    g["keys"]-=1; g["hub_door"]="opening"
                    g["hub_door_frame"]=0; g["hub_door_timer"]=0
                    g["loot_msg"]="Дверь открывается..."; g["loot_msg_timer"]=120
                else:
                    g["loot_msg"]="Нужен ключ!"; g["loot_msg_timer"]=90

            # Сундук арены (открывается только после волны)
            elif g["room"]=="arena" and g["arena_chest_open"] and not g["arena_chest_looted"]:
                if near(arena_chest_rect,g["player_x"],g["player_y"],80):
                    wave_idx = g["arena_wave"]-1
                    if 0 <= wave_idx < len(WAVE_LOOT):
                        loot = WAVE_LOOT[wave_idx]
                        g["player_max_hp"] += loot["hp"]
                        # Лут оставляем прежним, но после сундука полностью лечим игрока
                        g["player_hp"] = g["player_max_hp"]
                        g["player_damage"] += loot["dmg"]
                        g["keys"] += loot["key"]
                        g["loot_msg"] = loot["msg"]
                        g["loot_msg_timer"] = 200
                    g["arena_chest_looted"] = True
                    g["arena_chest_open"]   = False

    # --- логика ---
    if g.get("screen") == "game" and not g["game_over"] and not g["victory"]:

        # Движение
        keys_held = pygame.key.get_pressed()
        dx_p=dy_p=0; moving=False
        if keys_held[pygame.K_w] or keys_held[pygame.K_UP]:    dy_p=-1; moving=True
        if keys_held[pygame.K_s] or keys_held[pygame.K_DOWN]:  dy_p= 1; moving=True
        if keys_held[pygame.K_a] or keys_held[pygame.K_LEFT]:  dx_p=-1; moving=True
        if keys_held[pygame.K_d] or keys_held[pygame.K_RIGHT]: dx_p= 1; moving=True
        if dx_p and dy_p: dx_p*=0.707; dy_p*=0.707

        move_x = dx_p*PLAYER_SPEED; move_y = dy_p*PLAYER_SPEED

        if g["dash_time"]>0:
            move_x+=g["dash_dx"]*DASH_SPEED; move_y+=g["dash_dy"]*DASH_SPEED
            g["dash_time"]=max(0,g["dash_time"]-dt)
            g["dash_trails"].append({"x":g["player_x"],"y":g["player_y"],"dir":g["player_dir"],"life":TRAIL_LIFE})
        g["dash_cooldown"]=max(0,g["dash_cooldown"]-dt)
        for tr in g["dash_trails"]: tr["life"]-=dt
        g["dash_trails"]=[tr for tr in g["dash_trails"] if tr["life"]>0]

        if abs(g["player_knockback_x"])>0.05 or abs(g["player_knockback_y"])>0.05:
            move_x+=g["player_knockback_x"]; move_y+=g["player_knockback_y"]
            dec=0.72**dt; g["player_knockback_x"]*=dec; g["player_knockback_y"]*=dec

        move_with_collision(g, move_x, move_y, dt)
        check_transitions(g)
        g["player_moving"] = moving

        # Камера
        room_obj = rooms[g["room"]]
        tx = g["player_x"]-VIEW_W//2+PLAYER_SIZE//2
        ty = g["player_y"]-VIEW_H//2+PLAYER_SIZE//2
        sm = 1-(1-0.1)**dt
        g["cam_x"]+=(tx-g["cam_x"])*sm; g["cam_y"]+=(ty-g["cam_y"])*sm
        clamp_camera(g)

        px = g["player_x"]+PLAYER_SIZE//2; py = g["player_y"]+PLAYER_SIZE//2
        g["player_dir"] = 1 if mx>=px else -1

        # Анимация игрока
        fr = knight_run if moving else knight_idle
        g["player_anim_timer"],g["player_anim_frame"] = animate(fr,g["player_anim_timer"],g["player_anim_frame"],dt=dt)

        # Факелы
        g["torch_timer"],g["torch_frame"] = animate(torch_frames,g["torch_timer"],g["torch_frame"],speed=8,dt=dt)

        # Сундук хаба
        if g["room"]=="hub" and not g["hub_chest_opened"]:
            g["hub_chest_timer"],g["hub_chest_frame"] = animate(chest_closed_frames,g["hub_chest_timer"],g["hub_chest_frame"],speed=10,dt=dt)

        # Дверь хаба
        if g["hub_door"]=="opening":
            g["hub_door_timer"]+=dt
            if g["hub_door_timer"]>=4:
                g["hub_door_timer"]=0; g["hub_door_frame"]+=1
                if g["hub_door_frame"]>=len(door_open_frames): g["hub_door"]="open"

        # Slash
        if g["slash_active"]:
            g["slash_timer"]+=dt
            if g["slash_timer"]>=5:
                g["slash_timer"]=0; g["slash_frame"]+=1
                if g["slash_frame"]>=len(slash_frames): g["slash_active"]=False

        # Таймеры
        g["attack_cooldown"]=max(0,g["attack_cooldown"]-dt)
        g["loot_msg_timer"]=max(0,g["loot_msg_timer"]-dt)
        g["player_hit_flash"]=max(0,g["player_hit_flash"]-dt)

        # === Арена: логика волн ===
        if g["room"]=="arena" and g["arena_wave"]>0:
            # Если ждём новую волну — показываем паузу и спавним врагов только после таймера
            if g["arena_spawn_timer"] > 0:
                g["arena_spawn_timer"] = max(0, g["arena_spawn_timer"] - dt)
                if g["arena_spawn_timer"] <= 0 and g["arena_waiting_wave"] > 0:
                    g["arena_wave"] = g["arena_waiting_wave"]
                    g["arena_enemies"] = make_wave(g["arena_wave"])
                    g["arena_waiting_wave"] = 0
                    g["arena_chest_open"] = False
                    g["arena_chest_looted"] = False
                    # Перед началом каждой волны лечим на максимум
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = f"Волна {g['arena_wave']}!"
                    g["loot_msg_timer"] = 90

            alive = [e for e in g["arena_enemies"] if e["alive"]]

            # Обновляем врагов только когда не ждём таймер волны
            if g["arena_spawn_timer"] <= 0:
                for en in g["arena_enemies"]:
                    if en["alive"]:
                        update_enemy(en,g,dt)

            # Волна зачищена — появляется сундук
            if g["arena_spawn_timer"] <= 0 and g["arena_enemies"] and not alive and not g["arena_chest_open"] and not g["arena_chest_looted"]:
                if g["arena_wave"] <= 4:
                    g["arena_chest_open"] = True
                    g["arena_chest_looted"] = False
                    g["arena_chest_countdown"] = 60*10  # 10 секунд

            # Таймер сундука арены
            if g["arena_chest_open"] and not g["arena_chest_looted"]:
                g["arena_chest_timer"],g["arena_chest_frame"] = animate(
                    chest_closed_frames,g["arena_chest_timer"],g["arena_chest_frame"],speed=10,dt=dt)
                g["arena_chest_countdown"] = max(0,g["arena_chest_countdown"]-dt)
                if g["arena_chest_countdown"] <= 0:
                    # Время вышло — пропустили сундук, но всё равно лечим перед следующей волной позже
                    g["arena_chest_open"] = False
                    g["arena_chest_looted"] = True

            # Если залутали или пропустили сундук → следующая волна через 5 секунд
            if g["arena_chest_looted"] and not alive and g["arena_spawn_timer"] <= 0:
                if g["arena_wave"] < 4:
                    next_wave = g["arena_wave"] + 1
                    g["arena_waiting_wave"] = next_wave
                    g["arena_spawn_timer"] = 60 * 5
                    g["arena_enemies"] = []
                    g["arena_chest_looted"] = False
                    g["arena_chest_open"] = False
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = "Следующая волна через 5 секунд..."
                    g["loot_msg_timer"] = 180
                elif g["arena_wave"] == 4:
                    g["arena_wave"] = 5  # все волны пройдены
                    g["arena_enemies"] = []
                    g["arena_chest_open"] = False
                    g["arena_chest_looted"] = False
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = "Ключ получен. Иди к боссу!"
                    g["loot_msg_timer"] = 180

        # === Босс ===
        if g["room"]=="boss":
            if not g["boss_spawned"] and g["boss"] is None:
                if g["boss_spawn_timer"] > 0:
                    g["boss_spawn_timer"] = max(0, g["boss_spawn_timer"] - dt)
                else:
                    g["boss"] = make_boss()
                    g["boss_spawned"] = True
                    g["player_hp"] = g["player_max_hp"]
                    g["loot_msg"] = "СЛАЙМ-КОРОЛЬ появился!"
                    g["loot_msg_timer"] = 120
            if g["boss"] and g["boss"]["alive"]:
                update_boss(g["boss"],g,dt)

                # Босс раз в 5 секунд призывает 2-5 мини-слаймов
                g["boss_summon_timer"] = max(0, g["boss_summon_timer"] - dt)
                if g["boss_summon_timer"] <= 0:
                    g["boss_summon_timer"] = 60 * 5
                    count = random.randint(2, 5)
                    bcx = g["boss"]["x"] + BOSS_SIZE//2
                    bcy = g["boss"]["y"] + BOSS_SIZE//2
                    for _ in range(count):
                        angle = random.uniform(0, 2*math.pi)
                        dist = random.randint(70, 130)
                        x = max(80, min(bcx + math.cos(angle)*dist, rooms["boss"].world_w - 120))
                        y = max(80, min(bcy + math.sin(angle)*dist, rooms["boss"].world_h - 120))
                        g["boss_minions"].append(make_boss_minion(x, y))
                    g["loot_msg"] = f"Босс призвал слаймов: {count}!"
                    g["loot_msg_timer"] = 90

            # Мини-слаймы босса живут в комнате босса
            for en in g.get("boss_minions", []):
                if en["alive"]:
                    update_enemy(en, g, dt)
            g["boss_minions"] = [en for en in g.get("boss_minions", []) if en["alive"]]

        # Смерть игрока
        if g["player_hp"]<=0:
            g["player_hp"]=0; g["game_over"]=True

    # === Рисуем ===
    if g.get("screen") == "menu":
        screen.fill((8, 8, 12))
        title = font_big.render("MEDIEVAL DUNGEON", True, GOLD)
        sub = font.render("Пиксельный dungeon crawler", True, WHITE)
        screen.blit(title, (W//2 - title.get_width()//2, H//2 - 150))
        screen.blit(sub, (W//2 - sub.get_width()//2, H//2 - 105))

        mouse_pos = pygame.mouse.get_pos()
        for rect, text in [(start_button, "НАЧАТЬ"), (exit_button, "ВЫХОД")]:
            hover = rect.collidepoint(mouse_pos)
            color = (60, 60, 70) if not hover else (95, 85, 55)
            pygame.draw.rect(screen, color, rect, border_radius=8)
            pygame.draw.rect(screen, GOLD, rect, 2, border_radius=8)
            label = font_big.render(text, True, WHITE)
            screen.blit(label, (rect.centerx - label.get_width()//2, rect.centery - label.get_height()//2))

        hint_menu = font_small.render("Наведи мышкой и нажми ЛКМ", True, (150,150,150))
        screen.blit(hint_menu, (W//2 - hint_menu.get_width()//2, H//2 + 130))
        pygame.display.flip()
        continue

    cam_x=int(g["cam_x"]); cam_y=int(g["cam_y"])
    room_obj = rooms[g["room"]]

    world_surf.fill(BLACK)
    room_obj.draw(cam_x,cam_y)

    # Двери
    if g["room"]=="hub":
        draw_door(cam_x,cam_y,hub_door_rect,g["hub_door"],g["hub_door_frame"])
    if g["room"]=="arena":
        if arena_door_exit:
            state = "open" if g["keys"]>0 or g["arena_wave"]>=5 else "closed"
            draw_door(cam_x,cam_y,arena_door_exit,state,0)

    # Сундуки
    if g["room"]=="hub":
        draw_chest_obj(cam_x,cam_y,hub_chest_rect,g["hub_chest_opened"],g["hub_chest_frame"])
    if g["room"]=="arena":
        draw_chest_obj(cam_x,cam_y,arena_chest_rect,
                       not g["arena_chest_open"] and g["arena_chest_looted"],
                       g["arena_chest_frame"])

    # Факелы
    torches = room_obj.all_obj("torch","факел")
    for trect in torches:
        sz=(max(16,trect.width),max(16,trect.height))
        img=pygame.transform.scale(torch_frames[g["torch_frame"]%len(torch_frames)],sz)
        world_surf.blit(img,(trect.x-cam_x,trect.y-cam_y))

    # Враги арены
    if g["room"]=="arena":
        for en in g["arena_enemies"]:
            if en["alive"]: draw_enemy(cam_x,cam_y,en)

    # Мини-слаймы босса
    if g["room"]=="boss":
        for en in g.get("boss_minions", []):
            if en["alive"]:
                draw_enemy(cam_x,cam_y,en)

    # Босс
    if g["room"]=="boss" and g["boss"] and g["boss"]["alive"]:
        draw_boss_entity(cam_x,cam_y,g["boss"])

    # Подсказки взаимодействия
    if g["room"]=="hub" and not g["hub_chest_opened"] and near(hub_chest_rect,g["player_x"],g["player_y"]):
        h=font_small.render("E — открыть сундук",True,GOLD)
        world_surf.blit(h,(hub_chest_rect.x-cam_x-20,hub_chest_rect.y-cam_y-22))
    if g["room"]=="hub" and g["hub_door"]=="closed" and near(hub_door_rect,g["player_x"],g["player_y"],90):
        txt="E — открыть дверь" if g["keys"]>0 else "Нужен ключ!"
        h=font_small.render(txt,True,GOLD)
        world_surf.blit(h,(hub_door_rect.x-cam_x-20,hub_door_rect.y-cam_y-22))
    if g["room"]=="arena" and g["arena_chest_open"] and not g["arena_chest_looted"] and near(arena_chest_rect,g["player_x"],g["player_y"],90):
        secs=math.ceil(g["arena_chest_countdown"]/60)
        h=font_small.render(f"E — лут ({secs}с)",True,GOLD)
        world_surf.blit(h,(arena_chest_rect.x-cam_x-20,arena_chest_rect.y-cam_y-22))

    # След рывка + игрок
    if not g["game_over"]:
        fr=knight_run if g["player_moving"] else knight_idle
        tf=fr[g["player_anim_frame"]]
        for tr in g["dash_trails"]:
            gh=tf.copy()
            if tr["dir"]==-1: gh=pygame.transform.flip(gh,True,False)
            gh.set_alpha(int(120*tr["life"]/TRAIL_LIFE))
            world_surf.blit(gh,(tr["x"]-cam_x,tr["y"]-cam_y))
        frame=tf
        if g["player_dir"]==-1: frame=pygame.transform.flip(frame,True,False)
        if g["player_hit_flash"]>0:
            wf=frame.copy(); wf.fill((255,255,255),special_flags=pygame.BLEND_RGB_MAX)
            world_surf.blit(wf,(g["player_x"]-cam_x,g["player_y"]-cam_y))
        else:
            world_surf.blit(frame,(g["player_x"]-cam_x,g["player_y"]-cam_y))

    # Slash
    if g["slash_active"] and g["slash_frame"]<len(slash_frames):
        sf=slash_frames[g["slash_frame"]]
        rot=pygame.transform.rotate(sf,-g["slash_angle"])
        world_surf.blit(rot,(g["slash_x"]-cam_x,g["slash_y"]-cam_y))

    zoomed=pygame.transform.scale(world_surf,(W,H))
    screen.blit(zoomed,(0,0))

    # === HUD ===
    for i in range(g["player_max_hp"]):
        draw_heart(screen,12+i*22,H-34,filled=i<g["player_hp"],scale=2)

    # Счётчик волн на арене
    if g["room"]=="arena" and g["arena_wave"]>0:
        alive_cnt=sum(1 for e in g["arena_enemies"] if e["alive"])
        if g["arena_spawn_timer"] > 0 and g["arena_waiting_wave"] > 0:
            sec = max(1, math.ceil(g["arena_spawn_timer"] / 60))
            wt=font_big.render(f"Волна {g['arena_waiting_wave']} через {sec}...",True,GOLD)
        else:
            wt=font.render(f"Волна {min(g['arena_wave'],4)}/4   Врагов: {alive_cnt}",True,WHITE)
        screen.blit(wt,(W//2-wt.get_width()//2,10))

    # HP босса / таймер появления босса
    if g["room"]=="boss" and g["boss_spawn_timer"] > 0 and not g["boss"]:
        sec = max(1, math.ceil(g["boss_spawn_timer"] / 60))
        bt=font_big.render(f"Босс через {sec}...",True,GOLD)
        screen.blit(bt,(W//2-bt.get_width()//2,20))
    if g["room"]=="boss" and g["boss"] and g["boss"]["alive"]:
        bw=400
        draw_hp_bar(screen,W//2-bw//2,20,bw,16,g["boss"]["hp"],g["boss"]["max_hp"],RED)
        bt=font.render("СЛАЙМ-КОРОЛЬ",True,WHITE)
        screen.blit(bt,(W//2-bt.get_width()//2,40))

    screen.blit(font_small.render(
        f"Урон:{g['player_damage']}  Ключи:{g['keys']}  Комната:{g['room']}",True,WHITE),(10,H-55))
    if g.get("god_mode", False):
        gm = font.render("GOD MODE", True, GOLD)
        screen.blit(gm, (10, 10))

    if g["loot_msg_timer"]>0:
        msg=font_big.render(g["loot_msg"],True,GOLD)
        screen.blit(msg,(W//2-msg.get_width()//2,H//2-50))

    # Game Over
    if g["game_over"]:
        ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,160)); screen.blit(ov,(0,0))
        screen.blit(font_big.render("GAME OVER",True,RED),(W//2-100,H//2-50))
        screen.blit(font.render("R — рестарт   ESC — выход",True,WHITE),(W//2-90,H//2+10))

    # Victory
    if g["victory"]:
        ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,160)); screen.blit(ov,(0,0))
        win = font_big.render("ТЫ ВЫИГРАЛ!", True, GOLD)
        screen.blit(win, (W//2 - win.get_width()//2, H//2 - 70))
        sub_win = font.render("Слайм-Король повержен", True, WHITE)
        screen.blit(sub_win, (W//2 - sub_win.get_width()//2, H//2 - 25))
        screen.blit(font.render("R — играть снова   ESC — выход",True,WHITE),(W//2-110,H//2+25))

    hint=font_small.render(
        "WASD — движение   ПКМ — рывок   ЛКМ — атака   E — действие   O — god mode   R — рестарт   ESC — выход",
        True,(120,120,120))
    screen.blit(hint,(W//2-hint.get_width()//2,H-12))

    pygame.display.flip()

pygame.quit()
