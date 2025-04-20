# main.py
import pygame
import sys

# Import the state classes and manager
from states.base_state import BaseState # Optional, for type hinting
from states.editor_state import EditorState
from states.playing_state import PlayingState
# --- Import Player class to call load_assets ---
from player import Player

pygame.init() # Initialize Pygame modules
pygame.font.init()

# Constants
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
FPS = 60

# --- Set up screen FIRST ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Level Editor/Game") # Initial caption
clock = pygame.time.Clock()

# --- Load Player Assets AFTER Display is Set ---
# Moved this line down!
Player.load_assets() # Call the class method here!


# --- Game State Manager ---
class GameStateManager:
    def __init__(self, initial_state: BaseState):
        self.active_state = initial_state
        if self.active_state:
            self.active_state.manager = self
            self.active_state.enter_state() # Call enter on initial state

    def set_state(self, new_state_instance: BaseState):
        if self.active_state:
            previous_data = self.active_state.exit_state() # Call exit on old state
        self.active_state = new_state_instance
        if self.active_state:
            self.active_state.manager = self
            self.active_state.enter_state(previous_data) # Call enter on new state

    def handle_event(self, event):
        if self.active_state:
            self.active_state.handle_event(event)

    def update(self, dt):
        if self.active_state:
            self.active_state.update(dt)

    def draw(self, screen):
        if self.active_state:
            self.active_state.draw(screen)


# --- Main Execution ---
if __name__ == '__main__': # Good practice
    # Initialize the first state (e.g., Editor)
    # Ensure assets are loaded before creating states that might need them indirectly
    if Player.SPRITE_FRAMES is None:
         print("CRITICAL ERROR: Player assets failed to load. Exiting.")
         pygame.quit()
         sys.exit()

    initial_state = EditorState((SCREEN_WIDTH, SCREEN_HEIGHT))
    game_manager = GameStateManager(initial_state)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.1) # Cap delta time

        # --- Event Loop ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                # Delegate event handling to the active state
                game_manager.handle_event(event)

        # --- Update ---
        # Delegate update logic to the active state
        game_manager.update(dt)

        # --- Drawing ---
        # Delegate drawing to the active state
        game_manager.draw(screen)

        # Flip the display
        pygame.display.flip()

    # --- Shutdown ---
    pygame.quit()
    sys.exit()