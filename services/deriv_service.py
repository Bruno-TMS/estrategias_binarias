import asyncio
import websockets
from datetime import datetime
from deriv_api import DerivAPI, APIError

from app.core.config import settings


class DerivService:
    def __init__(self):
        self.app_id = settings.deriv_app_id
        self.token = settings.deriv_token

        self.connection = None
        self.api = None
        self.connected_at = None

    @property
    def is_alive(self) -> bool:
        return self.connection is not None and not self.connection.closed

    async def connect(self):
        if self.is_alive:
            return await self.api.authorize(self.token)

        try:
            self.connection = await websockets.connect(
                f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
            )

            self.api = DerivAPI(connection=self.connection)

            response = await asyncio.wait_for(
                self.api.authorize(self.token),
                timeout=5
            )

            self.connected_at = datetime.utcnow()
            return response

        except APIError as e:
            self._reset()
            raise RuntimeError(f"Deriv API error: {e}")

        except Exception as e:
            self._reset()
            raise RuntimeError(f"Connection error: {e}")

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
        self._reset()

    async def send(self, payload: dict):
        if not self.is_alive:
            raise RuntimeError("Not connected")

        try:
            return await self.api.send(payload)

        except APIError as e:
            self._reset()
            raise RuntimeError(f"API error: {e}")

        except Exception as e:
            self._reset()
            raise RuntimeError(f"Send error: {e}")

    def _reset(self):
        self.connection = None
        self.api = None
        self.connected_at = None