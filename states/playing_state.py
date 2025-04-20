# states/playing_state.py
import pygame
from pymunk import Vec2d

from .base_state import BaseState
from game_world import GameWorld
# Import EditorState for transitioning back (use local import in method)


class PlayingState(BaseState):
    """Handles the active gameplay."""
    def __init__(self, game_world: GameWorld): # Receive the existing GameWorld
        super().__init__()
        self.game_world = game_world
        self.screen_width = game_world.screen_width
        self.screen_height = game_world.screen_height
        self.info_font = pygame.font.SysFont('arial', 20)
        self.end_message_font = pygame.font.SysFont('impact', 80)
        self._game_over = False
        self._level_won = False

    def enter_state(self, previous_state_data=None):
        super().enter_state()
        if previous_state_data and isinstance(previous_state_data.get('game_world'), GameWorld):
            self.game_world = previous_state_data['game_world']; print("PlayingState received existing GameWorld.")
        self.game_world.set_gravity((0, 980))
        spawn_pos = self.game_world.get_spawn_position()
        if not self.game_world.player: self.game_world.add_player(spawn_pos)
        else: self.game_world.ensure_player_in_space(); self.game_world.player.reset_state(spawn_pos) # Full reset on play start
        self.game_world.last_checkpoint_activated = None
        # self.game_world.player_died_this_frame = False # Removed this flag
        self.game_world.player_needs_respawn = False
        self._game_over = False; self._level_won = False
        self.game_world.update_camera(force_center=True); pygame.display.set_caption("Playing Mode")

    def exit_state(self):
        super().exit_state()
        # Stop player sound effects etc. if any
        return {'game_world': self.game_world} # Pass world back

    def handle_event(self, event):
        """Handle input specific to playing or ending states."""
        if event.type == pygame.KEYDOWN:
            # --- Always allow returning to editor if game ended ---
            if (self._game_over or self._level_won) and event.key == pygame.K_RETURN:
                from .editor_state import EditorState # Local import
                state_data = self.exit_state()
                self.manager.set_state(EditorState((self.screen_width, self.screen_height))) # Recreate editor state
                return # Event handled

            # --- Allow returning to editor mid-game via TAB (if not dead/won) ---
            if not self._game_over and not self._level_won and event.key == pygame.K_TAB:
                from .editor_state import EditorState # Local import
                state_data = self.exit_state()
                self.manager.set_state(EditorState((self.screen_width, self.screen_height)))
                return # Event handled

            # --- Handle other playing input (e.g., pause) ---
            # elif not self._game_over and not self._level_won and event.key == pygame.K_ESCAPE:
            #    self.manager.set_state(PauseState(self))


    # --- MODIFIED update method ---
    def update(self, dt):
        """Update gameplay logic."""
        # Freeze screen if game is over or won, waiting for Enter
        if self._game_over or self._level_won:
            # We might still want player animation to finish?
            # If player exists and is dead, let animation update
            if self.game_world.player and self.game_world.player.is_dead:
                self.game_world.player.update_animation(dt)
            return # Skip game logic updates

        keys = pygame.key.get_pressed()

        # Reset respawn flag before update
        self.game_world.player_needs_respawn = False

        # Update Player Input & State
        if self.game_world.player:
            self.game_world.update_player_state(dt, keys)

        # Step Physics (Collision handlers run here, may set flags)
        self.game_world.step_physics(dt)

        # --- Handle Deferred Actions AFTER Physics Step ---
        # 1. Handle non-fatal respawn if flagged
        if self.game_world.player_needs_respawn:
            self.game_world.respawn_player() # Teleport without health reset
            self.game_world.player_needs_respawn = False # Reset flag

        # --- Check Game End Conditions AFTER potential respawn ---
        player_alive_and_exists = self.game_world.player and not self.game_world.player.is_dead

        # 2. Check if player IS dead AND death animation finished
        if self.game_world.player and self.game_world.player.is_dead and self.game_world.player.animation_finished:
             print("Game Over Transition (Death Anim Finished)")
             self._game_over = True
             return # Freeze game loop

        # 3. Check fall condition (only if player alive)
        if player_alive_and_exists and self.game_world.check_fall_condition():
             print("Game Over Transition (Fell)")
             self.game_world.player.is_dead = True # Mark as dead if fell
             self.game_world.player.set_animation("death") # Trigger death anim (optional for falling)
             # Game over screen will appear after animation finishes next frame
             return # Let animation play

        # 4. Check win condition (only if player alive)
        if player_alive_and_exists and self.game_world.check_win_condition():
             print("Win Transition")
             self._level_won = True
             return # Freeze game loop

        # --- Update Camera, Checkpoints (only if game not ended) ---
        if player_alive_and_exists:
             self.game_world.update_camera()
             self.game_world.update_checkpoints()


    def draw(self, screen):
        """Draw the playing view."""
        screen.fill((100, 100, 120))
        self.game_world.draw(screen)
        self.game_world.draw_hud(screen)

        # --- Draw Win/Game Over Overlays ---
        overlay_drawn = False
        if self._level_won:
            overlay_surf = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA); overlay_surf.fill((50, 50, 50, 180)); screen.blit(overlay_surf, (0, 0))
            win_text = self.end_message_font.render("You Win!", True, (100, 255, 100)); win_rect = win_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 30)); screen.blit(win_text, win_rect)
            enter_text = self.info_font.render("Press Enter to return to Editor", True, (200, 200, 200)); enter_rect = enter_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 40)); screen.blit(enter_text, enter_rect)
            overlay_drawn = True
        # Show Game Over screen only AFTER death animation finishes
        if self._game_over:
             # We could check player.animation_finished here again, but _game_over flag
             # is only set after the animation is done in update()
             if not overlay_drawn: overlay_surf = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA); overlay_surf.fill((80, 0, 0, 190)); screen.blit(overlay_surf, (0, 0))
             game_over_text = self.end_message_font.render("Game Over", True, (255, 80, 80)); go_rect = game_over_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 30)); screen.blit(game_over_text, go_rect)
             enter_text = self.info_font.render("Press Enter to return to Editor", True, (200, 200, 200)); enter_rect = enter_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 40)); screen.blit(enter_text, enter_rect)