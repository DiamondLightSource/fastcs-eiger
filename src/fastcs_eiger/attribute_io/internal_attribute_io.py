from typing import Any

from fastcs2.attribute import AttributeR, AttributeRW
from fastcs2.attribute_io import AttributeIO
from fastcs2.attribute_io_ref import AttributeIORef


class InternalAttributeIORef(AttributeIORef):
    pass


class InternalAttributeIO(AttributeIO):
    """
    Handler for FastCS Attribute Creation

    Dataclass that is called using the AttrR, AttrRW function.
    Used for dynamically created attributes that are added for additional logic
    """

    def __init__(self):
        super().__init__(InternalAttributeIORef)

    async def put(self, attr: AttributeRW, value: Any) -> None:
        assert isinstance(attr, AttributeR)  # AttrW does not implement set
        await attr.update(value)
