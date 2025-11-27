import asyncio
from collections.abc import Callable, Coroutine, Iterable
from typing import Literal

from fastcs.attributes import Attribute, AttrR, AttrRW
from fastcs.controllers import Controller
from fastcs.logging import bind_logger

from fastcs_eiger.eiger_parameter import (
    EIGER_PARAMETER_MODES,
    EigerParameterRef,
    EigerParameterResponse,
    key_to_attribute_name,
)
from fastcs_eiger.http_connection import HTTPConnection
from fastcs_eiger.io import EigerAttributeIO

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


class EigerSubsystemController(Controller):
    _subsystem: Literal["detector", "stream", "monitor"]

    def __init__(
        self,
        connection: HTTPConnection,
        queue_subsystem_update: Callable[[list[Coroutine]], Coroutine],
    ):
        self.logger = bind_logger(__class__.__name__)

        self.connection = connection
        self._queue_subsystem_update = queue_subsystem_update
        self._io = EigerAttributeIO(connection, self.update_now, self.queue_update)
        super().__init__(ios=[self._io])

    async def _introspect_detector_subsystem(self) -> list[EigerParameterRef]:
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
                    EigerParameterRef(
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
            self.add_attribute(name, attribute)

    @classmethod
    def _group(cls, parameter: EigerParameterRef):
        if "/" in parameter.key:
            group_parts = parameter.key.split("/")[:-1]
            # e.g. "threshold/difference/mode" -> ThresholdDifference
            return "".join(list(map(str.capitalize, group_parts)))
        return f"{parameter.subsystem.capitalize()}{parameter.mode.capitalize()}"

    @classmethod
    def _create_attributes(cls, parameters: list[EigerParameterRef]):
        """Create ``Attribute``s from ``EigerParameterRef``s.

        Args:
            parameters: ``EigerParameterRef``s to create ``Attributes`` from

        """
        attributes: dict[str, Attribute] = {}
        for parameter in parameters:
            group = cls._group(parameter)
            match parameter.response.access_mode:
                case "r":
                    attributes[parameter.attribute_name] = AttrR(
                        parameter.fastcs_datatype,
                        group=group,
                        io_ref=parameter,
                    )
                case "rw":
                    attributes[parameter.attribute_name] = AttrRW(
                        parameter.fastcs_datatype, group=group, io_ref=parameter
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
            coros = self._get_update_coros_for_parameters(parameters)
            await asyncio.gather(*coros)
            self.logger.info("Parameters updated during put", parameters=parameters)

    def _get_update_coros_for_parameters(
        self, parameters: Iterable[str]
    ) -> list[Coroutine]:
        coros: list[Coroutine] = []
        for parameter in parameters:
            attr_name = key_to_attribute_name(parameter)
            match self.attributes.get(attr_name, None):
                case AttrR(io_ref=EigerParameterRef()) as attr:
                    coros.append(self._io.do_update(attr))  # type: ignore
                case _ as attr:
                    if parameter not in IGNORED_KEYS:
                        print(
                            f"Failed to find updater for {parameter}"
                            f"with attribute {attr}"
                        )
        return coros
