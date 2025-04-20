# states/editor_state.py
import pygame
from pymunk import Vec2d
from collections import deque

from .base_state import BaseState
from game_world import GameWorld, MAP_WIDTH, MAP_HEIGHT
from toolbar import Toolbar, TOOLBAR_HEIGHT
# --- Import Radial Menu ---
from ui_elements import RadialMenu
# --- Import Commands ---
from commands import (Command, PlaceShapeCommand, DeleteShapeCommand, MoveShapeCommand,
                      TogglePropertyCommand, ResizeShapeCommand, SetMarkerCommand,
                      AddCheckpointCommand, RemoveCheckpointCommand)
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from shape import Shape

# Editor Specific Constants
EDGE_SCROLL_ZONE = 40
EDGE_SCROLL_SPEED = 600
UNDO_LIMIT = 10 # Moved outside the class
RESIZE_HANDLE_SIZE = 8
RESIZE_HANDLE_COLOR = (255, 0, 255) # Magenta
SCROLL_WHEEL_SPEED_FACTOR = 50 # Adjust sensitivity

PLACEMENT_TOOLS = ['Rectangle', 'Circle', 'Triangle']
MARKER_TOOLS = ['Start', 'End', 'Checkpoint']


class EditorState(BaseState):
    def __init__(self, screen_dims):
        super().__init__()
        self.screen_width, self.screen_height = screen_dims
        self.game_world = GameWorld(self.screen_width, self.screen_height)
        self.toolbar = Toolbar() # Toolbar no longer holds properties
        self.selected_shape_instance: Optional['Shape'] = None
        self.undo_stack = deque(maxlen=UNDO_LIMIT)
        self.redo_stack = deque(maxlen=UNDO_LIMIT)
        self.dragging_action = None; self.drag_start_mouse_world = None
        self.drag_shape_start_pos = None; self.resize_handle_dragged = None
        self.resize_start_shape_params = None; self.resize_start_shape_pos = None
        self.resize_start_shape_angle = None; self.shape_being_dragged = None

        # --- Create Radial Menu Instance ---
        self.radial_menu = RadialMenu(self) # Pass self (EditorState) as context

        # Initial setup
        self.game_world.load_level_data(); self.game_world.set_gravity((0, 0)); self.game_world.reset_camera(); self._clear_undo_redo()

    # --- Undo/Redo and Command Execution (Unchanged) ---
    def _clear_undo_redo(self): self.undo_stack.clear(); self.redo_stack.clear()
    def execute_command(self, command: Command):
        if command: command.execute(); self.undo_stack.append(command); self.redo_stack.clear(); print(f"Undo stack size: {len(self.undo_stack)}")
    def undo_last_command(self):
        if self.undo_stack: command=self.undo_stack.pop(); command.undo(); self.redo_stack.append(command); print("Action undone."); print(f"Undo:{len(self.undo_stack)},Redo:{len(self.redo_stack)}")
        else: print("Nothing to undo.")
    def redo_last_command(self):
        if self.redo_stack: command=self.redo_stack.pop(); command.execute(); self.undo_stack.append(command); print("Action redone."); print(f"Undo:{len(self.undo_stack)},Redo:{len(self.redo_stack)}")
        else: print("Nothing to redo.")

    # --- MODIFIED select_shape ---
    def select_shape(self, shape_instance: Optional['Shape']):
        """ Safely selects a shape, deselects previous, updates toolbar, shows/hides radial menu. """
        self.dragging_action = None; self.shape_being_dragged = None # Cancel drag

        if self.selected_shape_instance and self.selected_shape_instance != shape_instance:
             self.selected_shape_instance.selected = False

        # Hide menu before potentially changing selection
        if self.selected_shape_instance != shape_instance:
             self.radial_menu.hide()

        self.selected_shape_instance = shape_instance

        if self.selected_shape_instance:
             self.selected_shape_instance.selected = True
             # Toolbar no longer needs properties: self.toolbar.current_properties = self.selected_shape_instance.properties.copy()
             self.toolbar.set_active_tool('Select')
             # --- Show Radial Menu ---
             shape_screen_pos = self.game_world._world_to_screen(self.selected_shape_instance.body.position)
             self.radial_menu.show(shape_screen_pos, self.selected_shape_instance)
        # else: Menu is already hidden if selection changed to None


    def enter_state(self, previous_state_data=None):
        super().enter_state(); self.game_world.set_gravity((0, 0))
        if previous_state_data and isinstance(previous_state_data.get('game_world'), GameWorld): self.game_world = previous_state_data['game_world']; print("EditorState received existing GameWorld.")
        self.game_world.remove_player(); self.game_world.last_checkpoint_activated = None
        self.select_shape(None); self._clear_undo_redo(); self.toolbar.set_active_tool('Select');
        self.radial_menu.hide() # Ensure menu hidden on state entry
        pygame.display.set_caption("Level Editor Mode - Ctrl+Z/Y Undo/Redo")

    def exit_state(self):
        super().exit_state(); self.select_shape(None);
        self.radial_menu.hide() # Hide menu on exit
        return {'game_world': self.game_world}

    def _deselect_shape_if_needed(self, new_tool):
         tools_causing_deselect = PLACEMENT_TOOLS + MARKER_TOOLS
         if self.selected_shape_instance and new_tool in tools_causing_deselect:
             self.select_shape(None) # This now also hides the radial menu

    def _get_resize_handles(self):
        # (Unchanged)
        handles = {};
        if not self.selected_shape_instance or not self.selected_shape_instance.shape: return handles
        bb = self.selected_shape_instance.get_bounding_box();
        if not bb: return handles
        world_tl=Vec2d(bb.left,bb.top); world_br=Vec2d(bb.right,bb.bottom); world_tr=Vec2d(bb.right,bb.top); world_bl=Vec2d(bb.left,bb.bottom)
        world_tm=world_tl.interpolate_to(world_tr,0.5); world_bm=world_bl.interpolate_to(world_br,0.5); world_ml=world_tl.interpolate_to(world_bl,0.5); world_mr=world_tr.interpolate_to(world_br,0.5)
        handle_points_world={"tl":world_tl,"tm":world_tm,"tr":world_tr,"ml":world_ml,"mr":world_mr,"bl":world_bl,"bm":world_bm,"br":world_br}
        half_handle=RESIZE_HANDLE_SIZE//2
        for name, world_pos in handle_points_world.items():
            screen_pos=self.game_world._world_to_screen(world_pos); handles[name]=pygame.Rect(screen_pos.x-half_handle,screen_pos.y-half_handle,RESIZE_HANDLE_SIZE,RESIZE_HANDLE_SIZE)
        return handles

    def _get_current_size_params_for_command(self, shape_obj: Optional['Shape']) -> dict:
        # (Unchanged)
        if not shape_obj: return {}
        if shape_obj.shape_type == 'Circle': return {'radius': shape_obj.radius}
        elif shape_obj.shape_type == 'Rectangle':
             if shape_obj.size: return {'size': Vec2d(shape_obj.size.x, shape_obj.size.y)}
             else: return {}
        elif shape_obj.shape_type == 'Triangle': return {'scale': shape_obj.scale}
        else: return {}

    # --- MODIFIED handle_event ---
    def handle_event(self, event):
        # --- 1. Give Radial Menu first chance to handle event ---
        if self.radial_menu.handle_event(event):
            return # Event was handled by the menu (e.g., button click)

        # --- 2. Toolbar Interaction ---
        # Toolbar no longer calls set_property, only updates its own state
        self.toolbar.handle_event(event, self)

        # --- 3. World Interaction ---
        mouse_pos_screen = None; world_pos = None
        if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
            mouse_pos_screen = event.pos; world_pos = self.game_world._screen_to_world(mouse_pos_screen)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not mouse_pos_screen or mouse_pos_screen[1] <= TOOLBAR_HEIGHT: return # Outside world or toolbar click
            can_interact = (0 <= world_pos.x <= MAP_WIDTH and 0 <= world_pos.y <= MAP_HEIGHT)
            if not can_interact: self.select_shape(None); return # Deselects & hides menu

            # Interaction logic (Handles -> Shape -> Empty Space)
            clicked_on_handle = None
            if self.selected_shape_instance and self.toolbar.selected_tool == 'Select':
                handles = self._get_resize_handles();
                for name, rect in handles.items():
                    if rect.collidepoint(mouse_pos_screen): clicked_on_handle = name; break

            if clicked_on_handle: # Start Resize
                 self.dragging_action = "resize"; self.resize_handle_dragged = clicked_on_handle
                 self.drag_start_mouse_world = world_pos
                 self.resize_start_shape_params = self._get_current_size_params_for_command(self.selected_shape_instance)
                 self.resize_start_shape_pos = Vec2d(self.selected_shape_instance.body.position.x, self.selected_shape_instance.body.position.y)
                 self.resize_start_shape_angle = self.selected_shape_instance.body.angle
                 print(f"Starting resize via handle: {clicked_on_handle}")
                 self.radial_menu.hide() # Hide menu while resizing
            else: # Check Shape Click
                clicked_shape = None
                for shape_obj in reversed(self.game_world.shapes):
                    if shape_obj and shape_obj.shape and shape_obj.body and shape_obj.shape.point_query(world_pos).distance <= 0:
                        clicked_shape = shape_obj; break
                if clicked_shape: # Select and start Move
                     self.select_shape(clicked_shape) # Selects, shows menu, sets tool='Select'
                     if self.toolbar.selected_tool == 'Select': # Should always be true now after select
                          self.dragging_action = "move"; self.shape_being_dragged = clicked_shape
                          self.drag_start_mouse_world = world_pos; self.drag_shape_start_pos = Vec2d(clicked_shape.body.position.x, clicked_shape.body.position.y); print(f"Starting move")
                          self.radial_menu.hide() # Hide menu while moving
                else: # Clicked Empty Space -> Deselect or Place
                     self.select_shape(None) # Deselects & hides menu
                     self.dragging_action = None
                     current_tool = self.toolbar.selected_tool
                     if current_tool in MARKER_TOOLS: # Place marker
                          if current_tool == 'Start': command = SetMarkerCommand(self, 'start', world_pos); self.execute_command(command)
                          elif current_tool == 'End': command = SetMarkerCommand(self, 'end', world_pos); self.execute_command(command)
                          elif current_tool == 'Checkpoint': command = AddCheckpointCommand(self, world_pos); self.execute_command(command)
                     elif current_tool in PLACEMENT_TOOLS: # Place shape
                          # Use toolbar's last known defaults for properties when placing
                          shape_data = {'type': current_tool,'position': world_pos.int_tuple,'properties': self.toolbar.current_properties.copy()}
                          command = PlaceShapeCommand(self, shape_data); self.execute_command(command)
                          # Place command now selects the new shape & shows menu

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # (Mouse Button Up logic remains the same - finalize move/resize commands)
            if world_pos is None: world_pos = self.game_world._screen_to_world(pygame.mouse.get_pos())
            if self.dragging_action == "move" and self.shape_being_dragged:
                 final_body_pos = Vec2d(self.shape_being_dragged.body.position.x, self.shape_being_dragged.body.position.y)
                 self.game_world.space.reindex_shapes_for_body(self.shape_being_dragged.body)
                 if self.drag_shape_start_pos and (final_body_pos - self.drag_shape_start_pos).length > 1.0: command = MoveShapeCommand(self, self.shape_being_dragged, self.drag_shape_start_pos, final_body_pos); self.execute_command(command)
                 elif self.drag_shape_start_pos: self.shape_being_dragged.body.position = self.drag_shape_start_pos; self.game_world.space.reindex_shapes_for_body(self.shape_being_dragged.body)
            elif self.dragging_action == "resize" and self.selected_shape_instance:
                 new_params = self._calculate_final_resize(world_pos)
                 if self.resize_start_shape_params is not None:
                     if new_params and new_params != self.resize_start_shape_params: command = ResizeShapeCommand(self, self.selected_shape_instance, new_params); self.execute_command(command); self.select_shape(self.selected_shape_instance) # Reselect to show menu again
                     else: self.selected_shape_instance.resize(self.resize_start_shape_params, self.game_world.space, new_pos=self.resize_start_shape_pos, new_angle=self.resize_start_shape_angle); print("Resize cancelled or failed."); self.select_shape(self.selected_shape_instance) # Reselect even if cancelled
                 else: print("Error: Cannot finalize resize, missing start parameters.")
            # Reset dragging state
            self.dragging_action = None; self.shape_being_dragged = None; self.drag_start_mouse_world = None; self.drag_shape_start_pos = None; self.resize_handle_dragged = None; self.resize_start_shape_params = None; self.resize_start_shape_pos = None; self.resize_start_shape_angle = None
            # Re-show menu if a shape is still selected after drag/resize ends
            if self.selected_shape_instance:
                 shape_screen_pos = self.game_world._world_to_screen(self.selected_shape_instance.body.position)
                 self.radial_menu.show(shape_screen_pos, self.selected_shape_instance)


        elif event.type == pygame.MOUSEMOTION:
            # (Mouse motion logic for drag move unchanged, resize preview skipped)
            if world_pos is None: return
            if self.dragging_action == "move" and self.shape_being_dragged:
                if self.drag_start_mouse_world and self.drag_shape_start_pos: mouse_delta = world_pos - self.drag_start_mouse_world; new_shape_pos = Vec2d(self.drag_shape_start_pos.x + mouse_delta.x, self.drag_shape_start_pos.y + mouse_delta.y); self.shape_being_dragged.body.position = new_shape_pos; self.game_world.space.reindex_shapes_for_body(self.shape_being_dragged.body)
            elif self.dragging_action == "resize" and self.selected_shape_instance: pass

        elif event.type == pygame.KEYDOWN:
            # (Key handling unchanged: ESC, DEL, Save/Load, TAB, Undo/Redo)
            mods = pygame.key.get_mods(); is_ctrl = mods & pygame.KMOD_CTRL; is_shift = mods & pygame.KMOD_SHIFT
            if event.key == pygame.K_ESCAPE:
                print("ESC pressed - Deselecting shape/cancelling drag."); was_dragging = self.dragging_action == "move" and self.shape_being_dragged; was_resizing = self.dragging_action == "resize" and self.selected_shape_instance
                shape_to_snap = self.shape_being_dragged or self.selected_shape_instance
                self.select_shape(None); self.dragging_action = None # Deselect hides menu
                if shape_to_snap:
                    if was_dragging and self.drag_shape_start_pos: shape_to_snap.body.position = self.drag_shape_start_pos; self.game_world.space.reindex_shapes_for_body(shape_to_snap.body)
                    elif was_resizing and self.resize_start_shape_params: self.selected_shape_instance.resize(self.resize_start_shape_params, self.game_world.space, new_pos=self.resize_start_shape_pos, new_angle=self.resize_start_shape_angle)
                self.shape_being_dragged = None; self.drag_start_mouse_world = None; self.drag_shape_start_pos = None; self.resize_handle_dragged = None; self.resize_start_shape_params = None; self.resize_start_shape_pos = None; self.resize_start_shape_angle = None
            elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                 if self.selected_shape_instance: command = DeleteShapeCommand(self, self.selected_shape_instance); self.execute_command(command) # This will deselect via command
            elif event.key == pygame.K_s and is_ctrl: self.game_world.save_level_data()
            elif event.key == pygame.K_l and is_ctrl:
                 if self.game_world.load_level_data(): self.select_shape(None); self._clear_undo_redo()
                 else: print("Failed to load level.")
            elif event.key == pygame.K_TAB:
                 from .playing_state import PlayingState
                 if self.game_world.start_marker: state_data = self.exit_state(); self.manager.set_state(PlayingState(state_data['game_world']))
                 else: print("Cannot enter play mode: Start marker not set!")
            elif event.key == pygame.K_z and is_ctrl and not is_shift: self.undo_last_command()
            elif (event.key == pygame.K_y and is_ctrl) or (event.key == pygame.K_z and is_ctrl and is_shift): self.redo_last_command()

    # --- REMOVED set_property method - Toolbar no longer calls this ---
    # def set_property(self, prop_name, value):
    #     # ... (old logic using TogglePropertyCommand) ...
    #     pass

    @property
    def selected_shape(self): return self.selected_shape_instance

    def _calculate_final_resize(self, final_mouse_world):
        # (Unchanged - still simplified, but uses start params correctly)
        if not self.selected_shape_instance or not self.resize_handle_dragged or not self.drag_start_mouse_world: return None
        shape = self.selected_shape_instance; handle = self.resize_handle_dragged;
        if self.resize_start_shape_params is None or self.resize_start_shape_pos is None: return None
        mouse_delta = final_mouse_world - self.drag_start_mouse_world

        if shape.shape_type == 'Rectangle':
            start_size = self.resize_start_shape_params.get('size'); start_pos = self.resize_start_shape_pos
            if not start_size: return None;
            current_size_x, current_size_y = start_size.x, start_size.y; new_x, new_y = current_size_x, current_size_y
            if 't' in handle: new_y = max(10, start_size.y + mouse_delta.y)
            if 'b' in handle: new_y = max(10, start_size.y - mouse_delta.y)
            if 'l' in handle: new_x = max(10, start_size.x - mouse_delta.x)
            if 'r' in handle: new_x = max(10, start_size.x + mouse_delta.x)
            new_size = Vec2d(new_x, new_y);
            if new_size.x <=0 or new_size.y <= 0: print("Resize Error: Calc size non-positive."); return None
            new_center_x, new_center_y = start_pos.x, start_pos.y
            if 'l' in handle: new_center_x = start_pos.x - (new_size.x - start_size.x) / 2.0
            if 'r' in handle: new_center_x = start_pos.x + (new_size.x - start_size.x) / 2.0
            if 't' in handle: new_center_y = start_pos.y + (new_size.y - start_size.y) / 2.0
            if 'b' in handle: new_center_y = start_pos.y - (new_size.y - start_size.y) / 2.0
            new_pos_vec = Vec2d(new_center_x, new_center_y)
            print(f"Calculated new rect size: {new_size}, pos: {new_pos_vec}"); return {'size': new_size, 'position': new_pos_vec}
        elif shape.shape_type == 'Triangle':
             start_scale = self.resize_start_shape_params.get('scale', 1.0); center_world = self.resize_start_shape_pos
             start_dist = (self.drag_start_mouse_world - center_world).length; end_dist = (final_mouse_world - center_world).length
             if start_dist > 1: scale_multiplier = end_dist / start_dist; new_scale = max(0.1, start_scale * scale_multiplier); print(f"Calculated new triangle scale: {new_scale}"); return {'scale': new_scale}
             else: return None
        elif shape.shape_type == 'Circle':
             start_radius = self.resize_start_shape_params.get('radius'); center_world = self.resize_start_shape_pos
             if start_radius is None: return None
             start_dist = (self.drag_start_mouse_world - center_world).length; end_dist = (final_mouse_world - center_world).length
             if start_dist > 1: scale_factor = end_dist / start_dist; new_radius = max(5, start_radius * scale_factor); print(f"Calculated new circle radius: {new_radius}"); return {'radius': new_radius}
             else: return None
        else: print(f"Resize not implemented for shape type: {shape.shape_type}"); return None

    def update(self, dt):
        # (Edge scrolling unchanged)
        mouse_pos = pygame.mouse.get_pos(); dx = 0.0; dy = 0.0; scroll_speed_dt = EDGE_SCROLL_SPEED * dt
        if mouse_pos[0] < EDGE_SCROLL_ZONE: dx = -scroll_speed_dt
        elif mouse_pos[0] > self.screen_width - EDGE_SCROLL_ZONE: dx = scroll_speed_dt
        if mouse_pos[1] > TOOLBAR_HEIGHT and mouse_pos[1] < TOOLBAR_HEIGHT + EDGE_SCROLL_ZONE: dy = -scroll_speed_dt
        elif mouse_pos[1] > self.screen_height - EDGE_SCROLL_ZONE: dy = scroll_speed_dt
        if dx != 0 or dy != 0:
            scroll_delta = Vec2d(dx, dy); new_offset = self.game_world.camera_offset + scroll_delta
            max_offset_x = max(0, MAP_WIDTH - self.screen_width); max_offset_y = max(0, MAP_HEIGHT - self.screen_height)
            clamped_x = max(0, min(new_offset.x, max_offset_x)); clamped_y = max(0, min(new_offset.y, max_offset_y))
            self.game_world.camera_offset = Vec2d(clamped_x, clamped_y)

    # --- MODIFIED Draw Method ---
    def draw(self, screen):
        screen.fill((200, 200, 200)); self.game_world.draw(screen) # Draw world first

        # Draw Resize Handles if shape selected AND Select tool is active
        if self.selected_shape_instance and self.toolbar.selected_tool == 'Select':
            handles = self._get_resize_handles()
            for name, rect in handles.items(): pygame.draw.rect(screen, RESIZE_HANDLE_COLOR, rect); pygame.draw.rect(screen, (0, 0, 0), rect, 1)

        # --- Draw Radial Menu ---
        self.radial_menu.draw(screen) # Draw if visible

        # Draw Toolbar last
        self.toolbar.draw(screen, self)