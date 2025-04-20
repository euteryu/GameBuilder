# game_world.py
import pygame
import pymunk
from pymunk import Vec2d
import json
import os
import math # Needed for ceil

# Import the classes we just created
from player import Player
from shape import Shape

# Constants needed by GameWorld
# Map Dimensions
MAP_WIDTH = 2000
MAP_HEIGHT = 1000
# Boundary settings
BOUNDARY_THICKNESS = 10; BOUNDARY_COLOR = (0, 0, 0)
BOUNDARY_FRICTION = 1.0; BOUNDARY_ELASTICITY = 0.1
# Collision Types Dictionary
COLLISION_TYPES = { 'player': 1, 'shape_normal': 2, 'shape_danger': 3, 'boundary': 0 }
# Player specific constants
PLAYER_RADIUS = 15
# Marker/Checkpoint visual constants
CHECKPOINT_COLOR = (200, 200, 0, 180); CHECKPOINT_ACTIVE_COLOR = (255, 255, 100, 220)
CHECKPOINT_RADIUS = 18
# Heart image loading
HEART_IMG = None
try:
    HEART_IMG = pygame.Surface((24, 24), pygame.SRCALPHA); pygame.draw.circle(HEART_IMG, (255, 0, 0), (12, 12), 10); pygame.draw.circle(HEART_IMG, (200, 0, 0), (12, 12), 10, 2)
except Exception as e: print(f"Warning: Could not load/create heart image: {e}")
TOOLBAR_HEIGHT = 60 # For UI positioning

# --- Parallax Background Constants ---
# Adjust filenames and paths as needed
PARALLAX_LAYERS_INFO = [
    {"file": "assets/backgrounds/background_back.png",   "factor": 0.1, "scale": 3.0},
    {"file": "assets/backgrounds/background_middle.png", "factor": 0.4, "scale": 3.0},
    {"file": "assets/backgrounds/background_front.png",  "factor": 0.8, "scale": 3.0}
]

