#! /usr/bin/env python
"""Simplified multiplayer menu UI - easy host and join over the internet."""

from __future__ import annotations

import socket
import subprocess
import sys
import threading

from direct.gui.DirectGui import (
    DGG,
    DirectButton,
    DirectEntry,
    DirectFrame,
    DirectLabel,
)
from panda3d.core import TextNode

from pooltool.ani.fonts import load_font
from pooltool.ani.globals import Global
from pooltool.ani.menu._datatypes import (
    BUTTON_FONT,
    BUTTON_TEXT_SCALE,
    BaseMenu,
    MenuButton,
    MenuTitle,
    TEXT_COLOR,
    TITLE_FONT,
)
from pooltool.ani.menu._registry import MenuNavigator
from pooltool.multiplayer import MultiplayerClient
from pooltool.multiplayer.protocol import RoomInfo

# Global tunnel state
_tunnel_url: str | None = None
_ngrok_process = None


def get_local_ip() -> str:
    """Get the local IP address for sharing with friends."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_tunnel(port: int = 7777) -> str | None:
    """Start an ngrok tunnel to make server accessible over internet.
    
    Returns the public URL if successful, None otherwise.
    Note: ngrok now requires credit card verification for TCP tunnels on free accounts.
    """
    global _tunnel_url, _ngrok_process
    
    try:
        from pyngrok import ngrok, conf
        from pyngrok.exception import PyngrokNgrokError
        
        # Configure ngrok
        conf.get_default().log_level = "ERROR"
        
        # Start tunnel
        tunnel = ngrok.connect(port, "tcp")
        _tunnel_url = tunnel.public_url  # e.g., "tcp://0.tcp.ngrok.io:12345"
        
        # Parse the URL to get host:port
        if _tunnel_url.startswith("tcp://"):
            _tunnel_url = _tunnel_url[6:]  # Remove "tcp://" prefix
        
        return _tunnel_url
    except ImportError:
        # pyngrok not installed - fall back to local only
        return None
    except Exception as e:
        # ngrok TCP endpoints now require credit card on free accounts
        # Just silently fall back to LAN mode
        return None


def stop_tunnel() -> None:
    """Stop the ngrok tunnel."""
    global _tunnel_url, _ngrok_process
    
    try:
        from pyngrok import ngrok
        ngrok.kill()
    except Exception:
        pass
    
    _tunnel_url = None


class MultiplayerMenu(BaseMenu):
    """Simplified multiplayer menu - Host or Join with minimal clicks."""

    name: str = "multiplayer"

    def __init__(self) -> None:
        super().__init__()
        self.client: MultiplayerClient | None = None
        self.server_process = None
        self.status_label: DirectLabel | None = None
        self.ip_label: DirectLabel | None = None
        self.public_url: str | None = None

    def populate(self) -> None:
        # Clean up any stale client connection/task from previous session
        Global.task_mgr.remove("multiplayer_client_update")
        if self.client and self.client.is_connected and not self.server_process:
            # Disconnect stale client (but keep if we're hosting)
            self.client.disconnect()
            self.client = None

        # Create title fresh each time to avoid stale node issues
        title = MenuTitle.create(text="Online Multiplayer")
        self.add_title(title)

        font = load_font(BUTTON_FONT)
        title_font = load_font(TITLE_FONT)

        # Status label at top
        self.status_label = DirectLabel(
            text="Choose an option below",
            scale=BUTTON_TEXT_SCALE * 0.7,
            relief=None,
            text_fg=(0.7, 0.7, 0.7, 1),
            text_align=TextNode.ACenter,
            text_font=title_font,
            parent=self.area.getCanvas(),
        )
        self.status_label.setPos(0, 0, 0.55)

        # ==================== HOST GAME SECTION ====================
        host_frame = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.8),
            frameSize=(-0.75, 0.75, -0.25, 0.15),
            pos=(0, 0, 0.25),
            parent=self.area.getCanvas(),
            state=DGG.NORMAL,
            suppressMouse=False,
        )

        host_title = DirectLabel(
            text="HOST A GAME",
            scale=BUTTON_TEXT_SCALE * 0.9,
            relief=None,
            text_fg=(0.3, 0.8, 0.3, 1),
            text_align=TextNode.ACenter,
            text_font=title_font,
            parent=host_frame,
        )
        host_title.setPos(0, 0, 0.08)

        host_desc = DirectLabel(
            text="Start a server and invite friends",
            scale=BUTTON_TEXT_SCALE * 0.5,
            relief=None,
            text_fg=(0.6, 0.6, 0.6, 1),
            text_align=TextNode.ACenter,
            text_font=font,
            parent=host_frame,
        )
        host_desc.setPos(0, 0, 0.0)

        self.host_button = DirectButton(
            text="Host Game",
            text_align=TextNode.ACenter,
            text_font=font,
            scale=BUTTON_TEXT_SCALE * 1.2,
            relief=DGG.RIDGE,
            frameColor=(0.2, 0.6, 0.2, 1),
            frameSize=(-0.35, 0.35, -0.06, 0.08),
            command=self._host_game,
            parent=host_frame,
        )
        self.host_button.setPos(0, 0, -0.15)

        # ==================== JOIN GAME SECTION ====================
        join_frame = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.8),
            frameSize=(-0.75, 0.75, -0.35, 0.15),
            pos=(0, 0, -0.25),
            parent=self.area.getCanvas(),
            state=DGG.NORMAL,
            suppressMouse=False,
        )

        join_title = DirectLabel(
            text="JOIN A GAME",
            scale=BUTTON_TEXT_SCALE * 0.9,
            relief=None,
            text_fg=(0.3, 0.6, 0.9, 1),
            text_align=TextNode.ACenter,
            text_font=title_font,
            parent=join_frame,
        )
        join_title.setPos(0, 0, 0.08)

        join_desc = DirectLabel(
            text="Enter the host's IP address",
            scale=BUTTON_TEXT_SCALE * 0.5,
            relief=None,
            text_fg=(0.6, 0.6, 0.6, 1),
            text_align=TextNode.ACenter,
            text_font=font,
            parent=join_frame,
        )
        join_desc.setPos(0, 0, 0.0)

        # IP input
        ip_label = DirectLabel(
            text="IP:",
            scale=BUTTON_TEXT_SCALE * 0.6,
            relief=None,
            text_fg=TEXT_COLOR,
            text_align=TextNode.ARight,
            text_font=font,
            parent=join_frame,
        )
        ip_label.setPos(-0.35, 0, -0.12)

        self.ip_entry = DirectEntry(
            text="",
            scale=BUTTON_TEXT_SCALE * 0.6,
            width=15,
            relief=DGG.SUNKEN,
            frameColor=(1, 1, 1, 0.9),
            text_fg=(0, 0, 0, 1),
            text_font=font,
            initialText="localhost",
            numLines=1,
            parent=join_frame,
        )
        self.ip_entry.setPos(-0.25, 0, -0.12)

        self.join_button = DirectButton(
            text="Join Game",
            text_align=TextNode.ACenter,
            text_font=font,
            scale=BUTTON_TEXT_SCALE * 1.2,
            relief=DGG.RIDGE,
            frameColor=(0.2, 0.4, 0.7, 1),
            frameSize=(-0.35, 0.35, -0.06, 0.08),
            command=self._join_game,
            parent=join_frame,
        )
        self.join_button.setPos(0, 0, -0.25)

        # Your IP display (for sharing)
        local_ip = get_local_ip()
        self.ip_label = DirectLabel(
            text=f"Your IP: {local_ip}",
            scale=BUTTON_TEXT_SCALE * 0.5,
            relief=None,
            text_fg=(0.5, 0.5, 0.5, 1),
            text_align=TextNode.ACenter,
            text_font=font,
            parent=self.area.getCanvas(),
        )
        self.ip_label.setPos(0, 0, -0.7)

        # Back button - create fresh each time
        back_button = MenuButton.create(
            text="Back",
            command=self._go_back,
            description="Return to main menu",
        )
        self.add_button(back_button)

    def _update_status(self, text: str, color: tuple = (0.7, 0.7, 0.7, 1)) -> None:
        """Update status message."""
        if self.status_label:
            self.status_label["text"] = text
            self.status_label["text_fg"] = color

    def _host_game(self) -> None:
        """Start server and create a game room accessible over internet."""
        self._update_status("Starting server...", (0.8, 0.8, 0.3, 1))

        # Start the server in a subprocess
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, "-m", "pooltool.multiplayer.server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Give server time to start, then create tunnel
            def setup_and_connect():
                import time
                time.sleep(1.0)
                
                # Try to create internet tunnel
                self.public_url = start_tunnel(7777)
                
                if self.public_url:
                    # Update UI on main thread
                    Global.task_mgr.add(
                        lambda task: self._on_tunnel_ready(self.public_url),
                        "tunnel_ready_task"
                    )
                else:
                    # Fall back to LAN only
                    Global.task_mgr.add(
                        lambda task: self._connect_as_host_lan(),
                        "connect_as_host_task"
                    )

            threading.Thread(target=setup_and_connect, daemon=True).start()

        except Exception as e:
            self._update_status(f"Failed to start server: {e}", (0.8, 0.3, 0.3, 1))

    def _on_tunnel_ready(self, public_url: str) -> None:
        """Handle tunnel being ready - update UI and connect."""
        # Update IP label to show public URL
        if self.ip_label:
            self.ip_label["text"] = f"Share this address: {public_url}"
            self.ip_label["text_fg"] = (0.3, 0.9, 0.3, 1)
        
        self._update_status("Internet tunnel ready!", (0.3, 0.8, 0.3, 1))
        self._connect_as_host()

    def _connect_as_host_lan(self) -> None:
        """Connect as host (LAN only mode)."""
        if self.ip_label:
            local_ip = get_local_ip()
            self.ip_label["text"] = f"LAN only - Share IP: {local_ip}:7777"
            self.ip_label["text_fg"] = (0.9, 0.7, 0.3, 1)
        
        self._update_status("Server ready (LAN only - install pyngrok for internet)", (0.9, 0.7, 0.3, 1))
        self._connect_as_host()

    def _connect_as_host(self) -> None:
        """Connect to the local server as host."""
        self._setup_client()
        self.client.connect("localhost", 7777, "Host")
        self._update_status("Connecting to local server...", (0.8, 0.8, 0.3, 1))
        Global.task_mgr.add(self._update_client, "multiplayer_client_update")

    def _join_game(self) -> None:
        """Join a remote game (supports both IP and ngrok URLs)."""
        address = self.ip_entry.get().strip()
        if not address:
            self._update_status("Please enter an address", (0.8, 0.3, 0.3, 1))
            return

        # Parse address - could be "ip", "ip:port", or "host.ngrok.io:port"
        if ":" in address:
            parts = address.rsplit(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                port = 7777
        else:
            host = address
            port = 7777

        self._update_status(f"Connecting to {host}:{port}...", (0.8, 0.8, 0.3, 1))
        self._setup_client()
        self.client.connect(host, port, "Player")
        Global.task_mgr.add(self._update_client, "multiplayer_client_update")

    def _setup_client(self) -> None:
        """Initialize the multiplayer client."""
        # Always create a fresh client to avoid stale connection issues
        if self.client and self.client.is_connected:
            self.client.disconnect()
        self.client = MultiplayerClient()

        self.client.on_connected = self._on_connected
        self.client.on_disconnected = self._on_disconnected
        self.client.on_room_list = self._on_room_list
        self.client.on_room_update = self._on_room_update
        self.client.on_game_start = self._on_game_start
        self.client.on_error = self._on_error

    def _update_client(self, task):
        """Update client to process messages."""
        if self.client:
            self.client.update()
        return task.cont

    def _on_connected(self, player_id: str) -> None:
        """Handle successful connection."""
        # Automatically create/join a room
        if self.server_process:
            # We're the host - create a room and go to lobby
            self._update_status("Creating room...", (0.3, 0.8, 0.3, 1))
            self.client.create_room("Game Room", "8ball")
        else:
            # We're joining - request room list and auto-join first available
            self._update_status("Finding room...", (0.8, 0.8, 0.3, 1))
            self.client.request_room_list()

    def _on_disconnected(self) -> None:
        """Handle disconnection."""
        self._update_status("Disconnected", (0.8, 0.3, 0.3, 1))
        Global.task_mgr.remove("multiplayer_client_update")

    def _on_room_list(self, rooms: list[dict]) -> None:
        """Handle room list - auto-join first available room."""
        if rooms:
            room_id = rooms[0].get("room_id", "")
            if room_id:
                self.client.join_room(room_id)
                self._update_status("Joining room...", (0.8, 0.8, 0.3, 1))
        else:
            self._update_status("No rooms available. Try hosting instead.", (0.8, 0.5, 0.3, 1))

    def _on_room_update(self, room: RoomInfo) -> None:
        """Handle room update - go to lobby."""
        self._update_status("In lobby!", (0.3, 0.8, 0.3, 1))
        MenuNavigator.go_to_menu("multiplayer_lobby")()

    def _on_game_start(self, game_state) -> None:
        """Handle game start."""
        Global.base.messenger.send("enter-game")

    def _on_error(self, error: str) -> None:
        """Handle error message."""
        self._update_status(f"Error: {error}", (0.8, 0.3, 0.3, 1))

    def _go_back(self) -> None:
        """Return to main menu."""
        # Clean up
        if self.client and self.client.is_connected:
            self.client.disconnect()
        Global.task_mgr.remove("multiplayer_client_update")

        # Stop tunnel if running
        stop_tunnel()
        self.public_url = None

        # Kill server if we started one
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None

        MenuNavigator.go_to_menu("main_menu")()

    def hide(self) -> None:
        """Clean up when hiding menu."""
        super().hide()


class MultiplayerLobbyMenu(BaseMenu):
    """ Lobby - shows players, ready button, and start game for host."""

    name: str = "multiplayer_lobby"

    def __init__(self) -> None:
        super().__init__()
        self._dynamic_elements = []

    def _clear_dynamic_elements(self) -> None:
        """Clear all dynamically created elements to prevent overlap on refresh."""
        for elem in self._dynamic_elements:
            try:
                elem.destroy()
            except Exception:
                try:
                    elem.removeNode()
                except Exception:
                    pass
        self._dynamic_elements = []

    def populate(self) -> None:
        from pooltool.ani.menu._registry import MenuRegistry

        # Clear any existing dynamic elements first
        self._clear_dynamic_elements()

        # Create title fresh each time to avoid stale node issues
        title = MenuTitle.create(text="Game Lobby")
        self.add_title(title)

        font = load_font(BUTTON_FONT)
        title_font = load_font(TITLE_FONT)

        # Get client
        mp_menu = MenuRegistry.get_menu("multiplayer")
        client = mp_menu.client if mp_menu and hasattr(mp_menu, "client") else None
        room = client.current_room if client else None

        # Determine if current player is host
        is_host = False
        is_ready = False
        all_ready = False
        if client and room and room.players:
            for p in room.players:
                if p.player_id == client.player_id:
                    is_host = p.is_host
                    is_ready = p.is_ready
            all_ready = all(p.is_ready for p in room.players) and len(room.players) >= 2

        # Share address instruction - use public URL if available
        share_address = mp_menu.public_url if (mp_menu and hasattr(mp_menu, "public_url") and mp_menu.public_url) else f"{get_local_ip()}:7777"
        is_public = mp_menu and hasattr(mp_menu, "public_url") and mp_menu.public_url

        share_label = DirectLabel(
            text=f"Share: {share_address}",
            scale=BUTTON_TEXT_SCALE * 0.6,
            relief=None,
            text_fg=(0.3, 0.9, 0.3, 1) if is_public else (0.9, 0.7, 0.3, 1),
            text_align=TextNode.ACenter,
            text_font=font,
            parent=self.area.getCanvas(),
        )
        share_label.setPos(0, 0, 0.50)
        self._dynamic_elements.append(share_label)

        mode_text = "(Internet)" if is_public else "(LAN only)"
        mode_label = DirectLabel(
            text=mode_text,
            scale=BUTTON_TEXT_SCALE * 0.4,
            relief=None,
            text_fg=(0.5, 0.8, 0.5, 1) if is_public else (0.6, 0.5, 0.3, 1),
            text_align=TextNode.ACenter,
            text_font=font,
            parent=self.area.getCanvas(),
        )
        mode_label.setPos(0, 0, 0.40)
        self._dynamic_elements.append(mode_label)

        # Players section header
        players_header = DirectLabel(
            text="--- Players ---",
            scale=BUTTON_TEXT_SCALE * 0.7,
            relief=None,
            text_fg=(0.7, 0.7, 0.7, 1),
            text_align=TextNode.ACenter,
            text_font=title_font,
            parent=self.area.getCanvas(),
        )
        players_header.setPos(0, 0, 0.25)
        self._dynamic_elements.append(players_header)

        # Player list - cleaner layout
        y_pos = 0.10
        if room and room.players:
            for player in room.players:
                is_you = client and player.player_id == client.player_id

                # Player name
                name_text = player.name
                if is_you:
                    name_text += " (You)"
                if player.is_host:
                    name_text += " [HOST]"

                name_color = (0.9, 0.9, 0.9, 1) if is_you else (0.7, 0.7, 0.7, 1)
                name_label = DirectLabel(
                    text=name_text,
                    scale=BUTTON_TEXT_SCALE * 0.65,
                    relief=None,
                    text_fg=name_color,
                    text_align=TextNode.ACenter,
                    text_font=font,
                    parent=self.area.getCanvas(),
                )
                name_label.setPos(0, 0, y_pos)
                self._dynamic_elements.append(name_label)

                # Ready status on separate line
                status_text = "READY" if player.is_ready else "Not Ready"
                status_color = (0.3, 0.9, 0.3, 1) if player.is_ready else (0.5, 0.5, 0.5, 1)
                status_label = DirectLabel(
                    text=status_text,
                    scale=BUTTON_TEXT_SCALE * 0.45,
                    relief=None,
                    text_fg=status_color,
                    text_align=TextNode.ACenter,
                    text_font=font,
                    parent=self.area.getCanvas(),
                )
                status_label.setPos(0, 0, y_pos - 0.07)
                self._dynamic_elements.append(status_label)

                y_pos -= 0.18
        else:
            waiting_label = DirectLabel(
                text="Waiting for players...",
                scale=BUTTON_TEXT_SCALE * 0.6,
                relief=None,
                text_fg=(0.5, 0.5, 0.5, 1),
                text_align=TextNode.ACenter,
                text_font=font,
                parent=self.area.getCanvas(),
            )
            waiting_label.setPos(0, 0, 0.0)
            self._dynamic_elements.append(waiting_label)

        # Buttons section
        btn_y = -0.35

        # Ready button - larger and more clickable
        ready_btn = DirectButton(
            text="READY!" if not is_ready else "NOT READY",
            text_align=TextNode.ACenter,
            text_font=font,
            scale=BUTTON_TEXT_SCALE * 1.3,
            relief=DGG.RIDGE,
            frameColor=(0.2, 0.7, 0.2, 1) if not is_ready else (0.7, 0.3, 0.3, 1),
            frameSize=(-0.4, 0.4, -0.07, 0.09),
            command=self._toggle_ready,
            parent=self.area.getCanvas(),
        )
        ready_btn.setPos(0, 0, btn_y)
        self._dynamic_elements.append(ready_btn)

        # Start Game button - only for host when all ready
        if is_host:
            btn_y -= 0.18
            start_enabled = all_ready
            start_btn = DirectButton(
                text="START GAME" if start_enabled else "Waiting...",
                text_align=TextNode.ACenter,
                text_font=font,
                scale=BUTTON_TEXT_SCALE * 1.2,
                relief=DGG.RIDGE,
                frameColor=(0.8, 0.6, 0.1, 1) if start_enabled else (0.3, 0.3, 0.3, 1),
                frameSize=(-0.4, 0.4, -0.07, 0.09),
                command=self._start_game if start_enabled else None,
                parent=self.area.getCanvas(),
            )
            start_btn.setPos(0, 0, btn_y)
            if not start_enabled:
                start_btn["state"] = DGG.DISABLED
            self._dynamic_elements.append(start_btn)

        # Leave button
        btn_y -= 0.15
        leave_btn = DirectButton(
            text="Leave Room",
            text_align=TextNode.ACenter,
            text_font=font,
            scale=BUTTON_TEXT_SCALE * 0.8,
            relief=DGG.RIDGE,
            frameColor=(0.5, 0.3, 0.3, 1),
            frameSize=(-0.3, 0.3, -0.05, 0.07),
            command=self._leave_room,
            parent=self.area.getCanvas(),
        )
        self._dynamic_elements.append(leave_btn)
        leave_btn.setPos(0, 0, btn_y)

    def _toggle_ready(self) -> None:
        """Toggle ready status."""
        from pooltool.ani.menu._registry import MenuRegistry

        mp_menu = MenuRegistry.get_menu("multiplayer")
        if mp_menu and hasattr(mp_menu, "client") and mp_menu.client:
            client = mp_menu.client
            if client.current_room:
                for p in client.current_room.players:
                    if p.player_id == client.player_id:
                        client.set_ready(not p.is_ready)
                        # Refresh the lobby display
                        MenuNavigator.go_to_menu("multiplayer_lobby")()
                        break

    def _start_game(self) -> None:
        """Start the multiplayer game (host only)."""
        from pooltool.ani.menu._registry import MenuRegistry

        mp_menu = MenuRegistry.get_menu("multiplayer")
        if mp_menu and hasattr(mp_menu, "client") and mp_menu.client:
            # Send start game message to server - server will broadcast to all players
            mp_menu.client.start_game()

    def _leave_room(self) -> None:
        """Leave the current room."""
        from pooltool.ani.menu._registry import MenuRegistry

        mp_menu = MenuRegistry.get_menu("multiplayer")
        if mp_menu and hasattr(mp_menu, "client") and mp_menu.client:
            mp_menu.client.leave_room()

        MenuNavigator.go_to_menu("multiplayer")()
