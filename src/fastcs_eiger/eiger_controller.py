import asyncio
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Literal

import numpy as np
from fastcs.attributes import Attribute, AttrR, AttrRW, AttrW, Handler
from fastcs.controller import BaseController, Controller, SubController
from fastcs.datatypes import Bool, Float, String
from fastcs.wrappers import command, scan
from PIL import Image

from fastcs_eiger.eiger_parameter import (
    EIGER_PARAMETER_MODES,
    EIGER_PARAMETER_SUBSYSTEMS,
    EigerParameter,
    EigerParameterResponse,
    key_to_attribute_name,
)
from fastcs_eiger.http_connection import HTTPConnection, HTTPRequestError

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}

# Keys to be ignored when introspecting the detector to create parameters
IGNORED_KEYS = [
    # Big arrays
    "countrate_correction_table",
    "pixel_mask",
    "threshold/1/pixel_mask",
    "threshold/2/pixel_mask",
    "flatfield",
    "threshold/1/flatfield",
    "threshold/2/flatfield",
    # Deprecated
    "board_000/th0_humidity",
    "board_000/th0_temp",
    # TODO: Value is [value, max], rather than using max metadata
    "buffer_fill_level",
    # TODO: Handle array values
    "detector_orientation",
    "detector_translation",
    # TODO: Is it a bad idea to include these?
    "test_image_mode",
    "test_image_value",
]

# Parameters that are in the API but missing from keys
MISSING_KEYS: dict[str, dict[str, list[str]]] = {
    "detector": {"status": ["error"], "config": ["wavelength"]},
    "monitor": {"status": [], "config": []},
    "stream": {"status": ["error"], "config": []},
}


def command_uri(key: str) -> str:
    return f"detector/api/1.8.0/command/{key}"


def detector_command(fn) -> Any:
    return command(group="DetectorCommand")(fn)


@dataclass
class EigerHandler:
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Handler uses uri of detector to collect data for PVs
    """

    uri: str
    update_period: float | None = 0.2

    def _handle_params_to_update(self, parameters: list[str]):
        update_now = []
        update_later = []
        if not parameters:  # no response, queue update for the parameter we just put to
            update_later.append(self.uri.split("/", 4)[-1])
        else:
            for parameter in parameters:
                if parameter == "difference_mode":
                    # handling Eiger API inconsistency
                    parameter = "threshold/difference/mode"
                if parameter in FETCH_BEFORE_RETURNING:
                    update_now.append(parameter)
                else:
                    update_later.append(parameter)
        return update_now, update_later

    async def put(
        self, controller: "EigerSubsystemController", attr: AttrW, value: Any
    ) -> None:
        parameters_to_update = await controller.connection.put(self.uri, value)
        update_now, update_later = self._handle_params_to_update(parameters_to_update)
        await controller.update_now(update_now)
        print(
            f"Queueing updates for parameters after setting {self.uri}: {update_later}"
        )
        await controller.queue_update(update_later)

    async def update(self, controller: "EigerSubsystemController", attr: AttrR) -> None:
        try:
            response = await controller.connection.get(self.uri)
            value = response["value"]
            if isinstance(value, list) and all(
                isinstance(s, str) for s in value
            ):  # error is a list of strings
                value = ", ".join(value)
            await attr.set(value)
        except Exception as e:
            print(f"Failed to get {self.uri}:\n{e.__class__.__name__} {e}")


class EigerConfigHandler(EigerHandler):
    """Handler for config parameters that are polled once on startup."""

    first_poll_complete: bool = False

    async def update(self, controller: "EigerSubsystemController", attr: AttrR) -> None:
        # Only poll once on startup
        if not self.first_poll_complete:
            await super().update(controller, attr)
            if isinstance(attr, AttrRW):
                # Sync readback value to demand
                await attr.update_display_without_process(attr.get())

            self.first_poll_complete = True

    async def config_update(
        self, controller: "EigerSubsystemController", attr: AttrR
    ) -> None:
        await super().update(controller, attr)


@dataclass
class LogicHandler(Handler):
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Used for dynamically created attributes that are added for additional logic
    """

    async def put(self, controller: BaseController, attr: AttrW, value: Any) -> None:
        assert isinstance(attr, AttrR)  # AttrW does not implement set
        await attr.set(value)


