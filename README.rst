eiger-fastcs
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|


The existing Odin EPICS integration and underlying code is clunky and difficult to maintain. Odin deployments are dynamic by design, 
supporting multiple detectors and a scalable number of processes. EPICS database is static and inflexible. With pythonSoftIOC it is 
possible to create records dynamically at runtime, so it is possible to use introspection to check what parameters it needs to create, 
rather than defining them build time. FastCS will provide an abstraction layer to introspect hardware and other processes to create a 
set of parameters that they expose. These parameters can then be used to implement coordination logic and serve PVs by loading a 
generic EPICS backend into the application. [Placeholder].

============== ==============================================================
PyPI           ``pip install eiger-fastcs``
Source code    https://github.com/DiamondLightSource/eiger-fastcs
Documentation  https://DiamondLightSource.github.io/eiger-fastcs
Releases       https://github.com/DiamondLightSource/eiger-fastcs/releases
============== ==============================================================

Explanation of how to run Eiger-fastcs works once project is complete

.. code-block:: python

    print("Placeholder Print Code - To add functionality afterwards")

Command Line Placeholder 
    $ python -m eiger_fastcs --version

.. |code_ci| image:: https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/code.yml/badge.svg?branch=main
    :target: https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/code.yml
    :alt: Code CI

.. |docs_ci| image:: https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/docs.yml/badge.svg?branch=main
    :target: https://github.com/DiamondLightSource/eiger-fastcs/actions/workflows/docs.yml
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/DiamondLightSource/eiger-fastcs/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/DiamondLightSource/eiger-fastcs
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/eiger-fastcs.svg
    :target: https://pypi.org/project/eiger-fastcs
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://DiamondLightSource.github.io/eiger-fastcs for more detailed documentation.
