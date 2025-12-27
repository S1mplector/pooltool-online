#! /usr/bin/env python
"""Splash screen mode displaying 'X presents' before the main menu."""

from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import TextNode, TransparencyAttrib

import pooltool.ani.tasks as tasks
from pooltool.ani.action import Action
from pooltool.ani.constants import logo_paths
from pooltool.ani.fonts import load_font
from pooltool.ani.globals import Global
from pooltool.ani.modes.datatypes import BaseMode, Mode
from pooltool.ani.mouse import MouseMode, mouse


class SplashMode(BaseMode):
    """Splash screen mode that shows 'X (name you desire) presents' before the main menu."""

    name = Mode.splash
    keymap = {
        Action.exit: False,
        Action.click: False,
    }

    def __init__(self):
        super().__init__()
        self.splash_frame = None
        self.presenter_label = None
        self.logo_image = None
        self.online_label = None
        self.fade_task_name = "splash_fade_task"
        self.auto_advance_task_name = "splash_auto_advance"

    def enter(self):
        mouse.mode(MouseMode.ABSOLUTE)

        # Create full-screen backdrop
        self.splash_frame = DirectFrame(
            frameColor=(0.02, 0.02, 0.02, 1),
            frameSize=(-2, 2, -2, 2),
            parent=Global.render2d,
        )

        # Load custom font
        title_font = load_font("LABTSECW")

        # "S1mplector presents" text
        self.presenter_label = DirectLabel(
            text="S1mplector presents",
            text_font=title_font,
            scale=0.12,
            pos=(0, 0, 0.1),
            parent=self.splash_frame,
            relief=None,
            text_fg=(0.9, 0.75, 0.3, 1),  # Golden color
            text_align=TextNode.ACenter,
        )

        # Add the pooltool logo below
        self.logo_image = OnscreenImage(
            image=logo_paths["default"],
            pos=(0, 0, -0.2),
            parent=self.splash_frame,
            scale=(1.4 * 0.2, 1, 1.4 * 0.18),
        )
        self.logo_image.setTransparency(TransparencyAttrib.MAlpha)

        # "Online" label below the logo
        self.online_label = DirectLabel(
            text="Online",
            text_font=title_font,
            scale=0.08,
            pos=(0, 0, -0.45),
            parent=self.splash_frame,
            relief=None,
            text_fg=(0.3, 0.7, 0.9, 1),  # Blue color
            text_align=TextNode.ACenter,
        )

        # Register events to skip splash
        self.register_keymap_event("escape", Action.exit, True)
        self.register_keymap_event("escape-up", Action.exit, False)
        self.register_keymap_event("mouse1", Action.click, True)
        self.register_keymap_event("mouse1-up", Action.click, False)
        self.register_keymap_event("space", Action.click, True)
        self.register_keymap_event("space-up", Action.click, False)
        self.register_keymap_event("enter", Action.click, True)
        self.register_keymap_event("enter-up", Action.click, False)

        # Task to check for skip input
        tasks.add(self.splash_task, "splash_task")

        # Auto-advance after 3 seconds
        tasks.add_later(3.0, self._auto_advance, self.auto_advance_task_name)

    def exit(self):
        # Clean up UI elements
        if self.splash_frame:
            self.splash_frame.destroy()
            self.splash_frame = None

        if self.presenter_label:
            self.presenter_label.destroy()
            self.presenter_label = None

        if self.logo_image:
            self.logo_image.destroy()
            self.logo_image = None

        if self.online_label:
            self.online_label.destroy()
            self.online_label = None

        # Remove tasks
        tasks.remove("splash_task")
        tasks.remove(self.auto_advance_task_name)

    def splash_task(self, task):
        """Check for user input to skip the splash screen."""
        if self.keymap[Action.exit] or self.keymap[Action.click]:
            self._go_to_menu()
            return task.done

        return task.cont

    def _auto_advance(self, task):
        """Automatically advance to menu after timeout."""
        self._go_to_menu()
        return task.done

    def _go_to_menu(self):
        """Transition to the main menu."""
        Global.mode_mgr.change_mode(Mode.menu)
