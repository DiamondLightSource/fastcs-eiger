from fastcs_eiger.attribute_io.eiger_attribute_io import EigerAttributeIORef
from fastcs_eiger.attribute_io.eiger_config_attribute_io import (
    EigerConfigAttributeIORef,
)

EIGER_IO_REFS: dict[str, type[EigerAttributeIORef]] = {
    "status": EigerAttributeIORef,
    "config": EigerConfigAttributeIORef,
}
