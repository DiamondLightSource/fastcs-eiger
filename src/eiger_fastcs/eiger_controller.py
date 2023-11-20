import asyncio
from dataclasses import dataclass
from typing import Any

from attr import Attribute
from fastcs.attributes import AttrR, AttrRW, AttrW
from fastcs.connections import HTTPConnection, IPConnectionSettings
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Float, Int, String
from fastcs.wrappers import command


@dataclass
class EigerHandler:
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Handler uses uri of detector to collect data for PVs
    """

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
            # TODO: Async sleep?
            response = await controller.connection.get(self.name)
            await attr.set(response["value"])
        except Exception as e:
            print(f"update loop failed:{e}")


@dataclass
class LogicHandler:
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Used for dynamically created attributes that are added for additional logic
    """

    name: str

    async def put(
        self,
        controller: "EigerController",
        attr: AttrW,
        value: Any,
    ) -> None:
        await attr.set(value)


class EigerController(Controller):
    """
    Controller Class for Eiger Detector

    Used for dynamic creation of variables useed in logic of the EigerFastCS backend.
    Sets up all connections with the Simplon API to send and receive information
    """

    manual_trigger = AttrRW(
        Bool(),
        handler=LogicHandler("manual trigger"),
    )

    def __init__(self, settings: IPConnectionSettings) -> None:
        super().__init__()
        self._ip_settings = settings

        asyncio.run(self.initialise())

    async def connect(self) -> None:
        """Connection settigns with Eiger Detector using HTTP"""
        self.connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )

    async def initialise(self) -> None:
        """
        Method to create all PVs from the tickit-devices simulator/device at startup
        Initialises the detector at the end of PV creation

        Where to find PVs created in tickit-devices.
            detector-status: eiger_status.py
            detector-config: eiger_settings.py
            stream-status: stream_status.py
            stream-config: stream_config.py
            monitor-status: monitor_status.py
            monitor-config: monitor_config.py

        Populates all PVs set in simulator/device in attributes dictionary
        (Name of PV, FastCS Attribute) after checking for any clashes with
        other subsystems and if the PV has already been created in the self
        dictionary keys.

        Initialises detector on startup.
        """
        # Adding extra loop prior to backend loop creating the Attributes to be PVs
        connection = HTTPConnection(
            self._ip_settings, headers={"Content-Type": "application/json"}
        )
        subsystems = ["detector", "stream", "monitor"]
        modes = ["status", "config"]
        pv_clashes: dict[str, str] = {}
        attributes: dict[str, Attribute] = {}

        for index, subsystem in enumerate(subsystems):
            for mode in modes:
                response = await connection.get(f"{subsystem}/api/1.8.0/{mode}/keys")
                subsystem_parameters = response["value"]
                requests = [
                    connection.get(f"{subsystem}/api/1.8.0/{mode}/{item}")
                    for item in subsystem_parameters
                ]
                values = await asyncio.gather(*requests)

                for parameter_name, parameter in zip(subsystem_parameters, values):
                    # FastCS Types
                    match parameter["value_type"]:
                        case "float":
                            datatype = Float()
                        case "int":
                            datatype = Int()
                        case "bool":
                            datatype = Bool()
                        case "string" | "datetime" | "State" | "string[]":
                            datatype = String()
                        case _:
                            print(f"Could not process {parameter_name}")

                    # finding appropriate naming to ensure repeats are not ovewritten
                    # and ensuring that PV has not been created already
                    if (
                        parameter_name in list(attributes.keys())
                        and parameter_name not in self.__dict__.keys()
                    ):
                        # Adding original instance of the duplicate into dictionary to
                        # rename original instance in attributes later
                        if parameter_name not in list(pv_clashes.keys()):
                            pv_clashes[
                                parameter_name
                            ] = f"{subsystems[index-1]}_{parameter_name}"
                        name = f"{subsystem}_{parameter_name}"
                    else:
                        name = parameter_name

                    # mapping attributes using access mode metadata
                    match parameter["access_mode"]:
                        case "r":
                            attributes[name] = AttrR(
                                datatype,
                                handler=EigerHandler(
                                    f"{subsystem}/api/1.8.0/{mode}/{parameter_name}"
                                ),
                            )
                        case "rw":
                            attributes[name] = AttrRW(
                                datatype,
                                handler=EigerHandler(
                                    f"{subsystem}/api/1.8.0/{mode}/{parameter_name}"
                                ),
                            )

        # Renaming original instance of duplicate in Attribute
        # Removing unique names already created
        for clash_name, unique_name in pv_clashes.items():
            if unique_name in self.__dict__.keys():
                del attributes[clash_name]
                print(
                    f"{unique_name} was already created before, "
                    f"{clash_name} is being deleted"
                )

            else:
                attributes[unique_name] = attributes.pop(clash_name)
                print(f"Replacing the repeat,{clash_name}, with {unique_name}")

        for name, attribute in attributes.items():
            setattr(self, name, attribute)

        # Check current state of detector_state to see if initializing is required.
        state_val = await connection.get(self.detector_state.updater.name)
        if state_val["value"] == "na":
            print("Initializing Detector")
            await connection.put("detector/api/1.8.0/command/initialize", "")

        await connection.close()

    async def close(self) -> None:
        """Closing HTTP connection with device"""
        await self.connection.close()

    async def arm(self):
        """Arming Detector called by the start acquisition button"""
        await self.connection.put("detector/api/1.8.0/command/arm", "")

    @command
    async def initialize(self):
        """Command to initialize Detector - will create a PVI button"""
        await self.connection.put("detector/api/1.8.0/command/initialize", "")

    @command
    async def disarm(self):
        """Command to disarm Detector - will create a PVI button"""
        await self.connection.put("detector/api/1.8.0/command/disarm", "")

    @command
    async def abort(self):
        """Command to abort any tasks Detector - will create a PVI button"""
        await self.connection.put("detector/api/1.8.0/command/abort", "")

    @command
    async def cancel(self):
        """Command to cancel readings from Detector - will create a PVI button"""
        await self.connection.put("detector/api/1.8.0/command/cancel", "")

    @command
    async def trigger(self):
        """
        Command to trigger Detector when manual triggering is switched on.
        will create a PVI button
        """
        await self.connection.put("detector/api/1.8.0/command/trigger", "")

    @command
    async def start_acquisition(self):
        """
        Command to start acquiring detector image.

        Iterates through arming and triggering the detector if manual trigger off.
        If manual triggers are on, it arms the detector, ready for triggering.
        """
        await self.arm()
        # Current functionality is for ints triggering and multiple ntriggers for
        # automatic triggering
        if not self.manual_trigger._value:
            for i in range(self.ntrigger._value):
                print(f"Acquisition number: {i+1}")
                await self.trigger()
