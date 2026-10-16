Copyright (C) 2020 Thomas Junier and Florian Laubscher

# FEVIR
High-throughput sequencing for viral detection

# Container

```bash
docker build --platform linux/amd64 -t fevir:1.0.0 .
docker save -o fevir-1.0.0.tar fevir:1.0.0
singularity build --force fevir-1.0.0.sif docker-archive:fevir-1.0.0.tar
```
