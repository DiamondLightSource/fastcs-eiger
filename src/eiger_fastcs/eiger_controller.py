import asyncio
from dataclasses import dataclass
from io import BytesIO
from itertools import product
from typing import Any, Coroutine, Literal, Type

import numpy as np
from attr import Attribute
from fastcs.attributes import AttrR, AttrRW, AttrW
from fastcs.controller import Controller
from fastcs.datatypes import Bool, Float, Int, String
from fastcs.wrappers import command, scan
from PIL import Image

from eiger_fastcs.http_connection import HTTPConnection, HTTPRequestError

IGNORED_PARAMETERS = [
    "countrate_correction_table",
    "pixel_mask",
    "threshold/1/pixel_mask",
    "threshold/2/pixel_mask",
    "flatfield",
    "threshold/1/flatfield",
    "threshold/2/flatfield",
    "board_000/th0_humidity",
    "board_000/th0_temp",
    "buffer_fill_level",  # TODO: Value is [value, max], rather than using max metadata
    "detector_orientation",  # TODO: Handle array values
    "detector_translation",
    "total_flux",  # TODO: Undocumented and value is `None`
]


def detector_command(fn) -> Any:
    return command(group="DetectorCommand")(fn)


@dataclass
class EigerHandler:
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Handler uses uri of detector to collect data for PVs
    """

    name: str
    update_period: float = 0.2

    async def put(self, controller: "EigerController", _: AttrW, value: Any) -> None:
        parameters_to_update = await controller._connection.put(self.name, value)
        if not parameters_to_update:
            parameters_to_update = [self.name.split("/")[-1]]
            print(f"Manually fetching parameter {parameters_to_update}")
        else:
            print(
                f"Fetching parameters after setting {self.name}: {parameters_to_update}"
            )

        await controller.queue_update(parameters_to_update)

    async def update(self, controller: "EigerController", attr: AttrR) -> None:
        try:
            response = await controller._connection.get(self.name)
            await attr.set(response["value"])
        except Exception as e:
            print(f"Failed to get {self.name}:\n{e.__class__.__name__} {e}")


class EigerConfigHandler(EigerHandler):
    """Handler for config parameters that are polled once on startup."""

    first_poll_complete: bool = False

    async def update(self, controller: "EigerController", attr: AttrR) -> None:
        # Only poll once on startup
        if not self.first_poll_complete:
            await super().update(controller, attr)
            if isinstance(attr, AttrRW):
                # Sync readback value to demand
                await attr._write_display_callback(attr.get())

            self.first_poll_complete = True

    async def config_update(self, controller: "EigerController", attr: AttrR) -> None:
        await super().update(controller, attr)


@dataclass
class LogicHandler:
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Used for dynamically created attributes that are added for additional logic
    """

    async def put(self, _: "EigerController", attr: AttrW, value: Any) -> None:
        await attr.set(value)


EIGER_HANDLERS: dict[str, Type[EigerHandler]] = {
    "status": EigerHandler,
    "config": EigerConfigHandler,
}


@dataclass
class EigerParameter:
    key: str
    """Last section of URI within a subsystem/mode."""
    subsystem: Literal["detector", "stream", "monitor"]
    """Subsystem within detector API."""
    mode: Literal["status", "config"]
    """Mode of parameter within subsystem."""
    response: dict[str, Any]
    """JSON response from GET of parameter."""
    has_unique_key: bool = True
    """Whether this parameter has a unique key across all subsystems."""

    @property
    def name(self) -> str:
        """Unique name of parameter across all subsystems."""
        return self.key if self.has_unique_key else f"{self.subsystem}_{self.key}"

    @property
    def uri(self) -> str:
        """Full URI for HTTP requests."""
        return f"{self.subsystem}/api/1.8.0/{self.mode}/{self.key}"


