#! /usr/bin/env python
"""Multiplayer server for hosting online pool games."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Callable

import attrs

from pooltool.multiplayer.protocol import (
    GameMessage,
    GameState,
    MessageType,
    PlayerInfo,
    RoomInfo,
)

logger = logging.getLogger(__name__)


@attrs.define
class ConnectedClient:
    """Represents a connected client."""

    client_id: str
    writer: asyncio.StreamWriter
    reader: asyncio.StreamReader
    player_info: PlayerInfo
    room_id: str | None = None


class MultiplayerServer:
    """Server for hosting multiplayer pool games.

    This server manages client connections, game rooms, and message routing.
    It uses asyncio for non-blocking network operations.

    Example:
        >>> server = MultiplayerServer(host="0.0.0.0", port=7777)
        >>> asyncio.run(server.start())
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7777,
        max_rooms: int = 100,
    ):
        self.host = host
        self.port = port
        self.max_rooms = max_rooms

        self.clients: dict[str, ConnectedClient] = {}
        self.rooms: dict[str, RoomInfo] = {}
        self.game_states: dict[str, GameState] = {}

        self._server: asyncio.Server | None = None
        self._running = False

        self._message_handlers: dict[MessageType, Callable] = {
            MessageType.CONNECT: self._handle_connect,
            MessageType.DISCONNECT: self._handle_disconnect,
            MessageType.PING: self._handle_ping,
            MessageType.CREATE_ROOM: self._handle_create_room,
            MessageType.JOIN_ROOM: self._handle_join_room,
            MessageType.LEAVE_ROOM: self._handle_leave_room,
            MessageType.ROOM_LIST: self._handle_room_list,
            MessageType.PLAYER_READY: self._handle_player_ready,
            MessageType.GAME_START: self._handle_game_start_request,
            MessageType.SHOT_AIM: self._handle_shot_aim,
            MessageType.SHOT_EXECUTE: self._handle_shot_execute,
            MessageType.CHAT_MESSAGE: self._handle_chat_message,
        }

    async def start(self) -> None:
        """Start the server and begin accepting connections."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._running = True

        addr = self._server.sockets[0].getsockname()
        logger.info(f"Multiplayer server started on {addr[0]}:{addr[1]}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Stop the server and disconnect all clients."""
        self._running = False

        # Disconnect all clients
        for client in list(self.clients.values()):
            await self._disconnect_client(client.client_id)

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("Multiplayer server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a new client connection."""
        client_id = str(uuid.uuid4())
        addr = writer.get_extra_info("peername")
        logger.info(f"New connection from {addr}, assigned ID: {client_id}")

        # Create placeholder client entry
        player_info = PlayerInfo(
            player_id=client_id,
            name=f"Player_{client_id[:8]}",
            is_ready=False,
            is_host=False,
        )
        client = ConnectedClient(
            client_id=client_id,
            writer=writer,
            reader=reader,
            player_info=player_info,
        )
        self.clients[client_id] = client

        try:
            while self._running:
                data = await reader.readline()
                if not data:
                    break

                try:
                    message = GameMessage.from_json(data.decode().strip())
                    await self._process_message(client_id, message)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from {client_id}: {e}")
                except Exception as e:
                    logger.error(f"Error processing message from {client_id}: {e}")

        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            logger.info(f"Connection reset by {client_id}")
        finally:
            await self._disconnect_client(client_id)

    async def _process_message(self, client_id: str, message: GameMessage) -> None:
        """Process an incoming message from a client."""
        handler = self._message_handlers.get(message.msg_type)
        if handler:
            await handler(client_id, message)
        else:
            logger.warning(f"Unknown message type: {message.msg_type}")

    async def _send_message(self, client_id: str, message: GameMessage) -> None:
        """Send a message to a specific client."""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]
        try:
            data = message.to_json() + "\n"
            client.writer.write(data.encode())
            await client.writer.drain()
        except Exception as e:
            logger.error(f"Error sending to {client_id}: {e}")
            await self._disconnect_client(client_id)

    async def _broadcast_to_room(
        self,
        room_id: str,
        message: GameMessage,
        exclude_client: str | None = None,
    ) -> None:
        """Broadcast a message to all clients in a room."""
        if room_id not in self.rooms:
            return

        room = self.rooms[room_id]
        for player in room.players:
            if player.player_id != exclude_client:
                await self._send_message(player.player_id, message)

    async def _disconnect_client(self, client_id: str) -> None:
        """Disconnect a client and clean up their resources."""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]

        # Leave any room they're in
        if client.room_id:
            await self._leave_room(client_id, client.room_id)

        # Close connection
        try:
            client.writer.close()
            await client.writer.wait_closed()
        except Exception:
            pass

        del self.clients[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def _leave_room(self, client_id: str, room_id: str) -> None:
        """Remove a client from a room."""
        if room_id not in self.rooms:
            return

        room = self.rooms[room_id]
        room.players = [p for p in room.players if p.player_id != client_id]

        if client_id in self.clients:
            self.clients[client_id].room_id = None

        # If room is empty, delete it
        if not room.players:
            del self.rooms[room_id]
            if room_id in self.game_states:
                del self.game_states[room_id]
            logger.info(f"Room {room_id} deleted (empty)")
        else:
            # If host left, assign new host
            if room.host_id == client_id:
                room.host_id = room.players[0].player_id
                room.players[0].is_host = True

            # Notify remaining players
            update_msg = GameMessage(
                msg_type=MessageType.ROOM_UPDATE,
                sender_id="server",
                data={"room": attrs.asdict(room)},
                timestamp=time.time(),
            )
            await self._broadcast_to_room(room_id, update_msg)

    # Message handlers

    async def _handle_connect(self, client_id: str, message: GameMessage) -> None:
        """Handle client connection request."""
        name = message.data.get("name", f"Player_{client_id[:8]}")
        self.clients[client_id].player_info.name = name

        response = GameMessage(
            msg_type=MessageType.CONNECT,
            sender_id="server",
            data={
                "success": True,
                "player_id": client_id,
                "name": name,
            },
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)

    async def _handle_disconnect(self, client_id: str, message: GameMessage) -> None:
        """Handle client disconnect request."""
        await self._disconnect_client(client_id)

    async def _handle_ping(self, client_id: str, message: GameMessage) -> None:
        """Handle ping message."""
        response = GameMessage(
            msg_type=MessageType.PONG,
            sender_id="server",
            data={"client_time": message.data.get("time", 0)},
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)

    async def _handle_create_room(self, client_id: str, message: GameMessage) -> None:
        """Handle room creation request."""
        if len(self.rooms) >= self.max_rooms:
            error_msg = GameMessage(
                msg_type=MessageType.ERROR,
                sender_id="server",
                data={"error": "Server is full. Cannot create more rooms."},
                timestamp=time.time(),
            )
            await self._send_message(client_id, error_msg)
            return

        room_id = str(uuid.uuid4())[:8]
        room_name = message.data.get("room_name", f"Room {room_id}")
        game_type = message.data.get("game_type", "8ball")

        player_info = self.clients[client_id].player_info
        player_info.is_host = True
        player_info.is_ready = False

        room = RoomInfo(
            room_id=room_id,
            room_name=room_name,
            host_id=client_id,
            players=[player_info],
            game_type=game_type,
        )
        self.rooms[room_id] = room
        self.clients[client_id].room_id = room_id

        response = GameMessage(
            msg_type=MessageType.CREATE_ROOM,
            sender_id="server",
            data={"success": True, "room": attrs.asdict(room)},
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)
        logger.info(f"Room {room_id} created by {client_id}")

    async def _handle_join_room(self, client_id: str, message: GameMessage) -> None:
        """Handle room join request."""
        room_id = message.data.get("room_id")

        if not room_id or room_id not in self.rooms:
            error_msg = GameMessage(
                msg_type=MessageType.ERROR,
                sender_id="server",
                data={"error": "Room not found."},
                timestamp=time.time(),
            )
            await self._send_message(client_id, error_msg)
            return

        room = self.rooms[room_id]

        if room.is_full:
            error_msg = GameMessage(
                msg_type=MessageType.ERROR,
                sender_id="server",
                data={"error": "Room is full."},
                timestamp=time.time(),
            )
            await self._send_message(client_id, error_msg)
            return

        if room.is_started:
            error_msg = GameMessage(
                msg_type=MessageType.ERROR,
                sender_id="server",
                data={"error": "Game already in progress."},
                timestamp=time.time(),
            )
            await self._send_message(client_id, error_msg)
            return

        player_info = self.clients[client_id].player_info
        player_info.is_host = False
        player_info.is_ready = False
        room.players.append(player_info)
        self.clients[client_id].room_id = room_id

        # Notify the joining player
        response = GameMessage(
            msg_type=MessageType.JOIN_ROOM,
            sender_id="server",
            data={"success": True, "room": attrs.asdict(room)},
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)

        # Notify other players
        update_msg = GameMessage(
            msg_type=MessageType.ROOM_UPDATE,
            sender_id="server",
            data={"room": attrs.asdict(room)},
            timestamp=time.time(),
        )
        await self._broadcast_to_room(room_id, update_msg, exclude_client=client_id)

        logger.info(f"Player {client_id} joined room {room_id}")

    async def _handle_leave_room(self, client_id: str, message: GameMessage) -> None:
        """Handle room leave request."""
        client = self.clients.get(client_id)
        if client and client.room_id:
            await self._leave_room(client_id, client.room_id)

        response = GameMessage(
            msg_type=MessageType.LEAVE_ROOM,
            sender_id="server",
            data={"success": True},
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)

    async def _handle_room_list(self, client_id: str, message: GameMessage) -> None:
        """Handle room list request."""
        room_list = [
            attrs.asdict(room)
            for room in self.rooms.values()
            if not room.is_started and not room.is_full
        ]

        response = GameMessage(
            msg_type=MessageType.ROOM_LIST,
            sender_id="server",
            data={"rooms": room_list},
            timestamp=time.time(),
        )
        await self._send_message(client_id, response)

    async def _handle_player_ready(self, client_id: str, message: GameMessage) -> None:
        """Handle player ready toggle."""
        client = self.clients.get(client_id)
        if not client or not client.room_id:
            return

        room = self.rooms.get(client.room_id)
        if not room:
            return

        is_ready = message.data.get("is_ready", True)
        for player in room.players:
            if player.player_id == client_id:
                player.is_ready = is_ready
                break

        # Notify all players in room
        update_msg = GameMessage(
            msg_type=MessageType.ROOM_UPDATE,
            sender_id="server",
            data={"room": attrs.asdict(room)},
            timestamp=time.time(),
        )
        await self._broadcast_to_room(room.room_id, update_msg)

        # Don't auto-start - wait for host to click START GAME
        # (removed auto-start logic)

    async def _handle_game_start_request(self, client_id: str, message: GameMessage) -> None:
        """Handle game start request from host."""
        client = self.clients.get(client_id)
        if not client or not client.room_id:
            return

        room = self.rooms.get(client.room_id)
        if not room:
            return

        # Only host can start the game
        is_host = any(p.player_id == client_id and p.is_host for p in room.players)
        if not is_host:
            await self._send_error(client_id, "Only the host can start the game")
            return

        # Check all players are ready
        if not all(p.is_ready for p in room.players):
            await self._send_error(client_id, "All players must be ready")
            return

        # Need at least 2 players
        if len(room.players) < 2:
            await self._send_error(client_id, "Need at least 2 players")
            return

        await self._start_game(room.room_id)

    async def _start_game(self, room_id: str) -> None:
        """Start the game in a room."""
        room = self.rooms.get(room_id)
        if not room:
            return

        room.is_started = True

        # Initialize game state
        game_state = GameState(
            room_id=room_id,
            current_player_id=room.players[0].player_id,
            turn_number=0,
            shot_number=0,
            ball_positions={},
            ball_states={},
            cue_state=None,
            score={p.player_id: 0 for p in room.players},
        )
        self.game_states[room_id] = game_state

        # Notify all players
        start_msg = GameMessage(
            msg_type=MessageType.GAME_START,
            sender_id="server",
            data={
                "room": attrs.asdict(room),
                "game_state": attrs.asdict(game_state),
                "first_player_id": room.players[0].player_id,
            },
            timestamp=time.time(),
        )
        await self._broadcast_to_room(room_id, start_msg)
        logger.info(f"Game started in room {room_id}")

    async def _handle_shot_aim(self, client_id: str, message: GameMessage) -> None:
        """Handle shot aim update (for live preview)."""
        client = self.clients.get(client_id)
        if not client or not client.room_id:
            return

        room = self.rooms.get(client.room_id)
        game_state = self.game_states.get(client.room_id)
        if not room or not game_state:
            return

        # Only allow current player to aim
        if game_state.current_player_id != client_id:
            return

        # Broadcast aim update to other players
        aim_msg = GameMessage(
            msg_type=MessageType.SHOT_AIM,
            sender_id=client_id,
            data=message.data,
            timestamp=time.time(),
        )
        await self._broadcast_to_room(room.room_id, aim_msg, exclude_client=client_id)

    async def _handle_shot_execute(self, client_id: str, message: GameMessage) -> None:
        """Handle shot execution."""
        client = self.clients.get(client_id)
        if not client or not client.room_id:
            return

        room = self.rooms.get(client.room_id)
        game_state = self.game_states.get(client.room_id)
        if not room or not game_state:
            return

        # Only allow current player to shoot
        if game_state.current_player_id != client_id:
            return

        # Broadcast shot to all players
        shot_msg = GameMessage(
            msg_type=MessageType.SHOT_EXECUTE,
            sender_id=client_id,
            data=message.data,
            timestamp=time.time(),
        )
        await self._broadcast_to_room(room.room_id, shot_msg)

    async def _handle_chat_message(self, client_id: str, message: GameMessage) -> None:
        """Handle chat message."""
        client = self.clients.get(client_id)
        if not client or not client.room_id:
            return

        chat_msg = GameMessage(
            msg_type=MessageType.CHAT_MESSAGE,
            sender_id=client_id,
            data={
                "name": client.player_info.name,
                "message": message.data.get("message", ""),
            },
            timestamp=time.time(),
        )
        await self._broadcast_to_room(client.room_id, chat_msg)


def run_server(host: str = "0.0.0.0", port: int = 7777) -> None:
    """Run the multiplayer server."""
    logging.basicConfig(level=logging.INFO)
    server = MultiplayerServer(host=host, port=port)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")


if __name__ == "__main__":
    run_server()
