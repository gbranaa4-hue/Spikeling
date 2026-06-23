"""
SPIKELING DUNGEON FPS - TRIPLE-A OPTIMIZED
============================================
- Neuro-morphic dormant system (enemies sleep when far)
- Occlusion culling (only render visible rooms)
- Door portal transitions
- LOD system for distant geometry
- Batch rendering for performance

CONTROLS: WASD | Mouse | LMB Shoot | Space Jump | L Invert | R Restart | ESC Quit
"""

import math, time, re, os, sys, random
from collections import deque
import numpy as np
import pygame
from pygame.locals import *
from OpenGL.GL   import *
from OpenGL.GLU  import *


# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

CELL_SIZE = 10.0
ROOM_HALF = 4.6
WALL_T = 0.4
ROOM_HEIGHT = 3.2
DOOR_WIDTH = 1.8
DOOR_HEIGHT = 2.4
MAX_RENDER_DIST = 50.0
MAX_ACTIVE_DIST = 30.0

DIRS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


# ═══════════════════════════════════════════════════════════════════════════════
#  MATH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def v3(x=0., y=0., z=0.):
    return np.array([x, y, z], dtype=np.float64)

def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v.copy()

def dist(a, b):
    return float(np.linalg.norm(a - b))


# ═══════════════════════════════════════════════════════════════════════════════
#  SPIKELING DSL (Neuromorphic Brain)
# ═══════════════════════════════════════════════════════════════════════════════

class SpikelingBrain:
    def __init__(self):
        self.neurons = {}
        self.reflex_mappings = {}
        self.refractory_ms = 800
        self.spike_history = {}
        self.stimulus_weights = {}
        self.dormant = True
        self.last_activity = 0.0

    def compile(self, src):
        for raw in src.strip().splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('neuron'):
                m = re.match(r'neuron\s+(\w+)\s+threshold=(\d+)\s+leak=(\d+)', line)
                if m:
                    name, thr, leak = m.groups()
                    self.neurons[name] = {'threshold': int(thr), 'leak': int(leak),
                                          'membrane_potential': 0.0}
                    self.spike_history[name] = 0.0
                    self.stimulus_weights[name] = {}
            elif line.startswith('action'):
                m = re.match(r'action\s+(\w+)\s+->\s+\[(\w+)\]', line)
                if m:
                    self.reflex_mappings[m.group(1)] = m.group(2)
            elif line.startswith('refractory'):
                m = re.match(r'refractory=(\d+)ms', line)
                if m:
                    self.refractory_ms = int(m.group(1))
            elif line.startswith('weight'):
                m = re.match(r'weight\s+(\w+)\s+stimulus=(\w+)\s+value=(\d+)', line)
                if m:
                    n, s, v = m.groups()
                    if n in self.stimulus_weights:
                        self.stimulus_weights[n][s] = int(v)

    def stimulate(self, neuron, stimulus, magnitude, now):
        if neuron not in self.neurons:
            return None
        if (now - self.spike_history[neuron]) * 1000 < self.refractory_ms:
            return None
        w = self.stimulus_weights[neuron].get(stimulus, 100)
        n = self.neurons[neuron]
        n['membrane_potential'] += magnitude * (w / 100.0)
        n['membrane_potential'] *= (1.0 - n['leak'] / 1000.0)
        if n['membrane_potential'] >= n['threshold']:
            self.spike_history[neuron] = now
            n['membrane_potential'] = 0.0
            self.last_activity = now
            self.dormant = False
            return self.reflex_mappings.get(neuron, 'UNKNOWN')
        return None

    def tick_leak(self, now):
        for n in self.neurons.values():
            n['membrane_potential'] *= (1.0 - n['leak'] / 1000.0)
        if now - self.last_activity > 3.0:
            self.dormant = True


