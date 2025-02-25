[![CI](https://github.com/DiamondLightSource/fastcs-eiger/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/fastcs-eiger/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/fastcs-eiger/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/fastcs-eiger)
[![PyPI](https://img.shields.io/pypi/v/fastcs-eiger.svg)](https://pypi.org/project/fastcs-eiger)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# FastCS Eiger

Control system integration for Dectris Eiger detectors using FastCS.

## Quickstart

1. Run eiger-detector development environment with data writers and simulated detector

    i. `podman run --rm -it -v /dev/shm:/dev/shm -v /tmp:/tmp --net=host ghcr.io/dls-controls/eiger-detector-runtime:latest`

    ii. It may be necessary to add the flag `--security-opt label=disable` if there are
    SELinux permissions restrictions.

2. Run the IOC against the simulated detector, either from a local checkout

    i. ``fastcs-eiger ioc `hostname -s`-EIGER``

    ii. or run the `Eiger IOC` vscode launch config, but edit it to include your
    hostname or there could be PV clashes from duplicate IOCs on the same network.

3. or to run the latest release directly from the container registry

    i. Make a local directory for UIs `mkdir /tmp/opi` - bob files will appear here that
    can be opened on the host with Phoebus.

    ii. `podman run --rm -it -v /tmp/opi:/epics/opi --net=host ghcr.io/DiamondLightSource/fastcs-eiger:latest`

Source          | <https://github.com/DiamondLightSource/fastcs-eiger>
:---:           | :---:
PyPI            | `pip install fastcs-eiger`
Docker          | `docker run ghcr.io/diamondlightsource/fastcs-eiger:latest`
Documentation   | <https://diamondlightsource.github.io/fastcs-eiger>
Releases        | <https://github.com/DiamondLightSource/fastcs-eiger/releases>

<!-- README only content. Anything below this line won't be included in index.md -->

See https://diamondlightsource.github.io/fastcs-eiger for more detailed documentation.
