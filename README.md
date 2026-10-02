# VIRAL-HTS
High-Throughput Sequencing for virus detection

#Container

```bash
docker build --platform linux/amd64 -t fevir:1.0.0-dev . && \
docker save -o fevir-1.0.0-dev.tar fevir:1.0.0-dev && \
singularity build --force \
  fevir-1.0.0-dev.sif \
  docker-archive:fevir-1.0.0-dev.tar
```
