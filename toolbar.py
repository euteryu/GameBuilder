# toolbar.py
import pygame

# Keep constants at module level
BUTTON_HEIGHT = 40
BUTTON_WIDTH = 100
TOOLBAR_HEIGHT = 60

SELECTED_TOOL_COLOR = (80, 80, 150)
BUTTON_COLOR = (100, 100, 100)
# PROPERTY_ACTIVE_COLOR = (50, 150, 50) # No longer needed
# PROPERTY_INACTIVE_COLOR = BUTTON_COLOR # No longer needed

class Toolbar:
    def __init__(self):
        if not pygame.font.get_init(): pygame.font.init()
        self.font = pygame.font.SysFont('arial', 18)
        self.buttons = []
        self.selected_tool = 'Select'
        # --- Removed current_properties as they are shape-specific now ---
        # self.current_properties = {'Danger': False, 'Spinning': False, 'Sticky': False}
        self.create_buttons()

    def create_buttons(self):
        self.buttons = [] # Clear existing buttons
        # --- Only Tool Buttons ---
        tools = ['Select', 'Rectangle', 'Circle', 'Triangle', 'Start', 'End', 'Checkpoint']
        x = 10

        for tool in tools:
            width = BUTTON_WIDTH
            self.buttons.append({'rect': pygame.Rect(x, 10, width, BUTTON_HEIGHT), 'label': tool, 'type': 'tool'})
            x += width + 10

        # --- NO Property Buttons Added ---

    def handle_event(self, event, editor_state_context):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            if mouse_pos[1] <= TOOLBAR_HEIGHT:
                for button in self.buttons:
                    if button['rect'].collidepoint(mouse_pos):
                        # --- Only handle TOOL clicks ---
                        if button['type'] == 'tool':
                            new_tool = button['label']
                            if self.selected_tool != new_tool:
                                self.selected_tool = new_tool
                                print(f"Toolbar: Tool selected: {self.selected_tool}")
                                if hasattr(editor_state_context, '_deselect_shape_if_needed'):
                                     editor_state_context._deselect_shape_if_needed(self.selected_tool)
                        # --- NO Property Click Handling ---
                        break # Button handled

    def set_active_tool(self, tool_name):
         if any(b['label'] == tool_name and b['type'] == 'tool' for b in self.buttons):
              if self.selected_tool != tool_name:
                   print(f"Toolbar: Tool force set to: {tool_name}")
                   self.selected_tool = tool_name
         else: print(f"Warning: Tried to set unknown tool '{tool_name}'")

    def draw(self, screen, editor_state_context):
        # --- Simplified Draw (No property button state) ---
        pygame.draw.rect(screen, (180, 180, 180), (0, 0, screen.get_width(), TOOLBAR_HEIGHT))
        for button in self.buttons:
            button_color = BUTTON_COLOR; is_selected = False
            # --- Only check tool selection ---
            if button['type'] == 'tool':
                if self.selected_tool == button['label']:
                    button_color = SELECTED_TOOL_COLOR; is_selected = True

            pygame.draw.rect(screen, button_color, button['rect'])
            if is_selected: pygame.draw.rect(screen, (255, 255, 0), button['rect'], 2)
            label_color = (255, 255, 255); label = self.font.render(button['label'], True, label_color)
            label_rect = label.get_rect(center=button['rect'].center); screen.blit(label, label_rect.topleft)