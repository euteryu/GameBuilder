# player.py
import pygame
import pymunk
from pymunk import Vec2d
import time
import os

# --- Constants ---
# Physics
PLAYER_RADIUS = 15
PLAYER_MASS = 1.0; PLAYER_FRICTION = 0.6; PLAYER_ELASTICITY = 0.0
PLAYER_MAX_HEALTH = 3
PLAYER_INVINCIBILITY_DURATION = 1.0

# Sprite / Animation Constants
SPRITESHEET_PATH = "assets/Ninja_10KStudios/facing_fwd/Ninja_10KStudios_fwd_spritesheet.png"
FRAME_WIDTH = 165; FRAME_HEIGHT = 165
SPRITE_SHEET_COLS = 10; SPRITE_SHEET_ROWS = 20
RUN_ANIM_FPS = 18; JUMP_ANIM_FPS = 16; IDLE_ANIM_FPS = 8; DEATH_ANIM_FPS = 25 # Faster death anim
PLAYER_SPRITE_SCALE = 0.5

ANIMATIONS = {
    "run":      (26, 17),
    "jump":     (43, 16),
    "idle":     (59, 16),
    "death":    (75, 55),
}
DEFAULT_ANIMATION = "idle"
NON_LOOPING_ANIMATIONS = {"death", "jump"}

# Movement Tuning Constants
MOVE_ACCELERATION = 3500; MAX_SPEED = 300
GROUND_DAMPING = 0.65; AIR_DAMPING = 0.95
STICKY_GROUND_DAMPING = 0.4
AIR_CONTROL_FACTOR = 0.6
STICKY_MOVE_FACTOR = 0.3; STICKY_JUMP_FACTOR = 0.5
JUMP_IMPULSE = 600; ENABLE_VARIABLE_JUMP = True
VARIABLE_JUMP_MULTIPLIER = 0.4; VARIABLE_JUMP_TIME = 0.3
COYOTE_TIME_LIMIT = 0.1; JUMP_BUFFER_LIMIT = 0.1
STUCK_VELOCITY_THRESHOLD = 5.0; STUCK_TIME_THRESHOLD = 0.2
NUDGE_IMPULSE_STRENGTH = 100.0


# --- Helper Function ---
def load_sliced_sprites_grid(filename, frame_width, frame_height, cols, rows):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Adjust path if needed, assuming player.py is at project root relative to assets
        project_root = script_dir
        filepath = os.path.join(project_root, filename)
        print(f"Attempting to load spritesheet from calculated path: {filepath}")
        if not os.path.exists(filepath):
             print(f"Error: File not found at calculated path: {filepath}")
             alt_filepath = os.path.join(os.path.dirname(script_dir), filename)
             print(f"Trying alternative path: {alt_filepath}")
             if not os.path.exists(alt_filepath): print(f"Error: File not found at alternative path either."); return None
             else: filepath = alt_filepath
        spritesheet = pygame.image.load(filepath)
    except Exception as e: print(f"Error loading spritesheet '{filename}': {e}"); return None
    spritesheet = spritesheet.convert_alpha()
    frames = []
    for row_idx in range(rows):
        for col_idx in range(cols):
            rect = pygame.Rect(col_idx * frame_width, row_idx * frame_height, frame_width, frame_height)
            frame = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA); frame.blit(spritesheet, (0, 0), rect)
            frames.append(frame)
    if frames: print(f"Successfully loaded and converted {len(frames)} frames from {filename}")
    else: print(f"Warning: Loaded 0 frames from {filename}, dimensions might be wrong.")
    return frames