class GameWorld:
    """
    Manages the physics space, game objects (player, shapes), level data,
    collision handling, camera, and drawing the world elements including parallax background.
    """
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Physics Space
        self.space = pymunk.Space(); self.space.gravity = (0, 0); self.space.iterations = 15

        # Game Objects & Level Data
        self.player = None; self.shapes = []; self.start_marker = None; self.end_marker = None
        self.checkpoints = []    # List of Vec2d world coordinates
        self.last_checkpoint_activated = None # Store the Vec2d world coordinate

        # Camera
        self.camera_offset = Vec2d(0, 0); self.reset_camera()

        # Boundaries
        self._boundary_segments = []; self._create_boundaries()

        # Collision Handlers
        self._setup_collision_handlers()

        # Fonts
        self.marker_font = pygame.font.SysFont(None, 24); self.checkpoint_font = pygame.font.SysFont(None, 20)

        # Game state flags
        self.player_needs_respawn = False

        # --- Load Parallax Backgrounds ---
        self.parallax_layers = self._load_parallax_layers(PARALLAX_LAYERS_INFO)

    def _load_parallax_layers(self, layer_infos):
        """Loads and scales parallax background images."""
        loaded_layers = []
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = script_dir # Adjust if game_world.py is not at root

        for info in layer_infos:
            try:
                filepath = os.path.join(project_root, info["file"])
                print(f"Loading parallax layer: {filepath}")
                if not os.path.exists(filepath):
                    alt_filepath = os.path.join(os.path.dirname(script_dir), info["file"])
                    print(f"File not found, trying alternative: {alt_filepath}")
                    if not os.path.exists(alt_filepath): raise FileNotFoundError(f"Cannot find parallax layer: {info['file']}")
                    else: filepath = alt_filepath
                img = pygame.image.load(filepath).convert_alpha()
                scale = info.get("scale", 1.0)
                if scale != 1.0:
                    new_size = (int(img.get_width() * scale), int(img.get_height() * scale))
                    img = pygame.transform.scale(img, new_size)
                loaded_layers.append({ "image": img, "factor": info["factor"], "width": img.get_width(), "height": img.get_height() })
                print(f"Loaded layer '{info['file']}' scaled to {img.get_size()}")
            except Exception as e: print(f"Error loading parallax layer '{info['file']}': {e}")
        return loaded_layers

    def set_gravity(self, gravity_vec): self.space.gravity = gravity_vec
    def step_physics(self, dt): step_dt = 1.0 / 60.0; self.space.step(step_dt)

    def add_player(self, position):
        if self.player: self.player.remove_from_space(self.space)
        self.player = Player(position, self.space, COLLISION_TYPES['player'], COLLISION_TYPES)
        print("Player added to GameWorld")

    def ensure_player_in_space(self):
        if self.player: self.player.add_to_space(self.space)

    def remove_player(self):
        if self.player: self.player.remove_from_space(self.space); self.player = None; print("Player removed from GameWorld")

    def add_shape(self, shape_data):
        shape_type=shape_data.get('type'); pos_list=shape_data.get('position'); angle=shape_data.get('angle',0.0); properties=shape_data.get('properties',{}); size_list=shape_data.get('size'); radius=shape_data.get('radius'); vertices=shape_data.get('vertices')
        if not shape_type or not pos_list: return None
        position=Vec2d(*pos_list); new_shape = Shape(shape_type, position, self.space, properties, angle)
        if size_list: new_shape.size = Vec2d(*size_list)
        if radius is not None: new_shape.radius = radius
        if vertices: new_shape.vertices = [tuple(v) for v in vertices]
        if new_shape.body: self.shapes.append(new_shape); return new_shape
        else: print(f"Warning: Failed to create/add shape: {shape_data}"); return None

    def remove_shape(self, shape_instance):
        if shape_instance in self.shapes: shape_instance.remove_from_space(self.space); self.shapes.remove(shape_instance); print("Shape removed")

    def set_start_marker(self, position): self.start_marker = position
    def set_end_marker(self, position): self.end_marker = position
    def add_checkpoint(self, position):
        # Add print here for debugging placement
        print(f"GameWorld: Adding checkpoint at world pos: {position}")
        self.checkpoints.append(position)
        print(f"GameWorld: Checkpoints list size now: {len(self.checkpoints)}")

    def clear_level(self):
        self.remove_player();
        for shape in list(self.shapes): self.remove_shape(shape)
        self.shapes.clear(); self.start_marker = None; self.end_marker = None
        self.checkpoints = []; self.last_checkpoint_activated = None
        self.reset_camera(); print("GameWorld cleared")

    def get_spawn_position(self):
        spawn_pos_world = self.last_checkpoint_activated or self.start_marker
        if not spawn_pos_world: spawn_pos_world = Vec2d(MAP_WIDTH / 2, MAP_HEIGHT / 2); print("Warning: No start/checkpoint found, using fallback spawn.")
        safe_x = max(PLAYER_RADIUS + BOUNDARY_THICKNESS, min(spawn_pos_world.x, MAP_WIDTH - PLAYER_RADIUS - BOUNDARY_THICKNESS))
        safe_y = max(PLAYER_RADIUS + BOUNDARY_THICKNESS, min(spawn_pos_world.y, MAP_HEIGHT - PLAYER_RADIUS - BOUNDARY_THICKNESS))
        return Vec2d(safe_x, safe_y)

    def update_player_state(self, dt, keys):
        if self.player: self.player.handle_input(keys, dt); self.player.update(dt, self.space)

    # --- MODIFIED Checkpoint Update Logic ---
    def update_checkpoints(self):
        """Checks for player activating checkpoints."""
        if not self.player or not self.checkpoints: return

        player_pos_world = self.player.body.position
        activation_radius_sq = (PLAYER_RADIUS + CHECKPOINT_RADIUS) ** 2

        closest_activated_checkpoint = None
        min_dist_sq = float('inf')

        # Find the *closest* checkpoint the player is currently touching
        for cp_pos_world in self.checkpoints:
            delta_vec = player_pos_world - cp_pos_world
            distance_sq = delta_vec.dot(delta_vec)

            if distance_sq < activation_radius_sq:
                if distance_sq < min_dist_sq:
                    min_dist_sq = distance_sq
                    closest_activated_checkpoint = cp_pos_world

        # Now update last_checkpoint_activated only if the closest one found
        # is different from the currently stored one.
        if closest_activated_checkpoint:
            # Use integer tuple comparison for stability
            current_last_tuple = self.last_checkpoint_activated.int_tuple if self.last_checkpoint_activated else None
            activated_tuple = closest_activated_checkpoint.int_tuple

            if current_last_tuple != activated_tuple:
                print(f"Checkpoint Activated: {closest_activated_checkpoint}") # Print the Vec2d
                self.last_checkpoint_activated = closest_activated_checkpoint # Store the Vec2d

    def check_win_condition(self):
        if self.player and self.end_marker: end_marker_radius = 15; return (self.player.body.position - self.end_marker).length < PLAYER_RADIUS + end_marker_radius
        return False

    def check_fall_condition(self):
        if self.player and self.player.body.position.y > MAP_HEIGHT + PLAYER_RADIUS * 5: return True
        return False

    # Collision Handling
    def _setup_collision_handlers(self):
        handler = self.space.add_collision_handler(COLLISION_TYPES['player'], COLLISION_TYPES['shape_danger'])
        handler.begin = self._player_hit_danger_begin

    def _player_hit_danger_begin(self, arbiter, space, data):
        player_shape = arbiter.shapes[0] if arbiter.shapes[0].collision_type == COLLISION_TYPES['player'] else arbiter.shapes[1]
        if self.player and player_shape == self.player.shape:
            damage_taken = self.player.take_damage(1)
            if damage_taken and not self.player.is_dead:
                self.player_needs_respawn = True; # Flag for deferred respawn
                # print("Damage taken, flagging respawn.") # Reduced console spam
        return True

    # Respawn Logic
    def respawn_player(self):
        if not self.player: print("Error: Cannot respawn, player object missing."); return
        spawn_pos_world = self.last_checkpoint_activated or self.start_marker
        if not spawn_pos_world: spawn_pos_world = Vec2d(MAP_WIDTH / 2, MAP_HEIGHT / 2); print(f"Warning: No start/checkpoint, respawning at fallback: {spawn_pos_world}")
        safe_x = max(PLAYER_RADIUS + BOUNDARY_THICKNESS, min(spawn_pos_world.x, MAP_WIDTH - PLAYER_RADIUS - BOUNDARY_THICKNESS))
        safe_y = max(PLAYER_RADIUS + BOUNDARY_THICKNESS, min(spawn_pos_world.y, MAP_HEIGHT - PLAYER_RADIUS - BOUNDARY_THICKNESS))
        safe_spawn_pos_world = Vec2d(safe_x, safe_y)
        self.player.teleport_and_reset_physics(safe_spawn_pos_world)
        self.update_camera(force_center=True)

    # Camera
    def update_camera(self, force_center=False):
        if not self.player: return
        player_pos = self.player.body.position; screen_w = self.screen_width; screen_h = self.screen_height
        target_x = player_pos.x - screen_w / 2; target_y = player_pos.y - screen_h / 2
        clamped_x = max(0, min(target_x, MAP_WIDTH - screen_w)) if MAP_WIDTH > screen_w else 0
        clamped_y = max(0, min(target_y, MAP_HEIGHT - screen_h)) if MAP_HEIGHT > screen_h else 0
        new_offset = Vec2d(clamped_x, clamped_y)
        if force_center: self.camera_offset = new_offset
        else: self.camera_offset = self.camera_offset.interpolate_to(new_offset, 0.08)

    def reset_camera(self):
        cam_x = max(0, (MAP_WIDTH - self.screen_width) / 2) if MAP_WIDTH > self.screen_width else 0
        cam_y = max(0, (MAP_HEIGHT - self.screen_height) / 2) if MAP_HEIGHT > self.screen_height else 0
        cam_x = min(cam_x, MAP_WIDTH - self.screen_width) if MAP_WIDTH > self.screen_width else 0
        cam_y = min(cam_y, MAP_HEIGHT - self.screen_height) if MAP_HEIGHT > self.screen_height else 0
        self.camera_offset = Vec2d(cam_x, cam_y)

    # --- Drawing ---
    def _world_to_screen(self, world_pos): return world_pos - self.camera_offset
    def _screen_to_world(self, screen_pos): return Vec2d(screen_pos[0], screen_pos[1]) + self.camera_offset

    def draw(self, screen):
        """Draws parallax background, then world elements."""
        # 1. Draw Parallax Background Layers
        for layer in self.parallax_layers:
            image = layer["image"]; factor = layer["factor"]; img_width = layer["width"]; img_height = layer["height"]
            layer_offset_x = self.camera_offset.x * factor; start_x = -(layer_offset_x % img_width)
            tiles_needed = math.ceil(self.screen_width / img_width) + 1; draw_y = 0 # Top aligned
            for i in range(tiles_needed):
                blit_pos_x = start_x + (i * img_width)
                if blit_pos_x < self.screen_width and blit_pos_x + img_width > 0: screen.blit(image, (int(blit_pos_x), int(draw_y)))

        # 2. Draw Boundaries
        for segment in self._boundary_segments: p1_s=self._world_to_screen(segment.a); p2_s=self._world_to_screen(segment.b); pygame.draw.line(screen, BOUNDARY_COLOR, p1_s, p2_s, max(1, int(BOUNDARY_THICKNESS)))

        # 3. Draw Shapes
        visible_world_rect = pygame.Rect(self.camera_offset.x, self.camera_offset.y, self.screen_width, self.screen_height)
        for shape_obj in self.shapes:
             if shape_obj.shape and hasattr(shape_obj.shape, 'bb'):
                 shape_bb = shape_obj.shape.bb; shape_world_rect = pygame.Rect(shape_bb.left, shape_bb.top, shape_bb.right - shape_bb.left, shape_bb.bottom - shape_bb.top)
                 if shape_world_rect.colliderect(visible_world_rect): shape_obj.draw(screen, self.camera_offset)

        # 4. Draw Markers (Start, End, Checkpoints)
        if self.start_marker: pos_s=self._world_to_screen(self.start_marker);
        if 0<=pos_s.x<=self.screen_width and 0<=pos_s.y<=self.screen_height: pygame.draw.circle(screen, (0, 255, 0, 180), pos_s, 12); text=self.marker_font.render('S', True, (0,0,0)); r=text.get_rect(center=pos_s); screen.blit(text, r)
        if self.end_marker: pos_s=self._world_to_screen(self.end_marker);
        if 0<=pos_s.x<=self.screen_width and 0<=pos_s.y<=self.screen_height: pygame.draw.circle(screen, (255, 0, 0, 180), pos_s, 12); text=self.marker_font.render('E', True, (255,255,255)); r=text.get_rect(center=pos_s); screen.blit(text, r)
        # --- Add print inside checkpoint draw loop for debugging visibility ---
        for cp_pos_world in self.checkpoints:
            pos_s = self._world_to_screen(cp_pos_world)
            # print(f"Draw loop: CP World={cp_pos_world}, Screen={pos_s}") # DEBUG PRINT
            if 0 <= pos_s.x <= self.screen_width and 0 <= pos_s.y <= self.screen_height:
                is_active = (self.last_checkpoint_activated == cp_pos_world) # Compare Vec2d should be ok now
                color = CHECKPOINT_ACTIVE_COLOR if is_active else CHECKPOINT_COLOR
                pygame.draw.circle(screen, color, pos_s, CHECKPOINT_RADIUS)
                pygame.draw.circle(screen, (50,50,50), pos_s, CHECKPOINT_RADIUS, 2)
                text = self.checkpoint_font.render('C', True, (0,0,0)); r=text.get_rect(center=pos_s); screen.blit(text, r)

        # 5. Draw Player
        if self.player: self.player.draw(screen, self.camera_offset, self.screen_width, self.screen_height)


    def draw_hud(self, screen):
        if self.player and HEART_IMG: heart_x=15; heart_y=TOOLBAR_HEIGHT+15;
        for i in range(self.player.health): screen.blit(HEART_IMG, (heart_x + i * (HEART_IMG.get_width() + 5), heart_y))


    # Boundaries
    def _create_boundaries(self):
        for seg in self._boundary_segments:
            if seg in self.space.shapes: self.space.remove(seg)
        self._boundary_segments.clear(); static_body = self.space.static_body
        points = [(0, 0), (MAP_WIDTH, 0), (MAP_WIDTH, MAP_HEIGHT), (0, MAP_HEIGHT)]
        for i in range(4):
            p1 = points[i]; p2 = points[(i + 1) % 4]
            segment = pymunk.Segment(static_body, p1, p2, BOUNDARY_THICKNESS / 2)
            segment.elasticity = BOUNDARY_ELASTICITY; segment.friction = BOUNDARY_FRICTION
            segment.collision_type = COLLISION_TYPES['boundary']; segment.filter = pymunk.ShapeFilter(categories=0b100)
            self.space.add(segment); self._boundary_segments.append(segment)

    # Save / Load
    def save_level_data(self, filename="level.json"):
        print(f"Saving level data to {filename}...")
        level_data = {'start_marker': self.start_marker.int_tuple if self.start_marker else None,'end_marker': self.end_marker.int_tuple if self.end_marker else None,'checkpoints': [cp.int_tuple for cp in self.checkpoints],'shapes': [] }
        for shape_obj in self.shapes:
            if not shape_obj.body: continue
            shape_info={'type':shape_obj.shape_type,'position':shape_obj.body.position.int_tuple,'angle':shape_obj.body.angle,'properties':shape_obj.properties.copy(),'size':shape_obj.size.int_tuple if shape_obj.size else None,'radius':shape_obj.radius if shape_obj.radius is not None else None,'vertices':shape_obj.vertices if shape_obj.vertices else None}
            level_data['shapes'].append(shape_info)
        try:
            with open(filename, 'w') as f: json.dump(level_data, f, indent=4); print(f"Level data saved successfully.")
        except Exception as e: print(f"Error saving level data: {e}")

    def load_level_data(self, filename="level.json"):
        if not os.path.exists(filename): print(f"Error: Save file '{filename}' not found."); return False
        print(f"Loading level data from {filename}...")
        self.clear_level()
        try:
            with open(filename, 'r') as f: level_data = json.load(f)
            if level_data.get('start_marker'): self.start_marker = Vec2d(*level_data['start_marker'])
            if level_data.get('end_marker'): self.end_marker = Vec2d(*level_data['end_marker'])
            loaded_checkpoints = level_data.get('checkpoints', [])
            self.checkpoints = [Vec2d(*cp_tuple) for cp_tuple in loaded_checkpoints]
            print(f"Loaded {len(self.checkpoints)} checkpoints: {self.checkpoints}") # DEBUG PRINT
            loaded_shapes_data = level_data.get('shapes', [])
            count = 0
            for shape_data in loaded_shapes_data:
                if self.add_shape(shape_data): count += 1
            print(f"Level loaded successfully. {count} shapes, {len(self.checkpoints)} checkpoints loaded.")
            return True
        except Exception as e: print(f"An unexpected error occurred during loading: {e}"); import traceback; traceback.print_exc(); self.clear_level(); return False