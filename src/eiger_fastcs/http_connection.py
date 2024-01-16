from typing import Dict, Tuple

from aiohttp import ClientResponse, ClientSession


class HTTPConnection:
    def __init__(self, ip: str, port: int):
        self._session = ClientSession()
        self._ip = ip
        self._port = port

    def full_url(self, uri) -> str:
        return f"http://{self._ip}:{self._port}/{uri}"

    async def get(self, uri) -> str:
        async with self._session.get(self.full_url(uri)) as response:
            return await response.json()

    async def get_bytes(self, uri) -> Tuple[ClientResponse, bytes]:
        async with self._session.get(self.full_url(uri)) as response:
            return response, await response.read()

    async def put(self, uri, value):
        async with self._session.put(
            self.full_url(uri),
            json={"value": value},
            headers={"Content-Type": "application/json"},
        ) as response:
            return await response.json()

    async def close(self):
        await self._session.close()
