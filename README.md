# 🎱 Pooltool Online

A fork of pooltool with online multiplayer capabilities. 

<img src="pooltool/logo/logo_online.png" width="600" />

# Description

*Pooltool Online* is a fork of the realistic billiards simulator featuring:

- **Online Multiplayer** - Play pool with friends over the internet
- **3D Graphics** - Powered by Panda3D
- **Realistic Physics** - Accurate ball dynamics and collision detection
- **Multiple Game Modes** - 8-ball, 9-ball, snooker, and more
- **Extensible API** - Build your own pool AI or custom game modes

## New in this Fork

- **Online Multiplayer System** - Full client/server architecture
- **Room-based Matchmaking** - Create and join game rooms
- **Real-time Sync** - See opponent shots live

# Gallery

<img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_1.png" width="350" /><img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_2.png" width="350" /><img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_3.png" width="350" /><img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_5.png" width="350" /><img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_6.png" width="350" /><img src="https://ekiefl.github.io/images/pooltool/pooltool-graphics/gallery_7.png" width="350" />

# Installation

## One-Click Launch (Recommended)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/pooltool.git
cd pooltool

# Run it!
./run.sh        # macOS/Linux
run.bat         # Windows
```

That's it! The script handles everything: virtual environment, dependencies, and launching the game.

### Performance Mode (macOS)

If you're getting low FPS on macOS (especially Apple Silicon), use performance mode:

```bash
./run.sh --fast
```

This disables advanced shaders and reduces graphics settings for smoother gameplay.

## Manual Setup

If you prefer manual setup:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install poetry==1.8.4
poetry install
poetry run run-pooltool
```

# Usage

## Single Player
1. Launch the game with `poetry run run-pooltool`
2. Click through the splash screen
3. Select **New Game** from the main menu
4. Choose your game type and start playing!

## Online Multiplayer

### Host a Game (anyone can join from anywhere)
1. Launch the game and go to **Online Multiplayer**
2. Click **Host Game**
3. Share the address shown with your friend (works over the internet!)
4. Wait for them to join and click **Ready**

### Join a Game
1. Launch the game and go to **Online Multiplayer**  
2. Enter the address your friend shared
3. Click **Join Game**
4. Click **Ready** when you're in the lobby

> **Note:** Internet play uses ngrok tunneling. The address format is like `0.tcp.ngrok.io:12345`

# Credits

This project is a fork of [pooltool](https://github.com/ekiefl/pooltool) by **Evan Kiefl** respectfully. 

Original work licensed under Apache 2.0. See [NOTICE](NOTICE) for attribution details.

If you use the physics engine in research, please cite the original JOSS publication.

```
@article{Kiefl2024,
    doi = {10.21105/joss.07301},
    url = {https://doi.org/10.21105/joss.07301},
    year = {2024},
    publisher = {The Open Journal},
    volume = {9},
    number = {101},
    pages = {7301},
    author = {Evan Kiefl},
    title = {Pooltool: A Python package for realistic billiards simulation},
    journal = {Journal of Open Source Software}
}
```

# License

Apache 2.0 - See [LICENSE.txt](LICENSE.txt)
