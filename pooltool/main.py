#!/usr/bin/env python


import attrs
import click

from pooltool.ani.animate import Game, ShowBaseConfig


@click.command()
@click.option("--monitor", is_flag=True, help="Spit out per-frame info about game")
@click.option("--fast", is_flag=True, help="Performance mode: reduced graphics for better FPS on macOS")
def run(monitor, fast):
    # Apply performance mode settings before creating the game
    if fast:
        from pooltool.config import settings
        # Reduce graphics for performance
        settings.graphics.shader = False
        settings.graphics.room = False
        settings.graphics.shadows = False
        settings.graphics.max_lights = 2
        settings.graphics.fps = 60
        settings.system.window_width = 1200
        click.echo("🚀 Performance mode enabled")

    config = attrs.evolve(ShowBaseConfig.default(), monitor=monitor)

    play = Game(config)
    play.start()


if __name__ == "__main__":
    run()