EIGER_HANDLERS: dict[str, type[EigerHandler]] = {
    "status": EigerHandler,
    "config": EigerConfigHandler,
}


class EigerController(Controller):
    """
    Controller Class for Eiger Detector

    Used for dynamic creation of variables useed in logic of the EigerFastCS backend.
    Sets up all connections with the Simplon API to send and receive information
    """

    # Internal Attribute
    stale_parameters = AttrR(Bool())

    def __init__(self, ip: str, port: int) -> None:
        super().__init__()
        self._ip = ip
        self._port = port
        self.connection = HTTPConnection(self._ip, self._port)
        # Parameter update logic
        self._parameter_update_lock = asyncio.Lock()
        self.queue = asyncio.Queue()

    async def initialise(self) -> None:
        """Create attributes by introspecting detector.

        The detector will be initialized if it is not already.

        """
        self.connection.open()

        try:
            for subsystem in EIGER_PARAMETER_SUBSYSTEMS:
                match subsystem:
                    case "detector":
                        controller = EigerDetectorController(
                            self.connection,
                            self.queue_subsystem_update,
                        )
                        # detector subsystem initialises first
                        # Check current state of detector_state to see
                        # if initializing is required.
                        state_val = await self.connection.get(
                            "detector/api/1.8.0/status/state"
                        )
                        if state_val["value"] == "na":
                            print("Initializing Detector")
                            # send initialize command to detector
                            await controller.initialize()
                    case "monitor":
                        controller = EigerMonitorController(
                            self.connection,
                            self.queue_subsystem_update,
                        )
                    case "stream":
                        controller = EigerStreamController(
                            self.connection,
                            self.queue_subsystem_update,
                        )
                    case _:
                        raise NotImplementedError(
                            f"No subcontroller implemented for subsystem {subsystem}"
                        )
                self.register_sub_controller(subsystem.capitalize(), controller)
                await controller.initialise()

        except HTTPRequestError:
            print("\nAn HTTP request failed while introspecting detector:\n")
            raise

    def get_subsystem_controllers(self) -> list["EigerSubsystemController"]:
        return [
            controller
            for controller in self.get_sub_controllers().values()
            if isinstance(controller, EigerSubsystemController)
        ]

    @scan(0.1)
    async def update(self):
        """Periodically check for parameters that need updating from the detector."""
        if not self.queue.empty():
            coros: list[Coroutine] = []
            async with self._parameter_update_lock:
                while not self.queue.empty():
                    coros.append(await self.queue.get())
            await asyncio.gather(*coros)
        await self.stale_parameters.set(not self.queue.empty())

    async def queue_subsystem_update(self, coros: list[Coroutine]):
        if coros:
            await self.stale_parameters.set(True)
            async with self._parameter_update_lock:
                for coro in coros:
                    await self.queue.put(coro)


