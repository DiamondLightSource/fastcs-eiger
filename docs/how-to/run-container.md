# Run in a container

Pre-built containers with fastcs-eiger and its dependencies already
installed are available on [Github Container Registry](https://ghcr.io/DiamondLightSource/fastcs-eiger).

## Starting the container

To pull the container from github container registry and run:

```
$ docker run ghcr.io/diamondlightsource/fastcs-eiger:latest --version
```

To get a released version, use a numbered release instead of `latest`.