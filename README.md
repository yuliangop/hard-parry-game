# Hard Parry Game

A standalone Python action prototype inspired by high-difficulty sword duels.

## Run

```powershell
cd C:\Users\yuliang\Desktop\hard_parry_game
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python src\main.py
```

## Controls

- `WASD`: move
- `Mouse`: aim
- `Left mouse`: attack
- `Right mouse` or `F`: parry
- `Space`: dash
- `R`: restart after death/victory
- `Esc`: quit

## Combat

- Parry during the red flash attack window to stagger enemies.
- Regular blocking is weak. Perfect parry is the heart of the game.
- Posture breaks trigger execution damage.
- Bosses gain new behavior as their health drops.
- Music is procedurally generated at startup, so each run gets a slightly different tense loop.

## Blender Asset Generation

If Blender is installed and available as `blender`, generate placeholder low-poly models:

```powershell
blender --background --python tools\make_blender_assets.py
```

The script creates a stylized arena and four character models under `assets/generated_blender`.

## GitHub Upload

This project is ready to initialize and push. You will need to provide:

- GitHub username
- Repository name
- A GitHub token with repo permission