class EigerSubsystemController(SubController):
    _subsystem: Literal["detector", "stream", "monitor"]

    def __init__(
        self,
        connection: HTTPConnection,
        queue_subsystem_update: Callable[[list[Coroutine]], Coroutine],
    ):
        self.connection = connection
        self._queue_subsystem_update = queue_subsystem_update
        super().__init__()

    async def _introspect_detector_subsystem(self) -> list[EigerParameter]:
        parameters = []
        for mode in EIGER_PARAMETER_MODES:
            subsystem_keys = [
                parameter
                for parameter in await self.connection.get(
                    f"{self._subsystem}/api/1.8.0/{mode}/keys"
                )
                if parameter not in IGNORED_KEYS
            ] + MISSING_KEYS[self._subsystem][mode]
            requests = [
                self.connection.get(f"{self._subsystem}/api/1.8.0/{mode}/{key}")
                for key in subsystem_keys
            ]
            responses = await asyncio.gather(*requests)

            parameters.extend(
                [
                    EigerParameter(
                        key=key,
                        subsystem=self._subsystem,
                        mode=mode,
                        response=EigerParameterResponse.model_validate(response),
                    )
                    for key, response in zip(subsystem_keys, responses, strict=False)
                ]
            )

        return parameters

    async def initialise(self) -> None:
        parameters = await self._introspect_detector_subsystem()
        attributes = self._create_attributes(parameters)

        for name, attribute in attributes.items():
            self.attributes[name] = attribute

    @classmethod
    def _group(cls, parameter: EigerParameter):
        if "/" in parameter.key:
            group_parts = parameter.key.split("/")[:-1]
            # e.g. "threshold/difference/mode" -> ThresholdDifference
            return "".join(list(map(str.capitalize, group_parts)))
        return f"{parameter.subsystem.capitalize()}{parameter.mode.capitalize()}"

    @classmethod
    def _create_attributes(cls, parameters: list[EigerParameter]):
        """Create ``Attribute``s from ``EigerParameter``s.

        Args:
            parameters: ``EigerParameter``s to create ``Attributes`` from

        """
        attributes: dict[str, Attribute] = {}
        for parameter in parameters:
            group = cls._group(parameter)
            match parameter.response.access_mode:
                case "r":
                    attributes[parameter.attribute_name] = AttrR(
                        parameter.response.fastcs_datatype,
                        handler=EIGER_HANDLERS[parameter.mode](parameter.uri),
                        group=group,
                    )
                case "rw":
                    attributes[parameter.attribute_name] = AttrRW(
                        parameter.response.fastcs_datatype,
                        handler=EIGER_HANDLERS[parameter.mode](parameter.uri),
                        group=group,
                        allowed_values=parameter.response.allowed_values,
                    )
        return attributes

    async def queue_update(self, parameters: Iterable[str]):
        """Add the given parameters to the list of parameters to update.

        Args:
            parameters: Parameters to be updated

        """
        if not parameters:
            return
        coros: list[Coroutine] = self._get_update_coros_for_parameters(parameters)
        await self._queue_subsystem_update(coros)

    async def update_now(self, parameters: Iterable[str]):
        """Update the given parameters immediately without queueing or setting the
        top controller's stale_parameters ``Attribute``.
        Args:
            parameters: Parameters to be updated immediately

        """
        if parameters:
            print(
                f"Attempting to update {parameters} without setting controller to stale"
            )
            coros = self._get_update_coros_for_parameters(parameters)
            await asyncio.gather(*coros)

    def _get_update_coros_for_parameters(
        self, parameters: Iterable[str]
    ) -> list[Coroutine]:
        coros: list[Coroutine] = []
        for parameter in parameters:
            attr_name = key_to_attribute_name(parameter)
            match self.attributes.get(attr_name, None):
                case AttrR(updater=EigerConfigHandler() as updater) as attr:
                    coros.append(updater.config_update(self, attr))
                case _ as attr:
                    if parameter not in IGNORED_KEYS:
                        print(
                            f"Failed to find updater for {parameter}"
                            f"with attribute {attr}"
                        )
        return coros


class EigerDetectorController(EigerSubsystemController):
    _subsystem = "detector"

    # Detector parameters to use in internal logic
    trigger_mode = AttrRW(String())  # TODO: Include URI and validate type from API
    trigger_exposure = AttrRW(Float(), handler=LogicHandler())

    @detector_command
    async def initialize(self):
        await self.connection.put(command_uri("initialize"))

    @detector_command
    async def arm(self):
        await self.connection.put(command_uri("arm"))

    @detector_command
    async def trigger(self):
        match self.trigger_mode.get(), self.trigger_exposure.get():
            case ("inte", exposure) if exposure > 0.0:
                await self.connection.put(command_uri("trigger"), exposure)
            case ("ints" | "inte", _):
                await self.connection.put(command_uri("trigger"))
            case _:
                raise RuntimeError("Can only do soft trigger in 'ints' or 'inte' mode")

    @detector_command
    async def disarm(self):
        await self.connection.put(command_uri("disarm"))

    @detector_command
    async def abort(self):
        await self.connection.put(command_uri("abort"))

    @detector_command
    async def cancel(self):
        await self.connection.put(command_uri("cancel"))


class EigerMonitorController(EigerSubsystemController):
    _subsystem = "monitor"

    @scan(1)
    async def handle_monitor(self):
        """Poll monitor images to display."""
        response, image_bytes = await self.connection.get_bytes(
            "monitor/api/1.8.0/images/next"
        )
        if response.status != 200:
            return
        else:
            image = Image.open(BytesIO(image_bytes))

            # TODO: Populate waveform PV to display as image, once supported in PVI
            print(np.array(image))


class EigerStreamController(EigerSubsystemController):
    _subsystem = "stream"