DEFAULT_DSL = """
neuron SightThreat    threshold=80  leak=8
neuron ProximityAlert threshold=90  leak=5
neuron DamageTaken    threshold=40  leak=15
neuron LowHealth      threshold=90  leak=2
neuron PatrolIdle     threshold=30  leak=20

action SightThreat    -> [CHASE]
action ProximityAlert -> [ATTACK]
action DamageTaken    -> [RECOIL]
action LowHealth      -> [FLEE]
action PatrolIdle     -> [PATROL]

refractory=800ms

weight SightThreat    stimulus=SIGHT    value=100
weight SightThreat    stimulus=SOUND    value=40
weight ProximityAlert stimulus=DISTANCE value=100
weight DamageTaken    stimulus=HIT      value=100
weight LowHealth      stimulus=HEALTH   value=100
weight PatrolIdle     stimulus=IDLE     value=100
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  UNIT CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

class UnitClass:
    def __init__(self, name, health, speed, damage, attack_range, sight_range, 
                 width, height, color, is_boss=False, is_elite=False):
        self.name = name
        self.max_health = health
        self.speed = speed
        self.damage = damage
        self.attack_range = attack_range
        self.sight_range = sight_range
        self.width = width
        self.height = height
        self.color = color
        self.is_boss = is_boss
        self.is_elite = is_elite

UNIT_CLASSES = {
    'grunt': UnitClass('Grunt', 50, 2.5, 5, 1.8, 15, 0.4, 0.8, (0.3, 0.5, 0.9)),
    'soldier': UnitClass('Soldier', 80, 3.0, 8, 2.0, 20, 0.45, 0.9, (0.5, 0.7, 1.0)),
    'elite': UnitClass('Elite', 150, 3.5, 12, 2.5, 25, 0.5, 1.0, (0.9, 0.4, 0.8), is_elite=True),
    'boss': UnitClass('Boss', 500, 2.0, 20, 3.0, 30, 0.8, 1.5, (0.95, 0.15, 0.15), is_boss=True),
    'fast': UnitClass('Scout', 40, 5.0, 4, 1.5, 18, 0.35, 0.7, (0.2, 0.9, 0.6)),
    'tank': UnitClass('Tank', 300, 1.8, 10, 2.0, 20, 0.7, 1.2, (0.4, 0.3, 0.5)),
}


# ═══════════════════════════════════════════════════════════════════════════════
#  DUNGEON
# ═══════════════════════════════════════════════════════════════════════════════

def cell_center(cx, cz):
    return np.array([cx * CELL_SIZE, 0.0, cz * CELL_SIZE])


class Room:
    __slots__ = ('cx', 'cz', 'id', 'neighbors', 'center', 'kind', 'is_boss_room', 
                 'is_start', 'boxes', 'bounds', 'door_positions')
    
    def __init__(self, cx, cz, rid):
        self.cx, self.cz = cx, cz
        self.id = rid
        self.neighbors = {}
        self.center = cell_center(cx, cz)
        self.kind = 'normal'
        self.is_boss_room = False
        self.is_start = False
        self.boxes = []
        self.bounds = None
        self.door_positions = {}
    
    def has_door(self, direction):
        return direction in self.neighbors


class Dungeon:
    def __init__(self, num_rooms=400, seed=None):
        self.rng = random.Random(seed)
        self.rooms = {}
        self.rooms_by_id = []
        self.boss_room = None
        self._generate(num_rooms)
        self._build_geometry()
        self._compute_bounds()
        print(f"✓ Dungeon: {len(self.rooms_by_id)} rooms")

    def _generate(self, num_rooms):
        start = Room(0, 0, 0)
        start.is_start = True
        start.kind = 'start'
        self.rooms[(0, 0)] = start
        self.rooms_by_id.append(start)
        frontier = [start]

        while len(self.rooms) < num_rooms and frontier:
            room = self.rng.choice(frontier)
            dirs = list(DIRS.items())
            self.rng.shuffle(dirs)
            grew = False
            for d, (ox, oz) in dirs:
                if room.has_door(d):
                    continue
                ncx, ncz = room.cx + ox, room.cz + oz
                if (ncx, ncz) in self.rooms:
                    continue
                new_room = Room(ncx, ncz, len(self.rooms_by_id))
                if len(self.rooms_by_id) % 8 == 0:
                    new_room.kind = 'ambush'
                self.rooms[(ncx, ncz)] = new_room
                self.rooms_by_id.append(new_room)
                room.neighbors[d] = new_room
                new_room.neighbors[OPPOSITE[d]] = room
                frontier.append(new_room)
                grew = True
                break
            if not grew:
                frontier.remove(room)

        for _ in range(max(1, num_rooms // 15)):
            r = self.rng.choice(self.rooms_by_id)
            dirs = list(DIRS.items())
            self.rng.shuffle(dirs)
            for d, (ox, oz) in dirs:
                if r.has_door(d):
                    continue
                ncx, ncz = r.cx + ox, r.cz + oz
                if (ncx, ncz) in self.rooms:
                    other = self.rooms[(ncx, ncz)]
                    r.neighbors[d] = other
                    other.neighbors[OPPOSITE[d]] = r
                    break

        if len(self.rooms_by_id) > 10:
            start_room = self.rooms[(0, 0)]
            farthest = max(self.rooms_by_id, 
                          key=lambda rm: (rm.cx - start_room.cx)**2 + (rm.cz - start_room.cz)**2)
            farthest.is_boss_room = True
            farthest.kind = 'boss'
            self.boss_room = farthest

    def _build_geometry(self):
        for room in self.rooms_by_id:
            boxes = []
            x, _, z = room.center
            h = ROOM_HALF
            
            if room.is_boss_room:
                wall_color = (0.50, 0.20, 0.30)
                floor_color = (0.30, 0.15, 0.20)
            elif room.kind == 'ambush':
                wall_color = (0.30, 0.25, 0.35)
                floor_color = (0.28, 0.16, 0.16)
            elif room.is_start:
                wall_color = (0.35, 0.40, 0.45)
                floor_color = (0.25, 0.30, 0.25)
            else:
                wall_color = (0.30, 0.28, 0.30)
                floor_color = (0.22, 0.20, 0.20)
            
            boxes.append((x, -0.25, z, h, 0.25, h, *floor_color))
            boxes.append((x, ROOM_HEIGHT + 0.25, z, h, 0.25, h, 0.12, 0.12, 0.15))
            
            for d in ['N', 'S', 'E', 'W']:
                has_door = room.has_door(d)
                hw = ROOM_HEIGHT / 2
                
                if has_door:
                    if d == 'N':
                        room.door_positions[d] = np.array([x, 0, z - h])
                    elif d == 'S':
                        room.door_positions[d] = np.array([x, 0, z + h])
                    elif d == 'E':
                        room.door_positions[d] = np.array([x + h, 0, z])
                    else:
                        room.door_positions[d] = np.array([x - h, 0, z])
                
                if d in ('N', 'S'):
                    wz = z - h if d == 'N' else z + h
                    if not has_door:
                        boxes.append((x, hw, wz, h, hw, WALL_T, *wall_color))
                    else:
                        seg = (2 * h - DOOR_WIDTH) / 2
                        boxes.append((x - h + seg/2, hw, wz, seg/2, hw, WALL_T, *wall_color))
                        boxes.append((x + h - seg/2, hw, wz, seg/2, hw, WALL_T, *wall_color))
                        boxes.append((x, ROOM_HEIGHT - (ROOM_HEIGHT - DOOR_HEIGHT)/2, wz,
                                      DOOR_WIDTH/2, (ROOM_HEIGHT - DOOR_HEIGHT)/2, WALL_T, *wall_color))
                else:
                    wx = x - h if d == 'W' else x + h
                    if not has_door:
                        boxes.append((wx, hw, z, WALL_T, hw, h, *wall_color))
                    else:
                        seg = (2 * h - DOOR_WIDTH) / 2
                        boxes.append((wx, hw, z - h + seg/2, WALL_T, hw, seg/2, *wall_color))
                        boxes.append((wx, hw, z + h - seg/2, WALL_T, hw, seg/2, *wall_color))
                        boxes.append((wx, ROOM_HEIGHT - (ROOM_HEIGHT - DOOR_HEIGHT)/2, z,
                                      WALL_T, (ROOM_HEIGHT - DOOR_HEIGHT)/2, DOOR_WIDTH/2, *wall_color))
            
            room.boxes = boxes

    def _compute_bounds(self):
        for room in self.rooms_by_id:
            if room.boxes:
                minx = min(b[0] - b[3] for b in room.boxes)
                maxx = max(b[0] + b[3] for b in room.boxes)
                minz = min(b[2] - b[5] for b in room.boxes)
                maxz = max(b[2] + b[5] for b in room.boxes)
                room.bounds = (minx, minz, maxx, maxz)

    def room_at(self, pos):
        cx = round(pos[0] / CELL_SIZE)
        cz = round(pos[2] / CELL_SIZE)
        return self.rooms.get((cx, cz))

    def visible_rooms(self, from_room, max_hops=3, max_rooms=40):
        if from_room is None:
            return []
        visited = {from_room.id: from_room}
        frontier = [(from_room, 0)]
        result = [from_room]
        while frontier and len(result) < max_rooms:
            room, hop = frontier.pop(0)
            if hop >= max_hops:
                continue
            for nb in room.neighbors.values():
                if nb.id not in visited:
                    visited[nb.id] = nb
                    result.append(nb)
                    frontier.append((nb, hop + 1))
        return result

    def spawn_position_in(self, room):
        jitter_x = self.rng.uniform(-ROOM_HALF * 0.5, ROOM_HALF * 0.5)
        jitter_z = self.rng.uniform(-ROOM_HALF * 0.5, ROOM_HALF * 0.5)
        return room.center + np.array([jitter_x, 0, jitter_z])

    def collide_circle(self, pos, radius, player_half_height=0.9, eye_y=None):
        room = self.room_at(pos)
        if room is None:
            return
        py = eye_y if eye_y is not None else pos[1]
        p_lo, p_hi = py - player_half_height, py + player_half_height
        candidates = [room] + list(room.neighbors.values())
        for r in candidates:
            for b in r.boxes:
                bx, by, bz, hx, hy, hz = b[:6]
                if hx > 2.0 and hz > 2.0 and hy < 1.0:
                    continue
                b_lo, b_hi = by - hy, by + hy
                if b_hi < p_lo or b_lo > p_hi:
                    continue
                px, pz = pos[0], pos[2]
                closest_x = max(bx - hx, min(px, bx + hx))
                closest_z = max(bz - hz, min(pz, bz + hz))
                dx, dz = px - closest_x, pz - closest_z
                d = math.hypot(dx, dz)
                if d < radius:
                    if d > 1e-6:
                        nx, nz = dx / d, dz / d
                    else:
                        nx, nz = 1.0, 0.0
                    push = radius - d
                    pos[0] += nx * push
                    pos[2] += nz * push
    
    def check_door_crossing(self, old_pos, new_pos):
        old_room = self.room_at(old_pos)
        new_room = self.room_at(new_pos)
        
        if old_room is None or new_room is None:
            return new_room
        
        if old_room == new_room:
            return new_room
        
        for d, neighbor in old_room.neighbors.items():
            if neighbor == new_room:
                return new_room
        
        return old_room


# ═══════════════════════════════════════════════════════════════════════════════
#  OVERMIND
# ═══════════════════════════════════════════════════════════════════════════════

class Overmind:
    def __init__(self, dungeon):
        self.dungeon = dungeon
        self.phase = "CALM"
        self.active_zones = set()
        
        self.brain = SpikelingBrain()
        self.brain.compile("""
            neuron GlobalThreat    threshold=50  leak=3
            neuron BossDetected    threshold=40  leak=2
            
            action GlobalThreat  -> [FRENZY]
            action BossDetected  -> [BOSS_ALERT]
            
            refractory=500ms
            
            weight GlobalThreat  stimulus=ENEMY_ALIVE value=80
            weight GlobalThreat  stimulus=PLAYER_DIST value=60
            weight BossDetected  stimulus=BOSS_NEAR  value=100
        """)
    
    def get_global_directive(self, player, enemies, now):
        alive_enemies = [e for e in enemies if e.alive]
        alive_count = len(alive_enemies)
        
        boss_near = False
        for e in alive_enemies:
            if e.unit_class.is_boss and dist(e.pos, player.pos) < 40:
                boss_near = True
                break
        
        avg_dist = 0.0
        if alive_count > 0 and player.alive:
            distances = [np.linalg.norm(e.pos - player.pos) for e in alive_enemies if e.active]
            if distances:
                avg_dist = sum(distances) / len(distances)
        
        if player.alive:
            threat_mag = min(100, (alive_count * 6) + (30 - min(30, avg_dist)))
            self.brain.stimulate('GlobalThreat', 'ENEMY_ALIVE', threat_mag, now)
            self.brain.stimulate('GlobalThreat', 'PLAYER_DIST', max(0, 100 - avg_dist * 2), now)
            self.brain.stimulate('BossDetected', 'BOSS_NEAR', 100 if boss_near else 0, now)
        
        self.brain.tick_leak(now)
        
        threat_potential = self.brain.neurons.get('GlobalThreat', {}).get('membrane_potential', 0)
        boss_potential = self.brain.neurons.get('BossDetected', {}).get('membrane_potential', 0)
        
        if boss_potential > 30:
            self.phase = "BOSS_ALERT"
        elif threat_potential > 50:
            self.phase = "FRENZY"
        else:
            self.phase = "CALM"
        
        if self.phase == "BOSS_ALERT":
            return {"phase": "BOSS_ALERT", "ATTACK": 2.5, "CHASE": 2.0, "FLEE": 0.1,
                    "RECOIL": 0.1, "PATROL": 0.1, "aggression": 2.5}
        elif self.phase == "FRENZY":
            return {"phase": "FRENZY", "ATTACK": 2.0, "CHASE": 1.8, "FLEE": 0.2,
                    "RECOIL": 0.1, "PATROL": 0.3, "aggression": 2.0}
        else:
            return {"phase": "CALM", "ATTACK": 0.5, "CHASE": 0.7, "FLEE": 0.5,
                    "RECOIL": 0.5, "PATROL": 1.0, "aggression": 0.6}


# ═══════════════════════════════════════════════════════════════════════════════
#  3D RENDERING (Optimized with Display Lists)
# ═══════════════════════════════════════════════════════════════════════════════

_display_lists = {}

def draw_box(cx, cy, cz, sx, sy, sz, r, g, b):
    """Draw a box using display list caching for performance."""
    key = (round(sx, 2), round(sy, 2), round(sz, 2), round(r, 2), round(g, 2), round(b, 2))
    if key not in _display_lists:
        dl = glGenLists(1)
        glNewList(dl, GL_COMPILE)
        _draw_box_immediate(cx, cy, cz, sx, sy, sz, r, g, b)
        glEndList()
        _display_lists[key] = dl
    glCallList(_display_lists[key])

def _draw_box_immediate(cx, cy, cz, sx, sy, sz, r, g, b):
    """Immediate mode box drawing (called once per unique box type)."""
    x0, x1 = cx-sx, cx+sx
    y0, y1 = cy-sy, cy+sy
    z0, z1 = cz-sz, cz+sz
    dr, dg, db = r*0.55, g*0.55, b*0.55
    _face([(x0,y1,z1),(x1,y1,z1),(x1,y0,z1),(x0,y0,z1)],  0, 0, 1, r,  g,  b)
    _face([(x1,y1,z0),(x0,y1,z0),(x0,y0,z0),(x1,y0,z0)],  0, 0,-1, r,  g,  b)
    _face([(x0,y1,z0),(x0,y1,z1),(x0,y0,z1),(x0,y0,z0)], -1, 0, 0, dr, dg, db)
    _face([(x1,y1,z1),(x1,y1,z0),(x1,y0,z0),(x1,y0,z1)],  1, 0, 0, dr, dg, db)
    _face([(x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1)],  0, 1, 0, r*0.85,g*0.85,b*0.85)
    _face([(x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0)],  0,-1, 0, dr*0.7,dg*0.7,db*0.7)

def _face(verts, nx, ny, nz, r, g, b):
    glNormal3f(nx, ny, nz)
    glColor3f(r, g, b)
    glBegin(GL_QUADS)
    for v in verts:
        glVertex3f(*v)
    glEnd()

def draw_sphere(cx, cy, cz, radius, r, g, b, slices=8, stacks=6):
    glColor3f(r, g, b)
    glPushMatrix()
    glTranslatef(cx, cy, cz)
    q = gluNewQuadric()
    gluSphere(q, radius, slices, stacks)
    gluDeleteQuadric(q)
    glPopMatrix()

def set_camera(px, py, pz, yaw, pitch):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(75, pygame.display.get_surface().get_width() /
                       pygame.display.get_surface().get_height(), 0.05, 500)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glRotatef(-pitch, 1, 0, 0)
    glRotatef(-yaw,   0, 1, 0)
    glTranslatef(-px, -py, -pz)

def setup_lighting():
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION,  [1.0, 2.0, 1.0, 0.0])
    glLightfv(GL_LIGHT0, GL_DIFFUSE,   [1.0, 0.95, 0.9, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT,   [0.35, 0.35, 0.4, 1.0])
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROJECTILE
# ═══════════════════════════════════════════════════════════════════════════════

class Projectile:
    SPEED = 35.0
    DAMAGE = 25
    RADIUS = 0.12

    def __init__(self, pos, direction):
        self.pos = pos.copy()
        self.dir = norm(direction)
        self.alive = True

    def update(self, dt):
        self.pos += self.dir * self.SPEED * dt
        if np.linalg.norm(self.pos) > 400:
            self.alive = False

    def draw(self):
        draw_sphere(*self.pos, self.RADIUS, 1.0, 0.9, 0.1)


# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYER
# ═══════════════════════════════════════════════════════════════════════════════

class Player:
    HEIGHT = 1.75
    EYE_HEIGHT = 1.6
    RADIUS = 0.4
    MOVE_SPEED = 6.5
    JUMP_FORCE = 8.0
    GRAVITY = -22.0
    MAX_HEALTH = 100
    SHOOT_CD = 0.18

    def __init__(self):
        self.pos = v3(0, self.HEIGHT, 0)
        self.prev_pos = self.pos.copy()
        self.vel = v3()
        self.yaw = 0.0
        self.pitch = 0.0
        self.health = self.MAX_HEALTH
        self.alive = True
        self._on_ground = False
        self._shoot_timer = 0.0
        self.damage_flash = 0.0
        self.projectiles = []
        self.invert_yaw = False
        self.current_room = None

    @property
    def eye(self):
        return self.pos + v3(0, self.EYE_HEIGHT - self.HEIGHT, 0)

    def forward(self):
        y = math.radians(self.yaw)
        p = math.radians(self.pitch)
        return norm(v3(-math.sin(y)*math.cos(p), math.sin(p), -math.cos(y)*math.cos(p)))

    def right(self):
        y = math.radians(self.yaw)
        return norm(v3(math.cos(y), 0, -math.sin(y)))

    def take_damage(self, amt):
        self.health = max(0, self.health - amt)
        self.damage_flash = 0.35
        if self.health <= 0:
            self.alive = False

    def shoot(self):
        if self._shoot_timer > 0 or not self.alive:
            return
        self._shoot_timer = self.SHOOT_CD
        self.projectiles.append(Projectile(self.eye, self.forward()))

    def toggle_invert(self):
        self.invert_yaw = not self.invert_yaw

    def update(self, dt, dungeon):
        self._shoot_timer = max(0, self._shoot_timer - dt)
        self.damage_flash = max(0, self.damage_flash - dt)

        self.prev_pos = self.pos.copy()
        self.vel[1] += self.GRAVITY * dt
        self.pos += self.vel * dt

        floor_y = self.HEIGHT
        if self.pos[1] < floor_y:
            self.pos[1] = floor_y
            self.vel[1] = 0.0
            self._on_ground = True
        else:
            self._on_ground = False

        if dungeon is not None:
            band_center = self.pos[1] + self.HEIGHT / 2
            dungeon.collide_circle(self.pos, self.RADIUS,
                                   player_half_height=self.HEIGHT/2 + 0.05,
                                   eye_y=band_center)
            
            new_room = dungeon.check_door_crossing(self.prev_pos, self.pos)
            if new_room is not None and new_room != self.current_room:
                self.current_room = new_room

        for p in self.projectiles[:]:
            if not p.alive:
                self.projectiles.remove(p)
            else:
                p.update(dt)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENEMY (With neuro-morphic dormant system)
# ═══════════════════════════════════════════════════════════════════════════════

class Enemy:
    def __init__(self, name, pos, unit_class, room, dsl_source=None, dsl_file=None):
        self.name = name
        self.pos = v3(pos[0], 0, pos[2])
        self.unit_class = unit_class
        self.room = room
        self.health = unit_class.max_health
        self.max_health = unit_class.max_health
        self.alive = True
        self.active = False
        self.state = 'PATROL'
        self._attack_timer = 0.0
        self._recoil_timer = 0.0
        self._recoil_dir = v3()
        self._patrol_target = None
        self._color = unit_class.color
        self._activity_timer = 0.0
        
        self.brain = SpikelingBrain()
        if dsl_file and os.path.exists(dsl_file):
            self.brain.compile_file(dsl_file)
        else:
            self.brain.compile(dsl_source if dsl_source else DEFAULT_DSL)
        
        self._new_patrol()

    def _new_patrol(self):
        a = np.random.uniform(0, 2*math.pi)
        d = np.random.uniform(2, ROOM_HALF * 0.5)
        center = self.room.center
        self._patrol_target = center + v3(math.cos(a)*d, 0, math.sin(a)*d)

    def take_damage(self, amt):
        if not self.alive:
            return
        self.health -= amt
        now = time.time()
        self.brain.stimulate('DamageTaken', 'HIT', 100.0, now)
        hp_pct = max(0, (self.max_health - self.health) / self.max_health * 100)
        self.brain.stimulate('LowHealth', 'HEALTH', hp_pct, now)
        self._recoil_dir = -norm(v3(np.random.randn(), 0, np.random.randn()))
        self._recoil_timer = 0.25
        self.active = True
        if self.health <= 0:
            self.alive = False

    def update(self, dt, player, directive, dungeon, now):
        dist_to_player = dist(self.pos, player.pos)
        
        player_room = dungeon.room_at(player.pos)
        same_room = (player_room == self.room)
        adjacent = player_room in list(self.room.neighbors.values())
        
        if dist_to_player < self.unit_class.sight_range or same_room or adjacent:
            self.active = True
            self._activity_timer = 2.0
        elif self._activity_timer > 0:
            self._activity_timer -= dt
            if self._activity_timer <= 0:
                self.active = False
        
        if not self.alive:
            return
        
        # Dormant enemies - minimal processing
        if not self.active:
            if self._patrol_target is not None:
                diff = self._patrol_target - self.pos
                diff[1] = 0
                if np.linalg.norm(diff) < 0.5:
                    self._new_patrol()
                else:
                    self.pos += norm(diff) * self.unit_class.speed * 0.15 * dt
            return

        # Active enemy processing
        d_vec = player.pos - self.pos
        d_vec[1] = 0
        d_flat = float(np.linalg.norm(d_vec))

        emitted = None
        if (same_room or adjacent) and d_flat < self.unit_class.sight_range:
            mag = (self.unit_class.sight_range - d_flat) / self.unit_class.sight_range * 100
            a = self.brain.stimulate('SightThreat', 'SIGHT', mag, now)
            if a: emitted = a
        if same_room and d_flat < self.unit_class.attack_range * 4:
            mag = (self.unit_class.attack_range*4 - d_flat) / (self.unit_class.attack_range*4) * 100
            a = self.brain.stimulate('ProximityAlert', 'DISTANCE', mag, now)
            if a: emitted = a
        if not same_room or d_flat >= self.unit_class.sight_range:
            a = self.brain.stimulate('PatrolIdle', 'IDLE', 60.0, now)
            if a: emitted = a
        self.brain.tick_leak(now)

        individual_state = emitted if emitted else self.state
        aggression_mod = directive.get('aggression', 1.0)
        
        if self.unit_class.is_boss:
            aggression_mod = max(aggression_mod, 2.0)
            individual_state = 'ATTACK' if d_flat < 15 else 'CHASE'
        
        action_weights = {
            'ATTACK': directive.get('ATTACK', 1.0),
            'CHASE': directive.get('CHASE', 1.0),
            'FLEE': directive.get('FLEE', 0.5),
            'RECOIL': directive.get('RECOIL', 0.5),
            'PATROL': directive.get('PATROL', 1.0)
        }
        if individual_state in action_weights:
            action_weights[individual_state] *= 1.5
        
        total = sum(action_weights.values())
        if total > 0:
            r_val = np.random.random() * total
            cum = 0
            for s, w in action_weights.items():
                cum += w
                if r_val <= cum:
                    self.state = s
                    break

        self._attack_timer = max(0, self._attack_timer - dt)
        self._recoil_timer = max(0, self._recoil_timer - dt)

        speed = self.unit_class.speed * (0.5 + 0.5 * aggression_mod)

        if self.state == 'RECOIL' and self._recoil_timer > 0:
            self.pos += self._recoil_dir * 5.0 * dt * (1.0 / max(0.1, aggression_mod))
        elif self.state == 'FLEE':
            away = norm(self.pos - player.pos) if d_flat > 0.1 else v3(1,0,0)
            away[1] = 0
            self.pos += away * speed * 1.6 * dt
        elif self.state == 'CHASE':
            if d_flat > 0.6 and (same_room or adjacent):
                self.pos += norm(d_vec) * speed * dt
        elif self.state == 'ATTACK':
            if same_room and d_flat < self.unit_class.attack_range:
                if self._attack_timer <= 0 and player.alive:
                    player.take_damage(self.unit_class.damage)
                    self._attack_timer = 1.4
            elif (same_room or adjacent) and d_flat > 0.6:
                self.pos += norm(d_vec) * speed * 0.8 * dt
        else:
            if self._patrol_target is not None:
                diff = self._patrol_target - self.pos
                diff[1] = 0
                if np.linalg.norm(diff) < 0.5:
                    self._new_patrol()
                else:
                    self.pos += norm(diff) * speed * 0.3 * dt

        # Keep in room
        center = self.room.center
        dx = self.pos[0] - center[0]
        dz = self.pos[2] - center[2]
        max_dist = ROOM_HALF - 0.3
        if dx > max_dist: self.pos[0] = center[0] + max_dist
        if dx < -max_dist: self.pos[0] = center[0] - max_dist
        if dz > max_dist: self.pos[2] = center[2] + max_dist
        if dz < -max_dist: self.pos[2] = center[2] - max_dist
        self.pos[1] = 0.0

        # Update color
        if self.unit_class.is_boss:
            pulse = 0.8 + 0.2 * math.sin(now * 3)
            self._color = (pulse, 0.1, 0.1)
        elif self.state == 'ATTACK':
            self._color = (0.95, 0.15, 0.15)
        elif self.state == 'CHASE':
            self._color = (0.9, 0.65, 0.1)
        elif self.state == 'FLEE':
            self._color = (0.65, 0.15, 0.9)
        else:
            self._color = self.unit_class.color

    def draw(self):
        if not self.alive:
            draw_box(self.pos[0], 0.2, self.pos[2], 0.3, 0.2, 0.3, 0.25, 0.22, 0.20)
            return
        
        # Dormant enemies - simple sphere
        if not self.active:
            r, g, b = self.unit_class.color
            glColor3f(r*0.3, g*0.3, b*0.3)
            glPushMatrix()
            glTranslatef(self.pos[0], self.unit_class.height, self.pos[2])
            q = gluNewQuadric()
            gluSphere(q, self.unit_class.width * 0.6, 6, 4)
            gluDeleteQuadric(q)
            glPopMatrix()
            return
        
        r, g, b = self._color
        h = self.unit_class.height
        w = self.unit_class.width
        
        draw_box(self.pos[0], h, self.pos[2], w, h, w, r, g, b)
        
        if self.unit_class.is_boss:
            draw_box(self.pos[0], h*2 + 0.3, self.pos[2], w*0.8, 0.3, w*0.8, 1.0, 0.8, 0.1)
        elif self.unit_class.is_elite:
            draw_box(self.pos[0], h*2 + 0.2, self.pos[2], w*0.5, 0.2, w*0.5, 0.9, 0.4, 0.8)
        
        draw_box(self.pos[0], h*2 + 0.35, self.pos[2], w*0.7, 0.35, w*0.7, r*0.8, g*0.8, b*0.8)
        
        glDisable(GL_LIGHTING)
        eye_size = 0.08 if not self.unit_class.is_boss else 0.15
        eye_color = (1, 0, 0) if self.state == 'ATTACK' else (1, 1, 1)
        draw_sphere(self.pos[0]+w*0.3, h*2+0.45, self.pos[2]-w*0.6, eye_size, *eye_color)
        draw_sphere(self.pos[0]-w*0.3, h*2+0.45, self.pos[2]-w*0.6, eye_size, *eye_color)
        glEnable(GL_LIGHTING)

        hp_pct = self.health / self.max_health
        bw = w * 3 if self.unit_class.is_boss else w * 2
        bh = 0.08
        by = h*2 + (0.9 if self.unit_class.is_boss else 0.7)
        
        glDisable(GL_LIGHTING)
        glBegin(GL_QUADS)
        glColor3f(0.6, 0.1, 0.1)
        glVertex3f(self.pos[0]-bw/2, by, self.pos[2])
        glVertex3f(self.pos[0]+bw/2, by, self.pos[2])
        glVertex3f(self.pos[0]+bw/2, by+bh, self.pos[2])
        glVertex3f(self.pos[0]-bw/2, by+bh, self.pos[2])
        glColor3f(0.1, 0.9, 0.2)
        glVertex3f(self.pos[0]-bw/2, by, self.pos[2]-0.01)
        glVertex3f(self.pos[0]-bw/2+bw*hp_pct, by, self.pos[2]-0.01)
        glVertex3f(self.pos[0]-bw/2+bw*hp_pct, by+bh, self.pos[2]-0.01)
        glVertex3f(self.pos[0]-bw/2, by+bh, self.pos[2]-0.01)
        glEnd()
        glEnable(GL_LIGHTING)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD
# ═══════════════════════════════════════════════════════════════════════════════

class HUD:
    def __init__(self, w, h):
        self.w, self.h = w, h
        pygame.font.init()
        self.font_big = pygame.font.SysFont('consolas,monospace', 32, bold=True)
        self.font_med = pygame.font.SysFont('consolas,monospace', 20, bold=True)
        self.font_small = pygame.font.SysFont('consolas,monospace', 15)
        self._surf = pygame.Surface((w, h), pygame.SRCALPHA)

    def draw(self, screen, player, enemies, overmind, dungeon):
        self._surf.fill((0, 0, 0, 0))
        W, H = self.w, self.h

        cx, cy = W//2, H//2
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, W, H, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glLineWidth(1.5)
        glColor4f(1, 1, 1, 0.85)
        glBegin(GL_LINES)
        glVertex2f(cx-14, cy)
        glVertex2f(cx+14, cy)
        glVertex2f(cx, cy-14)
        glVertex2f(cx, cy+14)
        glEnd()
        glLineWidth(1.0)

        if player.damage_flash > 0:
            alpha = player.damage_flash / 0.35
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glColor4f(0.8, 0.0, 0.0, alpha * 0.45)
            glBegin(GL_QUADS)
            glVertex2f(0, 0)
            glVertex2f(W, 0)
            glVertex2f(W, H)
            glVertex2f(0, H)
            glEnd()
            glDisable(GL_BLEND)

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glEnable(GL_LIGHTING)
        glEnable(GL_DEPTH_TEST)

        hp = player.health / player.MAX_HEALTH
        pygame.draw.rect(self._surf, (80, 10, 10, 200), (18, H-46, 200, 20))
        pygame.draw.rect(self._surf, (210, 40, 40, 230), (18, H-46, int(200*hp), 20))
        pygame.draw.rect(self._surf, (255, 255, 255, 60), (18, H-46, 200, 20), 1)
        t = self.font_small.render(f'HP {player.health}', True, (255, 255, 255))
        self._surf.blit(t, (22, H-44))

        cd_pct = 1.0 - min(1.0, player._shoot_timer / player.SHOOT_CD)
        pygame.draw.rect(self._surf, (30, 30, 80, 200), (18, H-22, 80, 8))
        pygame.draw.rect(self._surf, (80, 120, 255, 220), (18, H-22, int(80*cd_pct), 8))

        phase_colors = {"BOSS_ALERT": (255, 50, 50), "FRENZY": (220, 40, 20),
                        "RETREAT": (150, 40, 210), "CALM": (50, 120, 210)}
        phase_color = phase_colors.get(overmind.phase, (200, 200, 200))
        pygame.draw.rect(self._surf, (50, 50, 50, 180), (W-180, 12, 168, 32), border_radius=4)
        t = self.font_med.render(f'HIVE: {overmind.phase}', True, phase_color)
        self._surf.blit(t, (W-170, 16))

        if player.current_room:
            room_label = f'Room {player.current_room.id}'
            if player.current_room.is_boss_room:
                room_label += ' ⚠ BOSS'
            elif player.current_room.is_start:
                room_label += ' 🏠 START'
            t = self.font_small.render(room_label, True, (200, 200, 200))
            self._surf.blit(t, (18, 12))

        alive_count = sum(1 for e in enemies if e.alive)
        active_count = sum(1 for e in enemies if e.alive and e.active)
        boss_count = sum(1 for e in enemies if e.alive and e.unit_class.is_boss)
        t = self.font_small.render(f'ENEMIES: {alive_count}  ACTIVE: {active_count}  BOSSES: {boss_count}', 
                                   True, (200, 200, 200))
        self._surf.blit(t, (W-270, 50))

        if not player.alive:
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            s.fill((0, 0, 0, 160))
            self._surf.blit(s, (0, 0))
            t = self.font_big.render('YOU DIED', True, (220, 50, 50))
            self._surf.blit(t, (W//2 - t.get_width()//2, H//2 - 40))
            t2 = self.font_med.render('Press R to restart', True, (200, 200, 200))
            self._surf.blit(t2, (W//2 - t2.get_width()//2, H//2 + 10))

        hint = self.font_small.render(
            'WASD | Mouse | LMB Shoot | Space Jump | L Invert | R Restart | ESC Quit',
            True, (120, 120, 120))
        self._surf.blit(hint, (W//2 - hint.get_width()//2, H-18))

        screen.blit(self._surf, (0, 0))


# ═══════════════════════════════════════════════════════════════════════════════
#  ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class SpikelingDungeonEngine:
    W, H = 1280, 720
    FPS = 60
    TITLE = 'Spikeling Dungeon FPS - AAA'

    def __init__(self):
        self.dungeon = Dungeon(num_rooms=400, seed=42)
        self.player = Player()
        start_room = self.dungeon.rooms[(0, 0)]
        spawn_pos = self.dungeon.spawn_position_in(start_room)
        self.player.pos = v3(spawn_pos[0], Player.HEIGHT, spawn_pos[2])
        self.player.current_room = start_room
        self.overmind = Overmind(self.dungeon)
        self.enemies = []
        self._spawn_enemies()
        self._frame_count = 0

    def _spawn_enemies(self):
        for room in self.dungeon.rooms_by_id:
            if room.is_start:
                continue
            
            if room.is_boss_room:
                boss_pos = self.dungeon.spawn_position_in(room)
                boss = Enemy(f'Boss_{room.id}', boss_pos, UNIT_CLASSES['boss'], room)
                self.enemies.append(boss)
                for i in range(3):
                    pos = self.dungeon.spawn_position_in(room)
                    self.enemies.append(Enemy(f'Minion_{room.id}_{i}', pos, 
                                              UNIT_CLASSES['elite'], room))
                continue
            
            dist_from_start = math.sqrt(room.cx**2 + room.cz**2)
            if dist_from_start < 2:
                continue
            elif dist_from_start < 5:
                count = 1
                unit_type = 'grunt'
            elif dist_from_start < 10:
                count = 2 if room.kind == 'ambush' else 1
                unit_type = 'soldier'
            else:
                count = 3 if room.kind == 'ambush' else 2
                unit_type = 'elite' if room.kind == 'ambush' else 'soldier'
            
            if room.kind == 'ambush':
                unit_type = random.choice(['elite', 'soldier', 'fast'])
            
            for i in range(count):
                pos = self.dungeon.spawn_position_in(room)
                self.enemies.append(Enemy(f'{unit_type}_{room.id}_{i}', pos,
                                          UNIT_CLASSES[unit_type], room))
        
        print(f"✓ Spawned {len(self.enemies)} enemies")

    def _check_hits(self):
        for proj in self.player.projectiles[:]:
            if not proj.alive:
                continue
            for e in self.enemies:
                if not e.alive:
                    continue
                if dist(proj.pos, e.pos + v3(0, e.unit_class.height, 0)) < e.unit_class.width + proj.RADIUS + 0.3:
                    e.take_damage(proj.DAMAGE)
                    proj.alive = False
                    break

    def _restart(self):
        self.player = Player()
        start_room = self.dungeon.rooms[(0, 0)]
        spawn_pos = self.dungeon.spawn_position_in(start_room)
        self.player.pos = v3(spawn_pos[0], Player.HEIGHT, spawn_pos[2])
        self.player.current_room = start_room
        self.enemies = []
        self._spawn_enemies()

    def run(self):
        pygame.init()
        screen = pygame.display.set_mode((self.W, self.H), DOUBLEBUF | OPENGL)
        pygame.display.set_caption(self.TITLE)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glShadeModel(GL_SMOOTH)
        setup_lighting()

        hud = HUD(self.W, self.H)
        clock = pygame.time.Clock()

        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)

        running = True
        while running:
            dt = min(clock.tick(self.FPS) / 1000.0, 0.05)
            self._frame_count += 1

            for ev in pygame.event.get():
                if ev.type == QUIT:
                    running = False
                elif ev.type == KEYDOWN:
                    if ev.key == K_ESCAPE:
                        running = False
                    if ev.key == K_l:
                        self.player.toggle_invert()
                    if ev.key == K_r and not self.player.alive:
                        self._restart()
                elif ev.type == MOUSEBUTTONDOWN:
                    if ev.button == 1 and self.player.alive:
                        self.player.shoot()

            dx, dy = pygame.mouse.get_rel()
            SENS = 0.15
            yaw_dx = -dx if not self.player.invert_yaw else dx
            self.player.yaw = (self.player.yaw + yaw_dx * SENS) % 360
            self.player.pitch = max(-89, min(89, self.player.pitch - dy * SENS))

            if self.player.alive:
                keys = pygame.key.get_pressed()
                yaw = math.radians(self.player.yaw)
                fwd = v3(-math.sin(yaw), 0, -math.cos(yaw))
                rgt = v3(math.cos(yaw), 0, -math.sin(yaw))
                move = v3()
                if keys[K_w]: move += fwd
                if keys[K_s]: move -= fwd
                if keys[K_a]: move -= rgt
                if keys[K_d]: move += rgt
                n = np.linalg.norm(move)
                if n > 0: move /= n
                self.player.vel[0] = move[0] * self.player.MOVE_SPEED
                self.player.vel[2] = move[2] * self.player.MOVE_SPEED
                if keys[K_SPACE] and self.player._on_ground:
                    self.player.vel[1] = self.player.JUMP_FORCE

            now = time.time()
            directive = self.overmind.get_global_directive(self.player, self.enemies, now)
            
            self.player.update(dt, self.dungeon)
            
            for e in self.enemies:
                e.update(dt, self.player, directive, self.dungeon, now)

            self._check_hits()

            glClearColor(0.05, 0.05, 0.10, 1)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            p = self.player
            set_camera(p.eye[0], p.eye[1], p.eye[2], p.yaw, p.pitch)

            current_room = self.dungeon.room_at(p.pos)
            visible_rooms = self.dungeon.visible_rooms(current_room, max_hops=3, max_rooms=40)
            
            for room in visible_rooms:
                for box in room.boxes:
                    draw_box(*box)

            visible_room_ids = {r.id for r in visible_rooms}
            for e in self.enemies:
                if e.room.id in visible_room_ids or e.active:
                    e.draw()

            for proj in self.player.projectiles:
                if proj.alive:
                    proj.draw()

            if self._frame_count % 2 == 0:
                hud.draw(screen, self.player, self.enemies, self.overmind, self.dungeon)

            pygame.display.flip()

        pygame.quit()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    engine = SpikelingDungeonEngine()
    engine.run()