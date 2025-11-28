from fastcs.attributes import AttrR
from fastcs.datatypes import Bool
from fastcs_odin.io.status_summary_attribute_io import StatusSummaryAttributeIORef
from fastcs_odin.odin_subcontroller import OdinSubController
from fastcs_odin.util import create_attribute


class EigerFanAdapterController(OdinSubController):
    """Controller for an EigerFan adapter in an odin control server"""

    state: AttrR[str]

    async def initialise(self):
        for parameter in self.parameters:
            # Remove 0 index and status/config
            match parameter.uri:
                case ["0", "status" | "config", *_]:
                    parameter.set_path(parameter.path[2:])
            self.add_attribute(
                parameter.name,
                create_attribute(parameter=parameter, api_prefix=self._api_prefix),
            )

        # Manually validate `state` to get a nicer error message if not introspected
        self._validate_hinted_attributes()

        self.ready = AttrR(
            Bool(),
            io_ref=StatusSummaryAttributeIORef(
                [], "", lambda states: states[0] == "DSTR_HEADER", [self.state]
            ),
        )
