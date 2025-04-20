# shape.py
import pygame
import pymunk
from pymunk import Vec2d

# Constants
SHAPE_DEFAULT_SIZE = 80 # Base size used for default triangle vertices
COLLISION_TYPES_DICT = { 'normal': 2, 'danger': 3 }

class Shape:
    """ Represents static or kinematic shapes in the level editor. """
    def __init__(self, shape_type, position, space, properties, angle=0.0,
                 size_params=None): # Size params can now include 'scale'
        self.shape_type = shape_type; self.properties = properties.copy(); self.selected = False

        # Store defining parameters
        self.size = None      # Rectangle (Vec2d)
        self.radius = None    # Circle (float)
        # --- Triangle Specific ---
        self.original_vertices = None # Store the canonical, unscaled vertices
        self.vertices = None          # Store the CURRENT runtime scaled vertices
        self.scale = 1.0              # Triangle scale factor

        initial_pos = position
        initial_angle = angle

        # Determine initial size/scale
        if shape_type == 'Rectangle':
            self.size = size_params.get('size', Vec2d(SHAPE_DEFAULT_SIZE, SHAPE_DEFAULT_SIZE)) if size_params else Vec2d(SHAPE_DEFAULT_SIZE, SHAPE_DEFAULT_SIZE)
        elif shape_type == 'Circle':
            self.radius = size_params.get('radius', SHAPE_DEFAULT_SIZE // 2) if size_params else SHAPE_DEFAULT_SIZE // 2
        elif shape_type == 'Triangle':
            s = SHAPE_DEFAULT_SIZE # Base size for canonical vertices
            # Define the UN SCALED, canonical vertices relative to (0,0)
            self.original_vertices = [Vec2d(-s//2, s//3), Vec2d(s//2, s//3), Vec2d(0, -2*s//3)] # Example equilateral base, adjust as needed
            # Apply initial scale if provided (e.g., loading from save)
            self.scale = size_params.get('scale', 1.0) if size_params else 1.0
            # Calculate initial runtime vertices
            self._update_scaled_vertices()

        # Create physics objects
        self.body = None; self.shape = None
        self._recreate_physics_objects(space, initial_pos, initial_angle)

    # --- NEW: Helper for Triangles ---
    def _update_scaled_vertices(self):
        """ Calculates self.vertices based on self.original_vertices and self.scale. """
        if self.shape_type == 'Triangle' and self.original_vertices:
            # Multiply each original vertex vector by the scale factor
            self.vertices = [(v * self.scale) for v in self.original_vertices]
        else:
            # Ensure self.vertices is None if not a triangle or no originals
            self.vertices = None

    def _recreate_physics_objects(self, space, position, angle):
        """Internal helper to create/recreate Pymunk body and shape."""
        self.remove_from_space(space) # Remove existing first

        is_spinning = self.properties.get('Spinning', False)
        current_body_type = pymunk.Body.KINEMATIC if is_spinning else pymunk.Body.STATIC
        self.body = pymunk.Body(body_type=current_body_type)
        self.body.position = position; self.body.angle = angle

        shape_created = False
        if self.shape_type == 'Rectangle' and self.size:
            self.shape = pymunk.Poly.create_box(self.body, self.size); shape_created = True
        elif self.shape_type == 'Circle' and self.radius is not None:
             safe_radius = max(1, self.radius); self.shape = pymunk.Circle(self.body, safe_radius); shape_created = True
        elif self.shape_type == 'Triangle' and self.vertices: # Use the current self.vertices
             # Ensure vertices are valid (e.g., enough points, not collinear - Pymunk checks convexity)
             if len(self.vertices) >= 3:
                 try:
                     # Convert Vec2d vertices back to tuples for Pymunk Poly if needed by version
                     # tuple_vertices = [v.int_tuple for v in self.vertices] # Or just v if Poly accepts Vec2d
                     self.shape = pymunk.Poly(self.body, self.vertices); shape_created = True # Pymunk often accepts Vec2d list
                 except Exception as e: print(f"Error creating Triangle Poly: {e}. Vertices: {self.vertices}"); shape_created = False
             else: print("Error: Not enough vertices for triangle."); shape_created = False

        if not shape_created: print(f"Error: Failed to recreate shape '{self.shape_type}'"); self.body = None; self.shape = None; return False

        self.shape.game_object_ref = self; self.body.game_object_ref = self
        self._apply_physics_properties(); self.body.angular_velocity = 1 if is_spinning else 0
        space.add(self.body, self.shape)
        return True

    # --- MODIFIED Resize Method ---
    def resize(self, new_size_params: dict, space, new_pos=None, new_angle=None):
        """ Resizes the shape and recreates physics objects. """
        print(f"Shape attempting resize to: {new_size_params}")
        position = new_pos if new_pos is not None else self.body.position
        angle = new_angle if new_angle is not None else self.body.angle

        resize_param_updated = False
        if self.shape_type == 'Circle':
            new_radius = new_size_params.get('radius')
            if new_radius is not None and new_radius > 0: self.radius = new_radius; resize_param_updated = True
            else: print("Resize Error: Invalid radius for Circle.")
        elif self.shape_type == 'Rectangle':
            new_size = new_size_params.get('size') # Expecting Vec2d
            if isinstance(new_size, Vec2d) and new_size.x > 0 and new_size.y > 0: self.size = new_size; resize_param_updated = True
            # Handle tuple/list conversion if needed from older command saves? Safer not to rely on this.
            # elif isinstance(new_size, (list, tuple))...
            else: print(f"Resize Error: Invalid size Vec2d for Rectangle: {new_size}")
        elif self.shape_type == 'Triangle':
            new_scale = new_size_params.get('scale')
            if new_scale is not None and new_scale > 0.01: # Add a minimum scale check
                self.scale = new_scale
                self._update_scaled_vertices() # Recalculate runtime vertices
                resize_param_updated = True
            else: print("Resize Error: Invalid scale for Triangle.")

        if resize_param_updated:
            return self._recreate_physics_objects(space, position, angle)
        else:
            return False

    # ... ( _apply_physics_properties, draw, update, set_property, remove_from_space, get_bounding_box methods remain the same) ...
    def _apply_physics_properties(self):
        if not self.shape: return
        self.shape.friction = 3.0 if self.properties.get('Sticky') else 1.0; self.shape.elasticity = 0.1
        if self.properties.get('Danger'): self.shape.collision_type = COLLISION_TYPES_DICT['danger']
        else: self.shape.collision_type = COLLISION_TYPES_DICT['normal']
        self.shape.filter = pymunk.ShapeFilter(categories=0b10)

    def draw(self, screen, offset):
        if not self.shape: return
        color = (50, 50, 255)
        if self.properties.get('Danger'): color = (255, 100, 0)
        if self.properties.get('Sticky'): color = (139, 69, 19)
        if self.properties.get('Spinning'): color = (255, 105, 180)
        screen_width=screen.get_width(); screen_height=screen.get_height()
        if isinstance(self.shape, pymunk.Poly):
            # --- Draw using current runtime vertices ---
            world_vertices = [self.body.local_to_world(v) - offset for v in self.shape.get_vertices()]
            # Basic check if any part might be visible (using bounding box is better)
            bb = self.shape.bb # Use shape's bounding box
            if bb.right >= offset.x and bb.left <= offset.x + screen_width and bb.bottom >= offset.y and bb.top <= offset.y + screen_height:
                 pygame.draw.polygon(screen, color, [(int(v.x), int(v.y)) for v in world_vertices])
        elif isinstance(self.shape, pymunk.Circle):
            pos = self.body.position - offset; current_radius = getattr(self.shape, 'radius', 1)
            if -current_radius < pos.x < screen_width + current_radius and -current_radius < pos.y < screen_height + current_radius:
                pygame.draw.circle(screen, color, pos, int(current_radius)) # Use Vec2d pos directly
                angle = self.body.angle; dot_offset = Vec2d(current_radius * 0.8, 0).rotated(angle); dot_pos = self.body.position + dot_offset - offset
                pygame.draw.circle(screen, (0,0,0), dot_pos, 4) # Use Vec2d pos directly
        if self.selected:
            pos = self.body.position - offset
            if 0 < pos.x < screen_width and 0 < pos.y < screen_height: pygame.draw.circle(screen, (0, 255, 0), pos, 10, 2) # Use Vec2d pos directly

    def update(self, dt): pass

    def set_property(self, prop, value, space):
        prop_changed = self.properties.get(prop) != value;
        if not prop_changed: return
        self.properties[prop] = value
        if prop == 'Spinning':
             new_body_type = pymunk.Body.KINEMATIC if value else pymunk.Body.STATIC
             if self.body.body_type != new_body_type:
                  pos = self.body.position; ang = self.body.angle
                  print(f"Shape: Recreating physics for Spinning toggle at {pos}")
                  self._recreate_physics_objects(space, pos, ang)
             else: self.body.angular_velocity = 1 if value else 0
        elif prop == 'Sticky' or prop == 'Danger': self._apply_physics_properties()

    def remove_from_space(self, space):
        if self.shape and self.shape in space.shapes: space.remove(self.shape)
        if self.body and self.body in space.bodies: space.remove(self.body)
        # Setting self.shape/body to None might be safer after removal
        # self.shape = None; self.body = None; # Consider this if issues arise

    def get_bounding_box(self):
        if self.shape: return self.shape.bb
        return None