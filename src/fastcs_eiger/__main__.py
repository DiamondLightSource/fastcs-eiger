from fastcs.launch import launch

from fastcs_eiger import __version__

from .controllers.eiger_controller import EigerController
from .controllers.odin.eiger_odin_controller import EigerOdinController

launch(controller_classes=[EigerController, EigerOdinController], version=__version__)
