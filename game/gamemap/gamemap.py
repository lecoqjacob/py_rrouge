from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Iterator, List, Optional, Tuple

import numpy as np
import tcod
from numpy.typing import NDArray
from snecs.typedefs import EntityID

from constants import SHROUD
from game import ecs
from game.components.stats import CombatStats
from game.node import Node
from game.tiles import TileType

from .rect import Rect

if TYPE_CHECKING:
    import game.engine


MAX_ROOMS: int = 30
MIN_SIZE: int = 6
MAX_SIZE: int = 10


class GameMap(Node):
    rooms: List[Rect] = []
    rng: random.Random

    def __init__(self, engine: game.engine.Engine, width: int, height: int):
        super().__init__()

        self.engine = engine
        self.rng = engine.rng

        self.width, self.height = width, height
        self.tiles: NDArray[np.uint8] = np.zeros((width, height), dtype=np.uint8, order="F")

        self.memory: NDArray[Any] = np.full((width, height), fill_value=SHROUD, order="F")

        self.tile_content: List[List[EntityID]] = [[] for _ in range(self.width * self.height)]

        self.blocked: NDArray[np.bool_] = np.full((width, height), fill_value=False, order="F")
        self.visible = np.full((width, height), fill_value=False, order="F")  # Tiles the player can currently see
        self.explored = np.full((width, height), fill_value=False, order="F")  # Tiles the player has seen before

        self.generate_map()

    def idx(self, x: int, y: int) -> int:
        """Return the index of the tile at the given coordinates."""
        return (y * self.width) + x

    def __tunnel_between__(self, start: Tuple[int, int], end: Tuple[int, int]) -> Iterator[Tuple[int, int]]:
        """Return an L-shaped tunnel between these two points."""
        x1, y1 = start
        x2, y2 = end

        if self.rng.random() < 0.5:  # 50% chance.
            corner_x, corner_y = x2, y1  # Move horizontally, then vertically.
        else:
            corner_x, corner_y = x1, y2  # Move vertically, then horizontally.

        # Generate the coordinates for this tunnel.
        for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
            yield x, y
        for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
            yield x, y

    def generate_map(self) -> None:
        for _ in range(MAX_ROOMS):
            w = self.rng.randint(MIN_SIZE, MAX_SIZE)
            h = self.rng.randint(MIN_SIZE, MAX_SIZE)
            x = self.rng.randint(0, self.width - w - 1)
            y = self.rng.randint(0, self.height - h - 1)

            new_room = Rect(x, y, w, h)

            # Run through the other rooms and see if they intersect with this one.
            if any(new_room.intersects(other_room) for other_room in self.rooms):
                continue  # This room intersects, so go to the next attempt.
            # If there are no intersections then the room is valid.

            # Dig out this rooms inner area.
            self.tiles[new_room.inner] = TileType.FLOOR.value

            if len(self.rooms) != 0:
                # Dig out a tunnel between this room and the previous one.
                for x, y in self.__tunnel_between__(self.rooms[-1].center, new_room.center):
                    self.tiles[x, y] = TileType.FLOOR.value

            # Finally, append the new room to the list.
            self.rooms.append(new_room)

    def in_bounds(self, x: int, y: int) -> bool:
        """check if the given coordinates are within the bounds of the map"""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, x: int, y: int) -> bool:
        """Returns an entity that blocks the position at x,y if one exists, otherwise returns None."""
        return self.blocked[x, y]  # type: ignore

    def populate_blocked(self) -> None:
        for idx, tile in np.ndenumerate(self.tiles):
            self.blocked[idx[0], idx[1]] = tile == TileType.WALL.value

    def clear_content_index(self) -> None:
        """Clear the map of all tiles."""
        for content in self.tile_content:
            content.clear()

    def get_target_at_location(self, x: int, y: int) -> Optional[EntityID]:
        """Return the actor at the given location."""
        for entity in self.tile_content[self.idx(x, y)]:
            if ecs.try_entity_component(entity, CombatStats):
                return entity
        return None
