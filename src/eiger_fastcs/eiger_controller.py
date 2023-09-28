import asyncio
from dataclasses import dataclass
from typing import Any

from fastcs.attributes import AttrR, AttrRW, AttrW
from fastcs.connections import HTTPConnection, IPConnectionSettings
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Float, Int, String


@dataclass
class EigerHandler:
    name: str
    update_period: float = 0.2

    async def put(
        self,
        controller: "EigerController",
        attr: AttrW,
        value: Any,
    ) -> None:
        await controller.connection.put(self.name, value)

    async def update(
        self,
        controller: "EigerController",
        attr: AttrR,
    ) -> None:
        try:
            response = await controller.connection.get(self.name)
            await attr.set(response["value"])
        except Exception as e:
            print(e)


class EigerController(Controller):
    def __init__(self, settings: IPConnectionSettings) -> None:
        super().__init__()
        self._ip_settings = settings

        asyncio.run(self.initialise())

    async def connect(self) -> None:
        self.connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )

    async def initialise(self) -> None:
        # Adding extra loop prior to backend loop creating the Attributes to be PVs
        connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )
        detector_status = await connection.get("detector/api/1.8.0/status/keys")
        requests = [
            connection.get(f"detector/api/1.8.0/status/{item}")
            for item in detector_status["value"]
        ]
        values = await asyncio.gather(*requests)

        for i in range(len(detector_status["value"])):
            # FastCS Types
            match values[i]["value_type"]:
                case "float":
                    datatype = Float()
                case "int":
                    datatype = Int()
                case "bool":
                    datatype = Bool()
                case "str" | "datetime" | "State":
                    datatype = String()

            # append the names of criteria to the values list
            values[i] = {**{"name": detector_status["value"][i]}, **values[i]}

            # Set Attributes
            match values[i]["access_mode"]:
                case "rw":
                    setattr(
                        self,
                        values[i]["name"],
                        AttrRW(
                            datatype,
                            handler=EigerHandler(
                                f'detector/api/1.8.0/status/{values[i]["name"]}'
                            ),
                        ),
                    )

                case "r":
                    setattr(
                        self,
                        values[i]["name"],
                        AttrR(
                            datatype,
                            handler=EigerHandler(
                                f'detector/api/1.8.0/status/{values[i]["name"]}'
                            ),
                        ),
                    )
        await connection.close()

    async def close(self) -> None:
        await self.connection.close()
