from pooltool.ani.menu._registry import MenuNavigator, MenuRegistry
from pooltool.ani.menu.menus.game_setup import GameSetupMenu
from pooltool.ani.menu.menus.main_menu import MainMenu
from pooltool.ani.menu.menus.multiplayer import (
    MultiplayerLobbyMenu,
    MultiplayerMenu,
)
from pooltool.ani.menu.menus.settings import SettingsMenu

MenuRegistry.register(GameSetupMenu)
MenuRegistry.register(MainMenu)
MenuRegistry.register(SettingsMenu)
MenuRegistry.register(MultiplayerMenu)
MenuRegistry.register(MultiplayerLobbyMenu)

__all__ = [
    "MenuRegistry",
    "MenuNavigator",
]
