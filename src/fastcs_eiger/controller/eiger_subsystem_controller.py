import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Literal

from fastcs2 import AttributeR, AttributeRW, Controller

from fastcs_eiger.attribute_io import EIGER_IO_REFS
from fastcs_eiger.attribute_io.eiger_attribute_io import EigerAttributeIO
from fastcs_eiger.attribute_io.eiger_config_attribute_io import EigerConfigAttributeIO
from fastcs_eiger.attribute_io.internal_attribute_io import (
    InternalAttributeIO,
    InternalAttributeIORef,
)
from fastcs_eiger.eiger_parameter import (
    EIGER_PARAMETER_MODES,
    EigerParameter,
    EigerParameterResponse,
    key_to_attribute_name,
)
from fastcs_eiger.http_connection import HTTPConnection

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

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}


class EigerSubsystemController(Controller):
    _subsystem: Literal["detector", "stream", "monitor"]
    stale_parameters = AttributeR("stale_parameters", bool, InternalAttributeIORef())

    def __init__(self, ip: str, port: int) -> None:
        self._ip = ip
        self._port = port
        self.connection = HTTPConnection(self._ip, self._port)
        # Parameter update logic
        self._parameter_update_lock = asyncio.Lock()
        self.queue = asyncio.Queue()

        super().__init__(
            [
                InternalAttributeIO(),
                EigerAttributeIO(self.connection, self._handle_parameter_update),
                EigerConfigAttributeIO(self.connection, self._handle_parameter_update),
            ]
        )

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
        self.connection.open()

        parameters = await self._introspect_detector_subsystem()
        attributes = self._create_attributes(parameters)

        for name, attribute in attributes.items():
            self.add_attribute(attribute)

            if class_attr := getattr(self, name, None):
                assert isinstance(class_attr, type(attribute)), (
                    f"Class attribute {class_attr} is not an instance of "
                    f"its introspected attribute's type {type(attribute)} "
                    f"on subsystem '{self._subsystem}'."
                )
                assert class_attr.datatype == attribute.datatype, (
                    f"Datatype of Introspected attribute "
                    f"'{name}': {type(attribute).__name__}({attribute.datatype}) "
                    f"does not match datatype of its class defined attribute "
                    f"{type(class_attr).__name__}({class_attr.datatype}) "
                    f"on subsystem '{self._subsystem}'."
                )
                setattr(self, name, attribute)

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
        attributes: dict[str, AttributeR | AttributeRW] = {}
        for parameter in parameters:
            group = cls._group(parameter)
            match parameter.response.access_mode:
                case "r":
                    attributes[parameter.attribute_name] = AttributeR(
                        parameter.attribute_name,
                        parameter.fastcs_datatype,
                        EIGER_IO_REFS[parameter.mode](
                            parameter.subsystem, parameter.mode, parameter.key
                        ),
                        # group=group,
                    )
                case "rw":
                    attributes[parameter.attribute_name] = AttributeRW(
                        parameter.attribute_name,
                        parameter.fastcs_datatype,
                        EIGER_IO_REFS[parameter.mode](
                            parameter.subsystem, parameter.mode, parameter.key
                        ),
                        # group=group,
                    )
        return attributes

    async def _handle_parameter_update(
        self, put_parameter: str, fetch_parameters: list[str]
    ):
        update_now = [put_parameter]
        update_later = []
        for parameter in fetch_parameters:
            if parameter == "difference_mode":
                # handling Eiger API inconsistency
                parameter = "threshold/difference/mode"

            if parameter in FETCH_BEFORE_RETURNING:
                update_now.append(parameter)
            else:
                update_later.append(parameter)

        await asyncio.gather(
            self.update_now(update_now), self.queue_update(update_later)
        )

    async def queue_update(self, parameters: Iterable[str]):
        """Add the given parameters to the list of parameters to update.

        Args:
            parameters: Parameters to be updated

        """
        if not parameters:
            return

        if coros := self._get_update_coros_for_parameters(parameters):
            self.stale_parameters._set(True)
            async with self._parameter_update_lock:
                for coro in coros:
                    await self.queue.put(coro)

    async def update_now(self, parameters: Iterable[str]):
        """Update the given parameters immediately without queueing or setting the
        top controller's stale_parameters ``Attribute``.
        Args:
            parameters: Parameters to be updated immediately

        """
        if parameters:
            logging.info(f"Updating {parameters} before returning success for put")
            coros = self._get_update_coros_for_parameters(parameters)
            await asyncio.gather(*coros)

    def _get_update_coros_for_parameters(
        self, parameters: Iterable[str]
    ) -> list[Coroutine]:
        coros: list[Coroutine] = []
        for parameter in parameters:
            attr_name = key_to_attribute_name(parameter)
            match self._attributes.get(attr_name, None):
                case AttributeR() as attr if attr.io_ref.update_period is not None:
                    attr_io = self._attribute_ref_io_map[type(attr.io_ref)]
                    assert isinstance(attr_io, EigerConfigAttributeIO)
                    coros.append(attr_io.config_update(attr))
                case _ as attr:
                    if parameter not in IGNORED_KEYS:
                        print(
                            f"Failed to find updater for {parameter}"
                            f"with attribute {attr}"
                        )
        return coros

    # @scan(0.1)
    async def update(self):
        """Periodically check for parameters that need updating from the detector."""
        if not self.queue.empty():
            coros: list[Coroutine] = []
            async with self._parameter_update_lock:
                while not self.queue.empty():
                    coros.append(await self.queue.get())
            await asyncio.gather(*coros)

        self.stale_parameters._set(not self.queue.empty())
