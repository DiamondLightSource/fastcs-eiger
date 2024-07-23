[![CI](https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/eiger-fastcs/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/eiger-fastcs)
[![PyPI](https://img.shields.io/pypi/v/eiger-fastcs.svg)](https://pypi.org/project/eiger-fastcs)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# Eiger FastCS

Control system integration for Dectris Eiger detectors using FastCS.

## Quickstart

1. Run eiger-detector development environment with data writers and simulated detector

    i. `podman run --rm -it -v /dev/shm:/dev/shm -v /tmp:/tmp --net=host ghcr.io/dls-controls/eiger-detector-runtime:latest`

2. Run the IOC against the simulated detector, either from a local checkout

    i. `eiger-fastcs ioc EIGER` (or run `Eiger IOC` vscode launch config)

3. or the container

    i. Make a local directory for UIs `mkdir /tmp/opi`

    ii. `podman run --rm -it -v /tmp/opi:/epics/opi --net=host ghcr.io/DiamondLightSource/eiger-fastcs:latest`

Source          | <https://github.com/DiamondLightSource/eiger-fastcs>
:---:           | :---:
PyPI            | `pip install eiger-fastcs`
Docker          | `docker run ghcr.io/diamondlightsource/eiger-fastcs:latest`
Documentation   | <https://diamondlightsource.github.io/eiger-fastcs>
Releases        | <https://github.com/DiamondLightSource/eiger-fastcs/releases>


<!-- README only content. Anything below this line won't be included in index.md -->

See https://diamondlightsource.github.io/eiger-fastcs for more detailed documentation.
