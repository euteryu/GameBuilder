# ui_elements.py (or similar name)
import pygame
import math
from commands import (Command, PlaceShapeCommand, DeleteShapeCommand, MoveShapeCommand,
                      TogglePropertyCommand, ResizeShapeCommand, SetMarkerCommand,
                      AddCheckpointCommand, RemoveCheckpointCommand)

# Constants for the Radial Menu
RADIAL_MENU_RADIUS = 60
BUTTON_RADIUS = 20
BUTTON_COLOR = (80, 80, 120)
BUTTON_HOVER_COLOR = (110, 110, 160)
BUTTON_BORDER_COLOR = (200, 200, 255)
ICON_COLOR = (255, 255, 255)

class RadialMenuButton:
    """ Represents a single button within the radial menu. """
    def __init__(self, id, icon_char, angle_degrees, command_func):
        self.id = id # e.g., "toggle_danger", "delete"
        self.icon_char = icon_char # Character to display (e.g., 'D', 'S', 'X')
        self.angle_degrees = angle_degrees # Position on the wheel
        self.command_func = command_func # Function to call when clicked (will execute a command)
        self.rect = pygame.Rect(0, 0, BUTTON_RADIUS * 2, BUTTON_RADIUS * 2)
        self.is_hovered = False
        self.font = pygame.font.SysFont('arial', 18, bold=True) # Font for icon

    def update_pos(self, center_x, center_y):
        """ Calculates the button's screen position based on the menu center and angle. """
        rad = math.radians(self.angle_degrees)
        offset_x = RADIAL_MENU_RADIUS * math.cos(rad)
        offset_y = RADIAL_MENU_RADIUS * math.sin(rad) # Pygame Y is down, but sin works correctly mathematically
        self.rect.center = (int(center_x + offset_x), int(center_y + offset_y))

    def draw(self, screen):
        """ Draws the button. """
        color = BUTTON_HOVER_COLOR if self.is_hovered else BUTTON_COLOR
        pygame.draw.circle(screen, color, self.rect.center, BUTTON_RADIUS)
        pygame.draw.circle(screen, BUTTON_BORDER_COLOR, self.rect.center, BUTTON_RADIUS, 2)

        # Draw icon character
        icon_surf = self.font.render(self.icon_char, True, ICON_COLOR)
        icon_rect = icon_surf.get_rect(center=self.rect.center)
        screen.blit(icon_surf, icon_rect)

    def handle_event(self, event, target_shape):
        """ Checks for hover and click events. Returns True if clicked. """
        self.is_hovered = False
        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                self.is_hovered = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                print(f"Radial button '{self.id}' clicked!")
                if self.command_func:
                     self.command_func(target_shape) # Execute the associated command function
                return True # Click handled
        return False


class RadialMenu:
    """ A context menu appearing around a selected object. """
    def __init__(self, editor_state):
        self.editor_state = editor_state # Reference to execute commands
        self.is_visible = False
        self.screen_center = (0, 0) # Center position on screen
        self.target_shape = None    # The shape this menu is acting upon
        self.buttons: list[RadialMenuButton] = []
        self._setup_buttons()

    def _setup_buttons(self):
        """ Create the buttons and their actions. """
        # Define actions using lambda functions that create and execute commands
        # Need to access editor_state to execute commands
        def create_toggle_cmd(prop):
            if self.target_shape:
                 # Create command using the state's method to handle undo stack
                 command = TogglePropertyCommand(self.editor_state, self.target_shape, prop)
                 self.editor_state.execute_command(command)
            self.hide() # Hide menu after action

        def create_delete_cmd():
            if self.target_shape:
                 command = DeleteShapeCommand(self.editor_state, self.target_shape)
                 self.editor_state.execute_command(command)
                 # Target shape is now gone, selection cleared by command execute
            self.hide()

        # Add buttons (Angles: 0=East, 90=South, 180=West, 270=North)
        self.buttons.append(RadialMenuButton("toggle_danger", "D", 270, lambda s: create_toggle_cmd("Danger")))
        self.buttons.append(RadialMenuButton("toggle_spinning", "S", 0, lambda s: create_toggle_cmd("Spinning")))
        self.buttons.append(RadialMenuButton("toggle_sticky", "T", 90, lambda s: create_toggle_cmd("Sticky"))) # 'T' for Sticky/Texture?
        self.buttons.append(RadialMenuButton("delete", "X", 180, lambda s: create_delete_cmd()))
        # Add more buttons as needed (e.g., duplicate, properties panel)

    def show(self, screen_position, target_shape):
        """ Make the menu visible at a specific screen location for a target shape. """
        print(f"Showing radial menu for shape at screen pos: {screen_position}")
        self.is_visible = True
        self.screen_center = screen_position
        self.target_shape = target_shape
        # Update button positions based on the new center
        for button in self.buttons:
            button.update_pos(self.screen_center[0], self.screen_center[1])

    def hide(self):
        """ Hide the menu. """
        if self.is_visible:
            print("Hiding radial menu.")
            self.is_visible = False
            self.target_shape = None
            # Reset hover state
            for button in self.buttons:
                 button.is_hovered = False

    def handle_event(self, event):
        """ Process events if the menu is visible. Returns True if event was handled. """
        if not self.is_visible:
            return False

        # Check button interactions first
        for button in self.buttons:
            if button.handle_event(event, self.target_shape):
                return True # Event handled by a button click

        # Optional: Hide menu if clicking *outside* its buttons while visible?
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
             # Check if click was outside all button rects
             mouse_pos = event.pos
             clicked_outside = True
             for button in self.buttons:
                  if button.rect.collidepoint(mouse_pos):
                       clicked_outside = False
                       break
             if clicked_outside:
                  self.hide()
                  # Don't consume the event here, let EditorState handle deselection/selection
                  # return True # Or return False to allow deselection? Let's return False.

        return False # Event not handled by the menu itself

    def draw(self, screen):
        """ Draw the menu background and buttons if visible. """
        if not self.is_visible:
            return

        # Optional: Draw semi-transparent background circle?
        # pygame.draw.circle(screen, (50, 50, 50, 150), self.screen_center, RADIAL_MENU_RADIUS + BUTTON_RADIUS + 5)

        # Draw buttons
        for button in self.buttons:
            button.draw(screen)
