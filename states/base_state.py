# states/base_state.py
import pygame

class BaseState:
    """
    Base class for all game states (e.g., MainMenu, Editor, Playing).
    """
    def __init__(self):
        self.manager = None # Set by GameStateManager upon state change

    def handle_event(self, event):
        """Process Pygame events."""
        pass

    def update(self, dt):
        """Update game logic for this state."""
        pass

    def draw(self, screen):
        """Draw everything for this state."""
        pass

    def enter_state(self, previous_state_data=None):
        """Called when this state becomes active. Can receive data from previous state."""
        print(f"Entering state: {self.__class__.__name__}")

    def exit_state(self):
        """Called when this state is no longer active. Can return data."""
        print(f"Exiting state: {self.__class__.__name__}")
        return None # Can return data needed by the next state
