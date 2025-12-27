#! /usr/bin/env python
"""Multiplayer client for connecting to online pool games."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

import attrs

from pooltool.multiplayer.protocol import (
    CueState,
    GameMessage,
    GameState,
    MessageType,
    PlayerInfo,
    RoomInfo,
)

logger = logging.getLogger(__name__)


@attrs.define
class MultiplayerClient:
    """Client for connecting to multiplayer pool game servers.

    This client handles network communication with the server and provides
    an event-driven interface for game state updates.

    Example:
        >>> client = MultiplayerClient()
        >>> client.connect("localhost", 7777, "MyName")
        >>> client.create_room("My Room", "8ball")
    """

    host: str = ""
    port: int = 7777
    player_id: str = ""
    player_name: str = ""

    # Connection state
    is_connected: bool = False
    current_room: RoomInfo | None = None
    game_state: GameState | None = None

    # Callbacks for events
    on_connected: Callable[[str], None] | None = None
    on_disconnected: Callable[[], None] | None = None
    on_room_update: Callable[[RoomInfo], None] | None = None
    on_room_list: Callable[[list[dict]], None] | None = None
    on_game_start: Callable[[GameState], None] | None = None
    on_shot_aim: Callable[[dict], None] | None = None
    on_shot_execute: Callable[[dict], None] | None = None
    on_turn_change: Callable[[str], None] | None = None
    on_game_over: Callable[[str | None], None] | None = None
    on_chat_message: Callable[[str, str], None] | None = None
    on_error: Callable[[str], None] | None = None

    # Internal state
    _reader: asyncio.StreamReader | None = attrs.field(default=None, repr=False)
    _writer: asyncio.StreamWriter | None = attrs.field(default=None, repr=False)
    _loop: asyncio.AbstractEventLoop | None = attrs.field(default=None, repr=False)
    _thread: threading.Thread | None = attrs.field(default=None, repr=False)
    _running: bool = attrs.field(default=False, repr=False)
    _message_queue: Queue = attrs.field(factory=Queue, repr=False)

    def connect(self, host: str, port: int, name: str) -> bool:
        """Connect to a multiplayer server.

        Args:
            host: Server hostname or IP address.
            port: Server port number.
            name: Player's display name.

        Returns:
            True if connection initiated successfully.
        """
        self.host = host
        self.port = port
        self.player_name = name
        self._running = True

        # Start network thread
        self._thread = threading.Thread(target=self._run_network_loop, daemon=True)
        self._thread.start()

        return True

    def disconnect(self) -> None:
        """Disconnect from the server."""
        if not self.is_connected:
            return

        self._send_message(MessageType.DISCONNECT, {})
        self._running = False
        self.is_connected = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self.current_room = None
        self.game_state = None

        if self.on_disconnected:
            self.on_disconnected()

    def create_room(self, room_name: str, game_type: str = "8ball") -> None:
        """Create a new game room.

        Args:
            room_name: Name for the room.
            game_type: Type of pool game (e.g., "8ball", "9ball").
        """
        self._send_message(
            MessageType.CREATE_ROOM,
            {"room_name": room_name, "game_type": game_type},
        )

    def join_room(self, room_id: str) -> None:
        """Join an existing game room.

        Args:
            room_id: ID of the room to join.
        """
        self._send_message(MessageType.JOIN_ROOM, {"room_id": room_id})

    def leave_room(self) -> None:
        """Leave the current room."""
        self._send_message(MessageType.LEAVE_ROOM, {})
        self.current_room = None

    def request_room_list(self) -> None:
        """Request list of available rooms from server."""
        self._send_message(MessageType.ROOM_LIST, {})

    def set_ready(self, is_ready: bool = True) -> None:
        """Set player ready status.

        Args:
            is_ready: Whether the player is ready to start.
        """
        self._send_message(MessageType.PLAYER_READY, {"is_ready": is_ready})

    def start_game(self) -> None:
        """Start the game (host only). Server will broadcast GAME_START to all players."""
        self._send_message(MessageType.GAME_START, {})

    def send_shot_aim(
        self,
        phi: float,
        theta: float,
        V0: float,
        a: float,
        b: float,
        cue_ball_id: str,
    ) -> None:
        """Send shot aim update for live preview.

        Args:
            phi: Horizontal angle.
            theta: Elevation angle.
            V0: Strike velocity.
            a: English horizontal offset.
            b: English vertical offset.
            cue_ball_id: ID of the cue ball.
        """
        cue_state = CueState(
            phi=phi,
            theta=theta,
            V0=V0,
            a=a,
            b=b,
            cue_ball_id=cue_ball_id,
        )
        self._send_message(MessageType.SHOT_AIM, {"cue_state": attrs.asdict(cue_state)})

    def send_shot_execute(
        self,
        phi: float,
        theta: float,
        V0: float,
        a: float,
        b: float,
        cue_ball_id: str,
    ) -> None:
        """Execute a shot.

        Args:
            phi: Horizontal angle.
            theta: Elevation angle.
            V0: Strike velocity.
            a: English horizontal offset.
            b: English vertical offset.
            cue_ball_id: ID of the cue ball.
        """
        cue_state = CueState(
            phi=phi,
            theta=theta,
            V0=V0,
            a=a,
            b=b,
            cue_ball_id=cue_ball_id,
        )
        self._send_message(
            MessageType.SHOT_EXECUTE,
            {"cue_state": attrs.asdict(cue_state)},
        )

    def send_shot_result(
        self,
        ball_positions: dict[str, tuple[float, float, float]],
        ball_states: dict[str, str],
        score: dict[str, int],
        next_player_id: str,
        is_game_over: bool = False,
        winner_id: str | None = None,
    ) -> None:
        """Send shot result after simulation.

        Args:
            ball_positions: Final positions of all balls.
            ball_states: States of all balls.
            score: Current score.
            next_player_id: ID of the next player.
            is_game_over: Whether the game has ended.
            winner_id: ID of the winner if game is over.
        """
        self._send_message(
            MessageType.SHOT_RESULT,
            {
                "ball_positions": ball_positions,
                "ball_states": ball_states,
                "score": score,
                "next_player_id": next_player_id,
                "is_game_over": is_game_over,
                "winner_id": winner_id,
            },
        )

    def send_chat(self, message: str) -> None:
        """Send a chat message.

        Args:
            message: Chat message text.
        """
        self._send_message(MessageType.CHAT_MESSAGE, {"message": message})

    def update(self) -> None:
        """Process pending messages. Call this from the main thread."""
        while True:
            try:
                msg = self._message_queue.get_nowait()
                self._handle_message(msg)
            except Empty:
                break

    def is_my_turn(self) -> bool:
        """Check if it's this player's turn."""
        if not self.game_state:
            return False
        return self.game_state.current_player_id == self.player_id

    def _send_message(self, msg_type: MessageType, data: dict[str, Any]) -> None:
        """Queue a message to be sent to the server."""
        if not self._writer:
            return

        message = GameMessage(
            msg_type=msg_type,
            sender_id=self.player_id,
            data=data,
            timestamp=time.time(),
        )

        try:
            json_data = message.to_json() + "\n"
            if self._loop and self._running:
                asyncio.run_coroutine_threadsafe(
                    self._async_send(json_data.encode()),
                    self._loop,
                )
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _async_send(self, data: bytes) -> None:
        """Async send data to server."""
        if self._writer:
            self._writer.write(data)
            await self._writer.drain()

    def _run_network_loop(self) -> None:
        """Run the async network loop in a thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            logger.error(f"Network loop error: {e}")
        finally:
            self._loop.close()

    async def _connect_and_listen(self) -> None:
        """Connect to server and listen for messages."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host,
                self.port,
            )

            # Send connect message
            connect_msg = GameMessage(
                msg_type=MessageType.CONNECT,
                sender_id="",
                data={"name": self.player_name},
                timestamp=time.time(),
            )
            self._writer.write((connect_msg.to_json() + "\n").encode())
            await self._writer.drain()

            # Listen for messages
            while self._running:
                try:
                    data = await asyncio.wait_for(
                        self._reader.readline(),
                        timeout=0.5,
                    )
                    if not data:
                        break

                    message = GameMessage.from_json(data.decode().strip())
                    self._message_queue.put(message)

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    break

        except ConnectionRefusedError:
            logger.error(f"Connection refused to {self.host}:{self.port}")
            if self.on_error:
                self._message_queue.put(
                    GameMessage(
                        msg_type=MessageType.ERROR,
                        sender_id="client",
                        data={"error": "Connection refused"},
                        timestamp=time.time(),
                    )
                )
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self._running = False
            self.is_connected = False

            if self._writer:
                self._writer.close()
                try:
                    await self._writer.wait_closed()
                except Exception:
                    pass

    def _handle_message(self, message: GameMessage) -> None:
        """Handle an incoming message."""
        handlers = {
            MessageType.CONNECT: self._on_connect,
            MessageType.ROOM_UPDATE: self._on_room_update,
            MessageType.ROOM_LIST: self._on_room_list,
            MessageType.CREATE_ROOM: self._on_create_room,
            MessageType.JOIN_ROOM: self._on_join_room,
            MessageType.LEAVE_ROOM: self._on_leave_room,
            MessageType.GAME_START: self._on_game_start,
            MessageType.SHOT_AIM: self._on_shot_aim,
            MessageType.SHOT_EXECUTE: self._on_shot_execute,
            MessageType.TURN_CHANGE: self._on_turn_change,
            MessageType.GAME_OVER: self._on_game_over,
            MessageType.CHAT_MESSAGE: self._on_chat_message,
            MessageType.ERROR: self._on_error,
        }

        handler = handlers.get(message.msg_type)
        if handler:
            handler(message)

    def _on_connect(self, message: GameMessage) -> None:
        """Handle connection confirmation."""
        if message.data.get("success"):
            self.player_id = message.data.get("player_id", "")
            self.player_name = message.data.get("name", self.player_name)
            self.is_connected = True
            logger.info(f"Connected as {self.player_name} (ID: {self.player_id})")

            if self.on_connected:
                self.on_connected(self.player_id)

    def _on_room_update(self, message: GameMessage) -> None:
        """Handle room update."""
        room_data = message.data.get("room", {})
        if room_data:
            players = [
                PlayerInfo(**p) for p in room_data.get("players", [])
            ]
            self.current_room = RoomInfo(
                room_id=room_data["room_id"],
                room_name=room_data["room_name"],
                host_id=room_data["host_id"],
                players=players,
                max_players=room_data.get("max_players", 2),
                game_type=room_data.get("game_type", "8ball"),
                is_started=room_data.get("is_started", False),
            )

            if self.on_room_update:
                self.on_room_update(self.current_room)

    def _on_room_list(self, message: GameMessage) -> None:
        """Handle room list."""
        rooms = message.data.get("rooms", [])
        if self.on_room_list:
            self.on_room_list(rooms)

    def _on_create_room(self, message: GameMessage) -> None:
        """Handle room creation response."""
        if message.data.get("success"):
            self._on_room_update(message)

    def _on_join_room(self, message: GameMessage) -> None:
        """Handle room join response."""
        if message.data.get("success"):
            self._on_room_update(message)

    def _on_leave_room(self, message: GameMessage) -> None:
        """Handle room leave response."""
        self.current_room = None

    def _on_game_start(self, message: GameMessage) -> None:
        """Handle game start."""
        state_data = message.data.get("game_state", {})
        if state_data:
            self.game_state = GameState(
                room_id=state_data["room_id"],
                current_player_id=state_data["current_player_id"],
                turn_number=state_data["turn_number"],
                shot_number=state_data["shot_number"],
                ball_positions=state_data.get("ball_positions", {}),
                ball_states=state_data.get("ball_states", {}),
                cue_state=None,
                score=state_data.get("score", {}),
            )

            if self.on_game_start:
                self.on_game_start(self.game_state)

    def _on_shot_aim(self, message: GameMessage) -> None:
        """Handle shot aim update from opponent."""
        if self.on_shot_aim:
            self.on_shot_aim(message.data)

    def _on_shot_execute(self, message: GameMessage) -> None:
        """Handle shot execution."""
        if self.on_shot_execute:
            self.on_shot_execute(message.data)

    def _on_turn_change(self, message: GameMessage) -> None:
        """Handle turn change."""
        next_player_id = message.data.get("next_player_id", "")
        if self.game_state:
            self.game_state.current_player_id = next_player_id

        if self.on_turn_change:
            self.on_turn_change(next_player_id)

    def _on_game_over(self, message: GameMessage) -> None:
        """Handle game over."""
        winner_id = message.data.get("winner_id")
        if self.game_state:
            self.game_state.is_game_over = True
            self.game_state.winner_id = winner_id

        if self.on_game_over:
            self.on_game_over(winner_id)

    def _on_chat_message(self, message: GameMessage) -> None:
        """Handle chat message."""
        name = message.data.get("name", "Unknown")
        text = message.data.get("message", "")

        if self.on_chat_message:
            self.on_chat_message(name, text)

    def _on_error(self, message: GameMessage) -> None:
        """Handle error message."""
        error = message.data.get("error", "Unknown error")
        logger.error(f"Server error: {error}")

        if self.on_error:
            self.on_error(error)