# --- Player Class ---
class Player:
    SPRITE_FRAMES = None
    FALLBACK_FRAME = None

    @classmethod
    def load_assets(cls):
        if cls.SPRITE_FRAMES is None:
            print("Loading player assets...")
            cls.SPRITE_FRAMES = load_sliced_sprites_grid(SPRITESHEET_PATH, FRAME_WIDTH, FRAME_HEIGHT, SPRITE_SHEET_COLS, SPRITE_SHEET_ROWS)
            if not cls.SPRITE_FRAMES:
                print("Error: Failed to load player spritesheet! Using fallback.")
                fallback_surf = pygame.Surface((30, 30), pygame.SRCALPHA); pygame.draw.circle(fallback_surf, (0, 200, 255), (15, 15), 15)
                cls.SPRITE_FRAMES = [fallback_surf]; cls.FALLBACK_FRAME = fallback_surf
                global ANIMATIONS, DEFAULT_ANIMATION, NON_LOOPING_ANIMATIONS
                ANIMATIONS = {"idle": (0, 1)}; DEFAULT_ANIMATION = "idle"; NON_LOOPING_ANIMATIONS = {}
            else: cls.FALLBACK_FRAME = cls.SPRITE_FRAMES[0]

    def __init__(self, position, space, collision_type_id, collision_types_dict):
        if Player.SPRITE_FRAMES is None: raise RuntimeError("Player assets not loaded!")
        self.body = pymunk.Body(PLAYER_MASS, float('inf')); self.body.position = position
        self.shape = pymunk.Circle(self.body, PLAYER_RADIUS)
        self.shape.elasticity = PLAYER_ELASTICITY; self.shape.friction = PLAYER_FRICTION
        self.shape.collision_type = collision_type_id; self.shape.filter = pymunk.ShapeFilter(group=1, categories=0b1)
        space.add(self.body, self.shape)
        self.shape.game_object_ref = self; self.body.game_object_ref = self
        self.collision_types = collision_types_dict
        self.max_health = PLAYER_MAX_HEALTH; self.health = self.max_health
        self.invincible_timer = 0.0; self.on_ground = False
        self.is_on_sticky_ground = False; self.last_on_ground_time = 0.0
        self.jump_requested_time = -1.0; self.is_holding_jump = False
        self.variable_jump_timer = 0.0; self.stuck_timer = 0.0; self._horizontal_intent = 0
        self.current_animation_name = DEFAULT_ANIMATION; self.current_frame_index_in_sequence = 0
        self.animation_timer = 0.0; self.facing_right = True; self.animation_finished = False
        self.is_dead = False; self.jump_start_y = 0.0; self.jump_peak_y = 0.0; self.is_jumping_state = False

    def reset_state(self, position):
        self.body.position = position; self.body.velocity = Vec2d.zero(); self.body.angular_velocity = 0
        self.health = self.max_health; self.invincible_timer = 0.0; self.on_ground = False
        self.is_on_sticky_ground = False; self.last_on_ground_time = 0.0
        self.jump_requested_time = -1.0; self.is_holding_jump = False; self.variable_jump_timer = 0.0
        self.stuck_timer = 0.0; self._horizontal_intent = 0
        self.current_animation_name = DEFAULT_ANIMATION; self.current_frame_index_in_sequence = 0
        self.animation_timer = 0.0; self.facing_right = True; self.animation_finished = False
        self.is_dead = False; self.is_jumping_state = False

    def teleport_and_reset_physics(self, position):
        self.body.position = position; self.body.velocity = Vec2d.zero(); self.body.angular_velocity = 0
        self.is_jumping_state = False; self.set_animation("idle")

    # --- MODIFIED take_damage ---
    def take_damage(self, amount=1):
        if self.is_dead: return False # Already dead
        if self.invincible_timer <= 0:
            self.health -= amount
            self.invincible_timer = PLAYER_INVINCIBILITY_DURATION
            print(f"Player took damage! Health: {self.health}")
            if self.health <= 0:
                if not self.is_dead: # Check to prevent setting multiple times
                    print("Player health depleted. Triggering death sequence.")
                    self.is_dead = True
                    self.set_animation("death") # Start death animation
                    self.body.velocity = Vec2d.zero() # Stop movement immediately on death
            return True # Damage was processed
        return False # Was invincible

    def _update_ground_contact(self, space):
        # (Unchanged from previous working version)
        ground_contact_info = {'found': False, 'is_sticky': False}
        def check_arbiter_for_ground(arbiter):
            if not hasattr(self, 'collision_types'): return
            if ground_contact_info['found'] and not ground_contact_info['is_sticky']: return
            contact_normal = arbiter.contact_point_set.normal; is_player_shape_a = arbiter.shapes[0] == self.shape
            other_shape = arbiter.shapes[1] if is_player_shape_a else arbiter.shapes[0]
            is_ground_contact = False
            if is_player_shape_a and contact_normal.y > 0.7: is_ground_contact = True
            elif not is_player_shape_a and contact_normal.y < -0.7: is_ground_contact = True
            if is_ground_contact:
                is_platform = other_shape.body.body_type in (pymunk.Body.STATIC, pymunk.Body.KINEMATIC)
                try: is_danger_shape = other_shape.collision_type == self.collision_types['danger']
                except KeyError: is_danger_shape = False
                except AttributeError: is_danger_shape = False
                if is_platform or is_danger_shape:
                    ground_contact_info['found'] = True
                    if hasattr(other_shape, 'game_object_ref') and other_shape.game_object_ref:
                        if other_shape.game_object_ref.properties.get('Sticky', False): ground_contact_info['is_sticky'] = True
        self.body.each_arbiter(check_arbiter_for_ground)
        self.on_ground = ground_contact_info['found']; self.is_on_sticky_ground = ground_contact_info['is_sticky']

    # --- MODIFIED handle_input ---
    def handle_input(self, keys, dt):
        if self.is_dead: return # No input if dead

        # (Rest of input handling remains the same)
        current_time = time.time(); self._horizontal_intent = 0
        if keys[pygame.K_SPACE]:
            if self.jump_requested_time < 0 and not self.is_holding_jump: self.jump_requested_time = current_time
            self.is_holding_jump = True
        else: self.is_holding_jump = False
        if self.jump_requested_time > 0 and current_time - self.jump_requested_time > JUMP_BUFFER_LIMIT: self.jump_requested_time = -1.0
        target_vx_intent = 0
        if keys[pygame.K_LEFT]: target_vx_intent -= 1; self.facing_right = False
        if keys[pygame.K_RIGHT]: target_vx_intent += 1; self.facing_right = True
        self._horizontal_intent = target_vx_intent
        move_factor = STICKY_MOVE_FACTOR if self.is_on_sticky_ground else 1.0
        current_move_acceleration = MOVE_ACCELERATION * move_factor
        control_factor = 1.0 if self.on_ground else AIR_CONTROL_FACTOR
        acceleration_force_x = target_vx_intent * current_move_acceleration * control_factor
        self.body.apply_force_at_local_point((acceleration_force_x, 0), (0, 0))
        apply_damping = (target_vx_intent == 0)
        if apply_damping:
            if self.on_ground: damping = STICKY_GROUND_DAMPING if self.is_on_sticky_ground else GROUND_DAMPING
            else: damping = AIR_DAMPING
            self.body.velocity = Vec2d(self.body.velocity.x * damping, self.body.velocity.y)
        elif abs(self.body.velocity.x) > MAX_SPEED: clamped_vx = max(-MAX_SPEED, min(MAX_SPEED, self.body.velocity.x)); self.body.velocity = Vec2d(clamped_vx, self.body.velocity.y)
        can_jump_from_state = self.on_ground or (current_time - self.last_on_ground_time <= COYOTE_TIME_LIMIT)
        should_jump = self.jump_requested_time > 0
        if should_jump and can_jump_from_state:
             jump_factor = STICKY_JUMP_FACTOR if self.is_on_sticky_ground else 1.0; current_jump_impulse = JUMP_IMPULSE * jump_factor
             self.body.velocity = Vec2d(self.body.velocity.x, -current_jump_impulse)
             self.jump_requested_time = -1.0; self.last_on_ground_time = -1.0; self.variable_jump_timer = VARIABLE_JUMP_TIME if self.is_holding_jump else 0
             self.is_jumping_state = True; self.jump_start_y = self.body.position.y; self.jump_peak_y = self.body.position.y

    def set_animation(self, name):
        if self.is_dead and name != "death": return # Don't change from death anim
        if name in ANIMATIONS and self.current_animation_name != name:
            self.current_animation_name = name; self.current_frame_index_in_sequence = 0
            self.animation_timer = 0.0; self.animation_finished = False

    def update_animation(self, dt):
        # (Unchanged from previous version)
        if self.current_animation_name not in ANIMATIONS: return
        if self.animation_finished: return
        start_frame, frame_count = ANIMATIONS[self.current_animation_name]
        if frame_count <= 0: return

        if self.current_animation_name == "jump":
            current_y = self.body.position.y
            if self.body.velocity.y < 0: # Moving up
                self.jump_peak_y = min(self.jump_peak_y, current_y)
                progress = 0.0
                if self.jump_start_y > self.jump_peak_y: progress = pygame.math.clamp((self.jump_start_y - current_y) / (self.jump_start_y - self.jump_peak_y), 0.0, 1.0) * 0.5
                else: progress = 0.0
            else: # Moving down
                if self.jump_start_y > self.jump_peak_y: progress = 0.5 + pygame.math.clamp((current_y - self.jump_peak_y) / (self.jump_start_y - self.jump_peak_y), 0.0, 1.0) * 0.5
                else: progress = 1.0
            progress = pygame.math.clamp(progress, 0.0, 1.0)
            self.current_frame_index_in_sequence = int(progress * (frame_count - 1))
        else: # Timer-based animation
            if self.current_animation_name == "run": anim_fps = RUN_ANIM_FPS
            elif self.current_animation_name == "death": anim_fps = DEATH_ANIM_FPS
            else: anim_fps = IDLE_ANIM_FPS
            time_per_frame = 1.0 / anim_fps if anim_fps > 0 else float('inf')
            self.animation_timer += dt
            while self.animation_timer >= time_per_frame:
                if self.animation_finished: self.animation_timer = 0; break
                self.animation_timer -= time_per_frame; self.current_frame_index_in_sequence += 1
                if self.current_frame_index_in_sequence >= frame_count:
                    if self.current_animation_name in NON_LOOPING_ANIMATIONS: self.current_frame_index_in_sequence = frame_count - 1; self.animation_finished = True
                    else: self.current_frame_index_in_sequence = 0

    # --- MODIFIED update ---
    def update(self, dt, space):
        """ Updates player state, handling death animation. """
        # --- Update Animation First, especially for Death ---
        # This ensures the death animation progresses even if other updates are skipped
        self.update_animation(dt)

        # --- Freeze player after death animation finishes ---
        if self.is_dead and self.animation_finished:
            # Ensure velocity stays zero after death animation completes
            if self.body.velocity.length > 0.1: # Small threshold
                 self.body.velocity = Vec2d.zero()
            return # Skip other updates

        # --- Skip physics/state updates if dead (but animation not finished) ---
        if self.is_dead:
            # Ensure velocity is zero during death animation
            if self.body.velocity.length > 0.1:
                 self.body.velocity = Vec2d.zero()
            return # Only animation updates happen when dead

        # --- Normal Updates (Invincibility, Ground Check, etc.) ---
        if self.invincible_timer > 0: self.invincible_timer -= dt; self.invincible_timer = max(0, self.invincible_timer)
        was_on_ground = self.on_ground; self._update_ground_contact(space)
        if self.on_ground and not was_on_ground: self.last_on_ground_time = time.time(); self.is_jumping_state = False
        if self.on_ground: self.variable_jump_timer = 0
        elif ENABLE_VARIABLE_JUMP and self.is_holding_jump and self.variable_jump_timer > 0 and self.body.velocity.y < 0:
             gravity = space.gravity;
             if gravity.y > 0: counter_gravity_force_y = -gravity.y*self.body.mass*(1.0-VARIABLE_JUMP_MULTIPLIER); self.body.apply_force_at_local_point((0, counter_gravity_force_y), (0,0))
             self.variable_jump_timer -= dt; self.variable_jump_timer = max(0, self.variable_jump_timer)
        else: self.variable_jump_timer = 0
        current_vel_magnitude_sq = self.body.velocity.dot(self.body.velocity); is_slow = current_vel_magnitude_sq < (STUCK_VELOCITY_THRESHOLD**2)
        if is_slow and self.on_ground and self._horizontal_intent != 0: self.stuck_timer += dt;
        if self.stuck_timer >= STUCK_TIME_THRESHOLD: self.body.apply_impulse_at_local_point((0, -NUDGE_IMPULSE_STRENGTH), (0, 0)); self.stuck_timer = 0
        elif not (is_slow and self.on_ground and self._horizontal_intent != 0): self.stuck_timer = 0 # Reset if condition not met
        if was_on_ground == False and self.on_ground == True: self.is_jumping_state = False

        # --- Determine Logical Animation State ---
        new_anim_name = self.current_animation_name # Default to current
        # Death state is handled by take_damage, don't override here
        if not self.is_dead: # Only change animation if not in death sequence
            if self.is_jumping_state or not self.on_ground: new_anim_name = "jump"
            else: # On ground
                 if self._horizontal_intent != 0: new_anim_name = "run"
                 else: new_anim_name = "idle"
            self.set_animation(new_anim_name)
        # Note: update_animation was already called at the beginning


    # --- MODIFIED draw ---
    def draw(self, screen, offset, screen_width, screen_height):
        """ Draws the correct player sprite frame at the physics body's location. """
        frame_list = Player.SPRITE_FRAMES; fallback_frame = Player.FALLBACK_FRAME
        if not frame_list:
            if fallback_frame: frame_list = [fallback_frame]
            else: return

        anim_name = self.current_animation_name
        if anim_name not in ANIMATIONS: anim_name = DEFAULT_ANIMATION
        start_frame, frame_count = ANIMATIONS.get(anim_name, (0, 1))
        if frame_count <= 0: frame_count = 1

        current_relative_idx = max(0, min(self.current_frame_index_in_sequence, frame_count - 1))
        absolute_frame_idx = start_frame + current_relative_idx

        if 0 <= absolute_frame_idx < len(frame_list): original_frame = frame_list[absolute_frame_idx]
        else: print(f"Draw Warning: Frame index out of bounds! Anim: {anim_name}, Abs Idx: {absolute_frame_idx}, List len: {len(frame_list)}"); original_frame = fallback_frame or frame_list[0]

        if PLAYER_SPRITE_SCALE != 1.0:
             new_size = (int(original_frame.get_width() * PLAYER_SPRITE_SCALE), int(original_frame.get_height() * PLAYER_SPRITE_SCALE))
             try: frame_to_draw = pygame.transform.smoothscale(original_frame, new_size)
             except ValueError: frame_to_draw = pygame.transform.scale(original_frame, new_size)
        else: frame_to_draw = original_frame

        if not self.facing_right: frame_to_draw = pygame.transform.flip(frame_to_draw, True, False)

        body_pos_screen = self.body.position - offset
        sprite_width = frame_to_draw.get_width(); sprite_height = frame_to_draw.get_height()
        draw_x = body_pos_screen.x - sprite_width / 2; draw_y = (body_pos_screen.y + PLAYER_RADIUS) - sprite_height

        if draw_x + sprite_width >= 0 and draw_x <= screen_width and draw_y + sprite_height >= 0 and draw_y <= screen_height:
            # --- Don't show invincibility flash when dead ---
            if self.invincible_timer > 0 and int(time.time() * 10) % 2 == 0 and not self.is_dead:
                 tint_surf = frame_to_draw.copy(); tint_surf.fill((255, 50, 50, 100), special_flags=pygame.BLEND_RGBA_ADD); screen.blit(tint_surf, (int(draw_x), int(draw_y)))
            else: screen.blit(frame_to_draw, (int(draw_x), int(draw_y)))
            # Debug Draw Hitbox
            # pygame.draw.circle(screen, (255, 0, 0, 100), body_pos_screen, PLAYER_RADIUS, 1)

    def add_to_space(self, space):
        if self.body not in space.bodies: space.add(self.body)
        if self.shape not in space.shapes: space.add(self.shape)

    def remove_from_space(self, space):
        if self.shape in space.shapes: space.remove(self.shape)
        if self.body in space.bodies: space.remove(self.body)