EIGER_PARAMETER_SUBSYSTEMS = EigerParameter.__annotations__["subsystem"].__args__
EIGER_PARAMETER_MODES = EigerParameter.__annotations__["mode"].__args__


class EigerController(Controller):
    """
    Controller Class for Eiger Detector

    Used for dynamic creation of variables useed in logic of the EigerFastCS backend.
    Sets up all connections with the Simplon API to send and receive information
    """

    # Detector Parameters
    ntrigger = AttrRW(Int())  # TODO: Include URI and validate type from API

    # Logic Parameters
    manual_trigger = AttrRW(Bool(), handler=LogicHandler())
    stale_parameters = AttrR(Bool())

    def __init__(self, ip: str, port: int) -> None:
        super().__init__()
        self._ip = ip
        self._port = port
        self._connection = HTTPConnection(self._ip, self._port)

        # Parameter update logic
        self._parameter_updates: set[str] = set()
        self._parameter_update_lock = asyncio.Lock()

        # Initialize parameters from hardware - run on ephemeral asyncio loop
        # TODO: Make the backend asyncio loop available earlier
        asyncio.run(self.initialise())

    async def connect(self) -> None:
        """Reopen connection on backend asyncio loop"""
        self._connection.open()

    async def initialise(self) -> None:
        """Create attributes by introspecting detector.

        The detector will be initialized if it is not already.

        """
        self._connection.open()

        try:
            parameters = await self._introspect_detector()
        except HTTPRequestError:
            print("\nAn HTTP request failed while introspecting detector:\n")
            raise

        attributes = self._create_attributes(parameters)

        for name, attribute in attributes.items():
            setattr(self, name, attribute)

        # Check current state of detector_state to see if initializing is required.
        state_val = await self._connection.get(self.detector_state.updater.name)
        if state_val["value"] == "na":
            print("Initializing Detector")
            await self._connection.put("detector/api/1.8.0/command/initialize", "")

        await self._connection.close()

    async def _introspect_detector(self) -> list[EigerParameter]:
        parameters = []
        for subsystem, mode in product(
            EIGER_PARAMETER_SUBSYSTEMS, EIGER_PARAMETER_MODES
        ):
            subsystem_keys = [
                parameter
                for parameter in await self._connection.get(
                    f"{subsystem}/api/1.8.0/{mode}/keys"
                )
                if parameter not in IGNORED_PARAMETERS
            ]
            requests = [
                self._connection.get(f"{subsystem}/api/1.8.0/{mode}/{key}")
                for key in subsystem_keys
            ]
            responses = await asyncio.gather(*requests)

            parameters.extend(
                [
                    EigerParameter(
                        key=key, subsystem=subsystem, mode=mode, response=response
                    )
                    for key, response in zip(subsystem_keys, responses)
                ]
            )

        return parameters

    def _create_attributes(self, parameters: list[EigerParameter]):
        """Create ``Attribute``s from ``EigerParameter``s.

        Args:
            parameters: ``EigerParameter``s to create ``Attributes`` from

        """
        self._tag_key_clashes(parameters)

        attributes: dict[str, Attribute] = {}
        for parameter in parameters:
            group = f"{parameter.subsystem.capitalize()}{parameter.mode.capitalize()}"
            match parameter.response["value_type"]:
                case "float":
                    datatype = Float()
                case "int" | "uint":
                    datatype = Int()
                case "bool":
                    datatype = Bool()
                case "string" | "datetime" | "State" | "string[]":
                    datatype = String()
                case _:
                    print(f"Failed to handle {parameter}")

            # Flatten nested uri keys - e.g. threshold/1/mode -> threshold_1_mode
            attribute_name = parameter.name.replace("/", "_")

            match parameter.response["access_mode"]:
                case "r":
                    attributes[attribute_name] = AttrR(
                        datatype,
                        handler=EIGER_HANDLERS[parameter.mode](parameter.uri),
                        group=group,
                    )
                case "rw":
                    attributes[attribute_name] = AttrRW(
                        datatype,
                        handler=EIGER_HANDLERS[parameter.mode](parameter.uri),
                        group=group,
                    )

        return attributes

    @staticmethod
    def _tag_key_clashes(parameters: list[EigerParameter]):
        """Find key clashes between subsystems and tag parameters to use extended name.

        Modifies list of parameters in place.

        Args:
            parameters: Parameters to search

        """
        for idx, parameter in enumerate(parameters):
            for other in parameters[idx + 1 :]:
                if parameter.key == other.key:
                    parameter.has_unique_key = False
                    other.has_unique_key = False
                    break

    async def close(self) -> None:
        """Closing HTTP connection with device"""
        await self._connection.close()

    async def arm(self):
        """Arming Detector called by the start acquisition button"""
        await self._connection.put("detector/api/1.8.0/command/arm", "")

    @detector_command
    async def initialize(self):
        """Command to initialize Detector - will create a PVI button"""
        await self._connection.put("detector/api/1.8.0/command/initialize", "")

    @detector_command
    async def disarm(self):
        """Command to disarm Detector - will create a PVI button"""
        await self._connection.put("detector/api/1.8.0/command/disarm", "")

    @detector_command
    async def abort(self):
        """Command to abort any tasks Detector - will create a PVI button"""
        await self._connection.put("detector/api/1.8.0/command/abort", "")

    @detector_command
    async def cancel(self):
        """Command to cancel readings from Detector - will create a PVI button"""
        await self._connection.put("detector/api/1.8.0/command/cancel", "")

    @detector_command
    async def trigger(self):
        """
        Command to trigger Detector when manual triggering is switched on.
        will create a PVI button
        """
        await self._connection.put("detector/api/1.8.0/command/trigger", "")

    @detector_command
    async def start_acquisition(self):
        """
        Command to start acquiring detector image.

        Iterates through arming and triggering the detector if manual trigger off.
        If manual triggers are on, it arms the detector, ready for triggering.
        """
        await self.arm()
        # Current functionality is for ints triggering and multiple ntriggers for
        # automatic triggering
        if not self.manual_trigger.get():
            for _ in range(self.ntrigger.get()):
                await self.trigger()

    async def queue_update(self, parameters: list[str]):
        """Add the given parameters to the list of parameters to update.

        Args:
            parameters: Parameters to be updated

        """
        async with self._parameter_update_lock:
            for parameter in parameters:
                self._parameter_updates.add(parameter)

            await self.stale_parameters.set(True)

    @scan(0.1)
    async def update(self):
        """Periodically check for parameters that need updating from the detector."""
        if not self._parameter_updates:
            if self.stale_parameters.get():
                await self.stale_parameters.set(False)

            return

        # Take a copy of the current parameters and clear. Parameters may be repopulated
        # during this call and need to be updated again immediately.
        async with self._parameter_update_lock:
            parameters = self._parameter_updates.copy()
            self._parameter_updates.clear()

        # Release lock while fetching parameters - this may be slow
        parameter_updates: list[Coroutine] = []
        for parameter in parameters:
            match getattr(self, parameter):
                # TODO: mypy doesn't understand AttrR as a type for some reason:
                # `error: Expected type in class pattern; found "Any"  [misc]`
                case AttrR(updater=EigerConfigHandler() as updater) as attr:  # type: ignore [misc]
                    parameter_updates.append(updater.config_update(self, attr))
                case _:
                    print(f"Failed to handle update for {parameter}")

        await asyncio.gather(*parameter_updates)

    @scan(1)
    async def handle_monitor(self):
        """Poll monitor images to display."""
        response, image_bytes = await self._connection.get_bytes(
            "monitor/api/1.8.0/images/next"
        )
        if response.status != 200:
            return
        else:
            image = Image.open(BytesIO(image_bytes))

            # TODO: Populate waveform PV to display as image, once supported in PVI
            print(np.array(image))
