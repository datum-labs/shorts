---
title: You already know datumctl compute
author: Daniel Lotterman
date: Draft, Nov 2026
reference file: https://github.com/datum-labs/shorts/blob/main/gists/compute/datumctl-compute-reference.md
---

![Docker and Podman + Datum](../assets/datumctl-docker-podman/00-docker-podman-plus-datum.svg)

*datumctl compute plugin v0.12 · Docker 20.10 · Podman 4.3 · captured 13 Nov 2026*

If you can run a container with `docker` or `podman`, you can run one on Datum.

## Same command

```bash
docker run -d -p 8080:80 docker.io/traefik/whoami
```

```bash
datumctl compute deploy whoami --image=docker.io/traefik/whoami \
  --http-port=80 --location=us-east-1 --runtime-class=general-purpose
```

![The same image and port: docker run publishes a host port on your host, datumctl compute deploy publishes an HTTPS URL that reaches an Instance in a Datum location](../assets/datumctl-docker-podman/01-same-command.png)

*Same image, same port. A URL takes the place of the host port, and TLS ends at Datum's edge.*

![Terminal run: docker run and curl on a Docker host, then datumctl compute deploy and curl of the HTTPS URL it prints](../assets/datumctl-docker-podman/10-run-same-command.gif)

*Terminal run: the same whoami image under `docker run` and `datumctl compute deploy`. On Datum it answers on an HTTPS URL, from an IPv6 address.*

- Pass `--runtime-class=general-purpose` for a stock image. The default is `unikernel`.
  [Why](../gists/compute/datumctl-compute-reference.md#5-runtime-classes)
- The app listens on `::`. Instances are IPv6 only.
  [IPv6 crash course](https://www.datum.net/blog/ipv6-crash-course)

## Same verbs

| You type | Now type |
|---|---|
| `docker run` | `datumctl compute deploy` |
| `docker ps` | `datumctl compute workloads` |
| `docker logs -f` | `datumctl compute logs -f` |
| `docker exec -it … sh` | `datumctl compute exec … -it -- sh` |
| `docker restart` | `datumctl compute restart` |
| `docker rm -f` | `datumctl compute destroy` |
| `docker build` | `datumctl compute build` |
| `docker context use` | `datumctl ctx` |
| `-e`, `--env-file`, `-v` | `--env`, `--env-from-secret`, `--secret` |

![Terminal run: docker ps next to datumctl compute workloads, docker logs next to compute logs, and docker exec next to compute exec showing a different kernel and capability set](../assets/datumctl-docker-podman/11-run-same-verbs.gif)

*Terminal run: `ps`, `logs` and `exec` on both. The container reports the host's kernel. The Instance reports its own.*

[Every verb and flag](../gists/compute/datumctl-compute-reference.md#2-command-map)

## Same defaults, almost

```bash
podman run --cap-drop SYS_CHROOT --security-opt no-new-privileges IMAGE
```

*Podman's default capabilities, minus `SYS_CHROOT`, with no-new-privileges: the same set as a `general-purpose` Instance.*

[Measured sets](../gists/compute/datumctl-compute-reference.md#14-local-preflight-with-podman)

## Same command, more places

```bash
datumctl compute deploy api --image=docker.io/traefik/whoami --city=DFW,IAD,SJC \
  --http-port=80 --runtime-class=general-purpose
```

![One deploy command creates one Workload with an Instance in each of Dallas, Ashburn and San Jose, behind one HTTPS URL](../assets/datumctl-docker-podman/02-many-places.png)

*One command, one Workload, one Instance in each city, one URL.*

![Terminal run: one deploy with --city=DFW,IAD,SJC rolls out three Instances, one per location, behind one URL, then docker rm and datumctl compute destroy clean up](../assets/datumctl-docker-podman/12-run-more-places.gif)

*Terminal run: three cities, 8 seconds, one URL.*

Compute runs in `us-central-1` (DFW), `us-east-1` (IAD) and `us-west-1` (SJC).
[Placement](../gists/compute/datumctl-compute-reference.md#43-many-places-from-one-command)

## Same Dockerfile

![Docker build and push give a plain image that general-purpose runs as is. datumctl compute build checks and packages the same Dockerfile for either class. Pushing the archive with skopeo is a dead end for unikernel](../assets/datumctl-docker-podman/03-build-push.png)

*Any image runs on `general-purpose`. `datumctl compute build` packages it for `unikernel` too.*

```text
$ datumctl compute build --analyze .
  finding entrypoint /usr/local/bin/python3
  running architecture check ... running runtime libraries check ...
✓ No compatibility issues found
```

`--fix` and `deploy --build` edit your Dockerfile in place.
[Build details](../gists/compute/datumctl-compute-reference.md#9-build)

## Same(-ish) IPv6 networks

![Docker resolves container names inside one bridge network on one host. Datum resolves Instance names across a network that spans locations, keeps networks isolated, and reaches IPv6 internet directly and IPv4 services by name through NAT64](../assets/datumctl-docker-podman/04-networks.png)

*Names resolve inside a network, and networks stay isolated. Datum's networks span cities. IPv4-only services are reachable by name, through DNS64 and NAT64.*

```yaml
# compose.yaml
services:
  api:
    image: docker.io/traefik/whoami
    networks: [backend]

networks:
  backend: {}
```

```yaml
# network.yaml + workload.yaml
apiVersion: networking.datumapis.com/v1alpha
kind: Network
metadata: {name: backend}
spec:
  ipam: {mode: Auto}
---
apiVersion: compute.datumapis.com/v1alpha
kind: Workload
metadata: {name: api}
spec:
  template:
    spec:
      networkInterfaces:
        - network: {name: backend}
      runtime: …                     # as in "Same(-ish) YAML shape" below
  placements: …
```

[Networks, DNS and egress](../gists/compute/datumctl-compute-reference.md#11-networks-dns-and-egress) ·
[IPv6 crash course](https://www.datum.net/blog/ipv6-crash-course)

## Same(-ish) YAML shape

```yaml
apiVersion: compute.datumapis.com/v1alpha
kind: Workload
metadata: {name: whoami}
spec:
  template:
    spec:
      runtime:
        class: general-purpose
        sandbox:
          containers:
            - name: app
              image: docker.io/traefik/whoami
              ports: [{name: http, port: 80}]
      networkInterfaces:
        - network: {name: default}
  placements:
    - name: east
      locations: [{name: us-east-1}]
      scaleSettings: {minReplicas: 1}
```

Workload files will look familiar to consumers of Compose and Kubeconfig files.
[Full manifest](../gists/compute/datumctl-compute-reference.md#12-manifests)

## Run datumctl itself in a container

```bash
podman run --rm -it -v datumctl-config:/root/.datumctl docker.io/dlotterman/datumctl-container:latest login
```

[dlotterman/datumctl-container](https://github.com/dlotterman/datumctl-container)
