# commands.py
from abc import ABC, abstractmethod
from pymunk import Vec2d
from typing import TYPE_CHECKING, List, Tuple, Optional

if TYPE_CHECKING:
    from shape import Shape
    from states.editor_state import EditorState

class Command(ABC):
    """Abstract base class for all undoable commands."""
    def __init__(self, editor_state: 'EditorState'):
        self.editor_state = editor_state
        self.game_world = editor_state.game_world

    @abstractmethod
    def execute(self): pass
    @abstractmethod
    def undo(self): pass

# --- Shape Commands ---
class PlaceShapeCommand(Command):
    def __init__(self, editor_state: 'EditorState', shape_data):
        super().__init__(editor_state)
        self.shape_data = shape_data
        self.created_shape_object = None

    def execute(self):
        self.created_shape_object = self.game_world.add_shape(self.shape_data)
        if self.created_shape_object:
            print(f"CMD: Placed {self.created_shape_object.shape_type} at {self.shape_data['position']}")
            self.editor_state.select_shape(self.created_shape_object)
        else:
            print("CMD Error: Place failed.")

    def undo(self):
        if self.created_shape_object:
            shape_pos = getattr(self.created_shape_object.body, 'position', 'N/A')
            print(f"CMD: Undoing place {shape_pos}")
            was_selected = (self.editor_state.selected_shape == self.created_shape_object)
            self.game_world.remove_shape(self.created_shape_object)
            self.created_shape_object = None
            if was_selected:
                self.editor_state.select_shape(None)

class DeleteShapeCommand(Command):
    def __init__(self, editor_state: 'EditorState', shape_to_delete: 'Shape'):
        super().__init__(editor_state); assert shape_to_delete is not None
        self.deleted_shape_object_ref = shape_to_delete
        pos = getattr(shape_to_delete.body, 'position', Vec2d(0,0)); ang = getattr(shape_to_delete.body, 'angle', 0.0)
        self.shape_data={'type':shape_to_delete.shape_type,'position':pos.int_tuple,'angle':ang,'properties':shape_to_delete.properties.copy(),'size':shape_to_delete.size.int_tuple if shape_to_delete.size else None,'radius':shape_to_delete.radius if shape_to_delete.radius is not None else None,'vertices':shape_to_delete.vertices if shape_to_delete.vertices else None,'scale':getattr(shape_to_delete,'scale',1.0)}
        print(f"CMD: Prepare delete {self.shape_data['position']}")

    def execute(self):
        shape_to_remove=self.deleted_shape_object_ref
        if shape_to_remove in self.game_world.shapes:
            shape_pos = shape_to_remove.body.position; print(f"CMD: Deleting {shape_pos}")
            was_selected=(self.editor_state.selected_shape==shape_to_remove)
            self.game_world.remove_shape(shape_to_remove)
            if was_selected: self.editor_state.select_shape(None)
        else: print("CMD Warning: Shape to delete was already removed or invalid.")

    def undo(self):
        print(f"CMD: Undoing delete {self.shape_data['position']}")
        recreated_shape=self.game_world.add_shape(self.shape_data)
        if recreated_shape: self.deleted_shape_object_ref = recreated_shape
        else: print("CMD Error: Failed to recreate shape on undo.")


class MoveShapeCommand(Command):
     def __init__(self, editor_state: 'EditorState', shape_to_move: 'Shape', start_pos: Vec2d, end_pos: Vec2d):
        super().__init__(editor_state); assert shape_to_move is not None
        self.shape_moved = shape_to_move; self.start_pos = start_pos; self.end_pos = end_pos
        print(f"CMD: Prepare move {start_pos} -> {end_pos}")

     def execute(self):
        if self.shape_moved and self.shape_moved.body:
            print(f"CMD: Moving to {self.end_pos}"); self.shape_moved.body.position = self.end_pos
            self.game_world.space.reindex_shapes_for_body(self.shape_moved.body)
        else: print("CMD Warning: Shape to move no longer valid.")

     def undo(self):
        if self.shape_moved and self.shape_moved.body:
            print(f"CMD: Undoing move to {self.start_pos}"); self.shape_moved.body.position = self.start_pos
            self.game_world.space.reindex_shapes_for_body(self.shape_moved.body)
        else: print("CMD Warning: Shape to undo move no longer valid.")


# --- CORRECTED TogglePropertyCommand ---
class TogglePropertyCommand(Command):
     def __init__(self, editor_state: 'EditorState', shape_instance: 'Shape', prop_name):
        super().__init__(editor_state); assert shape_instance is not None
        self.shape_instance = shape_instance; self.prop_name = prop_name
        self.previous_value = shape_instance.properties.get(prop_name, False); self.new_value = not self.previous_value
        pos = getattr(shape_instance.body, 'position', 'N/A'); print(f"CMD: Prepare toggle {prop_name} for {pos} {self.previous_value}->{self.new_value}")

     def execute(self):
        if self.shape_instance:
            print(f"CMD: Toggle {self.prop_name} -> {self.new_value}")
            self.shape_instance.set_property(self.prop_name, self.new_value, self.game_world.space)
            # --- REMOVED line trying to access toolbar.current_properties ---
            # if self.editor_state.selected_shape == self.shape_instance:
            #     self.editor_state.toolbar.current_properties[self.prop_name] = self.new_value
        else:
            print("CMD Warning: Shape to toggle property no longer valid.")

     def undo(self):
        if self.shape_instance:
            print(f"CMD: Undoing toggle {self.prop_name} -> {self.previous_value}")
            self.shape_instance.set_property(self.prop_name, self.previous_value, self.game_world.space)
            # --- REMOVED line trying to access toolbar.current_properties ---
            # if self.editor_state.selected_shape == self.shape_instance:
            #     self.editor_state.toolbar.current_properties[self.prop_name] = self.previous_value
        else:
             print("CMD Warning: Shape to undo toggle no longer valid.")
