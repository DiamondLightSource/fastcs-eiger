import logging

from fastcs2 import ConsoleTransport, FastCS

from fastcs_eiger.controller.eiger_detector_controller import EigerDetectorController

logging.basicConfig(level=logging.INFO)

controller = EigerDetectorController("127.0.0.1", 8081)
fastcs = FastCS(controller, ConsoleTransport)

fastcs.run()
