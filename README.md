/home/minseok/Gaming/Computer_Games/gamebuilder/assets/Ninja_10KStudios/facing_fwd/Ninja_10KStudios_fwd_spritesheet.png

.
├── main.py
├── toolbar.py
├── player.py         # NEW: Player class
├── shape.py          # NEW: Shape class
├── game_world.py     # NEW: Manages space, objects, physics, drawing world
├── level_data.py     # NEW: Simple data structure for level definition (optional for now, integrated in GameWorld)
├── states/           # NEW: Directory for states
│   ├── __init__.py
│   ├── base_state.py # NEW: Base GameState class
│   ├── editor_state.py # NEW: Handles editor mode
│   └── playing_state.py # NEW: Handles playing mode
├── level.json        # Existing save file
└── assets/           # Optional: For images like hearts
    └── heart.png     # (If you have one)