# --- End Correction ---


class ResizeShapeCommand(Command):
    def __init__(self, editor_state: 'EditorState', shape_instance: 'Shape', new_params: dict):
        super().__init__(editor_state); assert shape_instance is not None
        self.shape_instance = shape_instance; self.new_params = new_params.copy()
        self.old_params = self._get_current_params(shape_instance)
        self.old_position = Vec2d(shape_instance.body.position.x, shape_instance.body.position.y)
        self.old_angle = shape_instance.body.angle
        self.new_position = new_params.get('position', self.old_position); self.new_angle = self.old_angle
        print(f"CMD: Prepare resize shape"); print(f"  Old: Params={self.old_params}, Pos={self.old_position}, Ang={self.old_angle:.2f}"); print(f"  New: Params={self.new_params}, Pos={self.new_position}, Ang={self.new_angle:.2f}")

    def _get_current_params(self, shape_obj):
        if shape_obj.shape_type == 'Circle': return {'radius': shape_obj.radius}
        elif shape_obj.shape_type == 'Rectangle': return {'size': Vec2d(shape_obj.size.x, shape_obj.size.y)}
        elif shape_obj.shape_type == 'Triangle': return {'scale': shape_obj.scale}
        else: return {}

    def execute(self):
        if self.shape_instance:
            print(f"CMD: Resizing shape to {self.new_params} at pos {self.new_position}")
            success = self.shape_instance.resize(self.new_params, self.game_world.space, new_pos=self.new_position, new_angle=self.new_angle)
            if not success: print("CMD Error: Shape resize failed.")
        else: print("CMD Warning: Shape to resize no longer valid.")

    def undo(self):
        if self.shape_instance:
            print(f"CMD: Undoing resize, restoring to {self.old_params} at pos {self.old_position}")
            success = self.shape_instance.resize(self.old_params, self.game_world.space, new_pos=self.old_position, new_angle=self.old_angle)
            if not success: print("CMD Error: Shape resize undo failed.")
        else: print("CMD Warning: Shape to undo resize no longer valid.")


# --- Marker / Checkpoint Commands ---
class SetMarkerCommand(Command):
    def __init__(self, editor_state: 'EditorState', marker_type: str, new_pos: Optional[Vec2d]):
        super().__init__(editor_state); assert marker_type in ['start', 'end']
        self.marker_type = marker_type; self.new_pos = Vec2d(new_pos.x, new_pos.y) if new_pos else None
        self.old_pos = getattr(self.game_world, f"{marker_type}_marker", None); self.old_pos = Vec2d(self.old_pos.x, self.old_pos.y) if self.old_pos else None
        print(f"CMD: Prepare set {marker_type}: {self.old_pos} -> {self.new_pos}")

    def execute(self): print(f"CMD: Set {self.marker_type} -> {self.new_pos}"); setattr(self.game_world, f"{self.marker_type}_marker", self.new_pos)
    def undo(self): print(f"CMD: Undo set {self.marker_type} -> {self.old_pos}"); setattr(self.game_world, f"{self.marker_type}_marker", self.old_pos)

class AddCheckpointCommand(Command):
    def __init__(self, editor_state: 'EditorState', position: Vec2d):
        super().__init__(editor_state); self.position = Vec2d(position.x, position.y); self.added_checkpoint = None

    def execute(self):
        print(f"CMD: Add checkpoint {self.position}"); self.added_checkpoint = self.position
        self.game_world.checkpoints.append(self.added_checkpoint); print(f"CP count: {len(self.game_world.checkpoints)}")

    def undo(self):
        print(f"CMD: Undo add checkpoint {self.position}")
        if self.added_checkpoint in self.game_world.checkpoints:
             self.game_world.checkpoints.remove(self.added_checkpoint); print(f"CP count: {len(self.game_world.checkpoints)}")
             if self.game_world.last_checkpoint_activated == self.added_checkpoint: self.game_world.last_checkpoint_activated = None
        else: print(f"CMD Warning: Could not find checkpoint {self.added_checkpoint} to remove.")
        self.added_checkpoint = None # Clear after remove regardless


class RemoveCheckpointCommand(Command):
    def __init__(self, editor_state: 'EditorState', position: Vec2d):
        super().__init__(editor_state); self.position = Vec2d(position.x, position.y); self.removed_index = -1; self.removed_value = None

    def execute(self):
        print(f"CMD: Remove checkpoint near {self.position}"); self.removed_index = -1; self.removed_value = None
        try:
            # Find by value equality, store removed value
            self.removed_value = next(cp for cp in self.game_world.checkpoints if cp == self.position)
            self.removed_index = self.game_world.checkpoints.index(self.removed_value)
            self.game_world.checkpoints.pop(self.removed_index)
            print(f"CMD: Removed {self.removed_value} @{self.removed_index}")
            if self.game_world.last_checkpoint_activated == self.removed_value: self.game_world.last_checkpoint_activated = None
        except (ValueError, StopIteration):
             print(f"CMD Warning: Checkpoint at {self.position} not found for removal.")

    def undo(self):
        if self.removed_value and self.removed_index != -1:
            print(f"CMD: Undo remove CP {self.removed_value} @{self.removed_index}"); insert_index = max(0, min(self.removed_index, len(self.game_world.checkpoints)))
            self.game_world.checkpoints.insert(insert_index, self.removed_value)
        else: print("CMD Warning: Cannot undo checkpoint removal, state invalid.")