---
title: "Technical reference: datumctl compute for Docker and Podman users"
author: Daniel Lotterman
date: Draft, Nov 2026
---

# Technical reference: datumctl compute for Docker and Podman users

Companion to the short [You already know datumctl compute](../../shorts/datumctl-docker-podman.md).

Tags:

| Tag | Meaning |
|---|---|
| **[V]** | Verified against a live Datum project. Dates and transcripts in §16 |
| **[D]** | Datum docs, including pages pending in [docs#118](https://github.com/datum-cloud/docs/pull/118), [#120](https://github.com/datum-cloud/docs/pull/120) and [#157](https://github.com/datum-cloud/docs/pull/157) |
| **[C]** | `datumctl … --help`, compute plugin v0.12.11 |
| **[N]** | Field notes from earlier deploys, not re-tested |
| **[?]** | Open (§17) |

Compute is in preview. APIs are `v1alpha`. Re-check before relying on any of this.

Contents

1. [Mental model](#1-mental-model)
2. [Command map](#2-command-map)
3. [The CLI is a client](#3-the-cli-is-a-client)
4. [Deploy: flags and semantics](#4-deploy-flags-and-semantics)
5. [Runtime classes](#5-runtime-classes)
6. [Ports, URLs and protocols](#6-ports-urls-and-protocols)
7. [Environment, ConfigMaps and Secrets](#7-environment-configmaps-and-secrets)
8. [What changes what](#8-what-changes-what)
9. [Build](#9-build)
10. [Registry credentials](#10-registry-credentials)
11. [Networks, DNS and egress](#11-networks-dns-and-egress)
12. [Manifests](#12-manifests)
13. [Operate: logs, exec, scale, restart, destroy](#13-operate-logs-exec-scale-restart-destroy)
14. [Local preflight with Podman](#14-local-preflight-with-podman)
15. [Errors and their causes](#15-errors-and-their-causes)
16. [Experiments and transcripts](#16-experiments-and-transcripts)
17. [Limits and open questions](#17-limits-and-open-questions)
18. [Sources](#18-sources)

---

## 1. Mental model

**Docs:** [Compute overview](https://www.datum.net/docs/compute/overview) · [Choose a runtime class](https://www.datum.net/docs/compute/runtimes/overview) · [Deploy an app](https://www.datum.net/docs/getting-started/first-workload)

| Concept | Docker / Podman | datumctl compute |
|---|---|---|
| Unit | Container: one process tree on the host kernel | **Workload**: a template plus placements. Owns **Instances** [D] |
| Isolation | Namespaces and cgroups, shared kernel | One VM per Instance, own kernel (Kata Containers, guest kernel 6.18.35) [D][V] |
| Where | The engine's host | `us-central-1` (DFW), `us-east-1` (IAD), `us-west-1` (SJC) [D][V]. `get locations` lists 16; only these 3 serve Compute [V] |
| Who you talk to | Local daemon (Docker), no daemon (Podman), `DOCKER_HOST` / `podman --remote` for remote | The Datum API, always [C] |
| Run | `docker run -d IMAGE` | `datumctl compute deploy NAME --image=IMAGE --location=L --runtime-class=general-purpose` [C] |
| Publish | `-p 8080:80` host port | `--http-port=80` managed HTTPS URL [C][V] |
| Config | `-e`, `--env-file`, `-v` | `--env`, `--env-from-configmap`, `--env-from-secret`, `--configmap`, `--secret` [C] |
| Declarative | `compose.yaml`, `podman kube play` | `compute deploy -f`, `datumctl apply -f`. Kubernetes-shaped, kind `Workload` [C][V] |
| Image | Any OCI image | Any linux/amd64 OCI image on `general-purpose`; packaged image on `unikernel` [D][V] |
| Containers per unit | Pods allow many (Podman) | One container per Instance [D] |
| Size | Host limits, `--cpus`, `--memory` | One instance type: 1 vCPU, 2 GiB [D]. The guest reports 2 CPUs and 4,031,092 kB `MemTotal` [V] |
| Address family | IPv4 default, IPv6 opt-in | IPv6 only inside. IPv4 internet by hostname via DNS64/NAT64 [D][V] |
| Default runtime | n/a | `unikernel` [D][V] |

## 2. Command map

**Docs:** [Compute commands](https://www.datum.net/docs/datumctl/compute/overview) · [datumctl overview](https://www.datum.net/docs/datumctl/overview)

| Docker | Podman | datumctl | Notes |
|---|---|---|---|
| `docker login` | `podman login` | `datumctl login` | Datum sign-in. Registry sign-in is a Secret, §10 [C] |
| `docker context use` | `podman system connection default` | `datumctl ctx` | Org/project context [C] |
| `docker run -d IMAGE` | `podman run -d IMAGE` | `compute deploy NAME --image=IMAGE --location=L --runtime-class=general-purpose --yes` | Returns after rollout [V] |
| `docker run -it --rm IMAGE sh` | same | none | Deploy, then `compute exec` |
| `docker ps` | `podman ps` | `compute workloads`, `compute instances` | `--health=degraded`, `--location=L` [D] |
| `docker inspect` | `podman inspect` | `compute workloads describe`, `compute instances describe`, `datumctl get … -o yaml` | `describe` shows env sources, not values [V] |
| `docker logs -f` | `podman logs -f` | `compute logs NAME -f --since=15m` | Merged across Instances. Polls. `--alb` access logs [C][V] |
| `docker exec -it C sh` | `podman exec -it C sh` | `compute exec INSTANCE -it -- sh` | Instance name, not Workload name. `general-purpose` only. `--ttl` 1m–1h, default 15m [C][D][V] |
| `docker restart` | `podman restart` | `compute restart NAME [--location=L]` | Rolling, one at a time per location [D] |
| `docker rm -f` | `podman rm -f` | `compute destroy NAME --yes` | Instances and URL go. Secrets, ConfigMaps, custom domains stay [D][V] |
| `docker build -t T .` | `podman build -t T .` | `compute build .` | Local check only [C] |
| `docker push` | `podman push` | `compute build --push --output REG/IMG:TAG .` | Packages for unikernel [V] |
| `docker save` | `podman save` | `compute build --output ./img.tar .` | OCI archive [C] |
| `docker compose up --scale` | `podman-compose --scale` | `compute deploy --min=N` / `compute scale NAME --min=N` | Per location. No autoscaling, no zero [D][V] |
| `docker compose -f` | `podman kube play` | `compute deploy -f`, `datumctl apply -f`, `datumctl diff -f` | Workload kind only, §12 [V] |
| `docker network create` | `podman network create` | `datumctl apply -f network.yaml`; `deploy --network=N` offers to create [C][V] | §11 |
| `docker stats` | `podman stats` | Per-Instance CPU and memory metrics; portal and `datumctl` [D] | §13 |
| `docker cp` | `podman cp` | none | ConfigMap, Secret or image |
| `docker events` | `podman events` | `compute rollout NAME`, `datumctl activity` [C][D] | |
| `docker pull` | `podman pull` | none; Instances pull at start | New tag or digest, §8 |
| `docker port` | `podman port` | Last line of `deploy`; `URL` column of `compute workloads` [V] | |
| `docker version` | `podman version` | `datumctl version` | Client and server [C] |
| CLI plugins (`compose`, `buildx`) | extensions | `datumctl plugin list` | `compute` is itself a plugin [C][D] |

kubectl-shaped verbs: `get`, `describe`, `apply`, `diff`, `edit`, `patch`, `label`, `annotate`, `delete`, `explain`,
`api-resources` [C].

## 3. The CLI is a client

**Docs:** [Install](https://www.datum.net/docs/datumctl/install) · [Logging in](https://www.datum.net/docs/datumctl/auth/logging-in) · [Service accounts](https://www.datum.net/docs/datumctl/auth/service-accounts) · [Contexts and scoping](https://www.datum.net/docs/datumctl/contexts-and-scoping) · [Using plugins](https://www.datum.net/docs/datumctl/plugins/using-plugins) · [Limits and quotas](https://www.datum.net/docs/compute/limits-and-quotas)

- Client to the Datum API, like `docker -H` or `podman --remote` [C].
- `datumctl ctx`: list and switch org/project, like `docker context`. `--org`, `--project` per command. `DATUM_SESSION` runs
  one command as another signed-in account [C].
- CI: `datumctl login --credentials ./key.json` (service account) [C].
- Compute turns on for a project on the first `datumctl compute` command [D]. `compute access` shows status [C].
- Plugins, measured [V]:

```text
$ datumctl plugin list
NAME        INDEX      VERSION             TRUST         DESCRIPTION
compute     datum      v0.12.11            official      Deploy and manage containerized workloads on Datum Cloud
connect     (direct)   v1.0.0-preview.27   third-party   Connect devices and expose services through Datum Connect
dns         datum      v0.10.5             official      Manage DNS zones and records on Datum Cloud
ipam        datum      v0.5.1              official      Manage IP address space (pools and prefixes) across the platform
search      datum      v0.8.4              official      Search platform resources on Datum
telemetry   datum      v0.5.0              official      Query logs for the active project
alb         datum      v0.32.31            official      Manage Application Load Balancers on Datum Cloud
assistant   datum      v0.0.5              official      Chat with Patch, the Datum Cloud assistant
```

- In a container: [dlotterman/datumctl-container](https://github.com/dlotterman/datumctl-container). Every transcript here
  used it [V]:

```bash
podman run --rm -i -v datumctl-config:/root/.datumctl docker.io/dlotterman/datumctl-container:latest compute workloads
```

Container notes [V]: entrypoint is `datumctl` (`--entrypoint sh` to look inside); login state in the named volume; SELinux
hosts need `:Z` on bind mounts or reads and `workload.yaml` writes fail with `permission denied`; `--http-proxy=false` when the
host's proxy variables don't reach from the container.

## 4. Deploy: flags and semantics

**Docs:** [Deploying workloads](https://www.datum.net/docs/datumctl/compute/deploying-workloads) · [Placement and scaling](https://www.datum.net/docs/compute/placement-and-scaling)

### 4.1 Flags [C]

| datumctl compute deploy | Docker / Podman | Meaning |
|---|---|---|
| `NAME` | `--name` | Immutable [V] |
| `--image` | `IMAGE` | Registry host required (`must include a registry`) [D]. Required on every flag deploy [V] |
| `--location=a,b` | none | Exactly one of `--location`, `--city`, `--location-selector` [D] |
| `--city=DFW,IAD` | none | Selector on `topology.datum.net/city-code`. Cities without Compute are skipped silently [V] |
| `--location-selector` | none | Any topology selector |
| `--runtime-class` | `--runtime` (closest) | Default `unikernel` [D][V]. Immutable |
| `--network` | `--network` | Default `default`. Immutable. Offers to create a missing one |
| `--http-port` | `-p H:C` | Managed HTTPS URL; plain HTTP to the app. `--port` isn't supported [D] |
| `--http2` | none | HTTP/2 to the container (gRPC). Sticky until `--http2=false` |
| `--no-http` | drop `-p` | Remove the HTTP service and URL |
| `--env K=V` / `K-` | `-e` | Set or remove |
| `--env-from-configmap NAME[:PREFIX_]` | `--env-file` | Import every key. `general-purpose` only [D] |
| `--env-from-secret NAME[:PREFIX_]` | `--env-file` | Same, from a Secret |
| `--configmap NAME:/path` / `NAME-` | `-v` | Keys as files |
| `--secret NAME:/path` / `NAME-` | `-v`, `podman --secret` | Keys as files |
| `--label k=v` / `k-` | `--label` | Workload and Instances. Replaces Instances [D][V] |
| `--instance-type` | `--cpus`, `--memory` | Default `datumcloud-d1-standard-2`. The only type [D] |
| `--min` | `--scale` | Instances per location. Default 1. Must be ≥ 1 [V] |
| `--max`, `--cpu-percent`, `--memory-percent` | none | In the CLI; autoscaling isn't supported in the preview. Don't set [D] |
| `--build[=DIR]` | build + push + run | Pushes to `--image`, deploys the digest. Applies `--fix`: rewrites the Dockerfile in place |
| `-f FILE` | `compose -f`, `kube play` | Manifest. Can't combine with config flags [D] |
| `-y` | none | No prompts |
| (no args) | none | Interactive |

Not offered: `--platform`, `--restart`, `--health-cmd`, `--init`, `--user`, `--read-only`, `--cap-add`, `--pull`,
`--entrypoint`, `--command`. Command and args: manifest only [C].

### 4.2 Carry-forward

- Kept across flag deploys: env, ConfigMap and Secret imports, mounts, labels [C][D][V]. Remove with a trailing `-`.
- Replaced by every flag deploy: the template and placements. Lost: registry credentials, `command`, `args`, extra
  placements. Instance count reset to `--min` (default 1) [D][V].
- One way per workload: flags or `-f`.
- Omitting `--http-port` keeps the existing port and URL [C].
- Each flag deploy overwrites `./workload.yaml` [D]. Keep edited manifests under another name.

### 4.3 Many places from one command

```bash
datumctl compute deploy api --image=docker.io/traefik/whoami:v1.10.3 --city=DFW,IAD,SJC --http-port=80 --runtime-class=general-purpose --yes
```

One Workload, one placement `default`, one Instance per location, one URL. Rollout 8 s for all three [V] (§16.18).

- Compute locations: `us-central-1` (Dallas), `us-east-1` (Ashburn), `us-west-1` (San Jose) [D][V].
- `--city=DFW,IAD,AMS` deployed to DFW and IAD only, with no warning [V]. `--location=nl-west-1` is refused:
  `Unsupported value: "nl-west-1": supported values: "us-central-1", "us-east-1", "us-west-1"` [V].
- Instance names: `<workload>-<placement>-<location>-<n>` [V].
- Rollouts replace Instances one at a time per location, no surge [D].

## 5. Runtime classes

**Docs:** [Choose a runtime class](https://www.datum.net/docs/compute/runtimes/overview) · [Run a container image](https://www.datum.net/docs/compute/runtimes/general-compute) · [Build and deploy a unikernel](https://www.datum.net/docs/compute/runtimes/unikernels)

|  | general-purpose | unikernel |
|---|---|---|
| Default | No | **Yes** [D][V] |
| Image | Any linux/amd64 OCI image [D][V] | Packaged by `compute build` [D][V] |
| arm64-only image | `ImageUnavailable`, "could not be pulled" [V] | n/a |
| Kernel | Own, per Instance [D][V] | Own, per Instance [D] |
| Startup | `Available` 4 s after create, two runs [V] | "A fraction of a second" [D]. Not measured here [?] |
| Capabilities | `CapEff 0x800005fb` [V]: CHOWN, DAC_OVERRIDE, FOWNER, FSETID, KILL, SETGID, SETUID, SETPCAP, NET_BIND_SERVICE, SETFCAP | None addable [D] |
| no-new-privileges | On (`NoNewPrivs: 1`) [V]. `allowPrivilegeEscalation: true` turns it off [D] | |
| User | Image's user; root stays root [V] | |
| Memory | 2 GiB Instance [D] | Root filesystem in memory, counted against it [D] |
| Dynamic loading | Normal | Everything loaded at runtime must be in the image, `dlopen` plugins too [D] |
| `envFrom` | Yes | No; `valueFrom` [D] |
| `exec` | Yes [D][V] | No [D] |
| Debug | Logs, exec | Logs. Stuck in `Starting`: `compute build --analyze` [D] |
| Change later | No [V] | No |

Capabilities compared [V]:

| Runtime | `CapEff` | Difference from a Datum Instance |
|---|---|---|
| Datum `general-purpose` | `0x800005fb` | — |
| Podman 4.3 default | `0x800405fb` | + SYS_CHROOT |
| Docker 20.10 default | `0xa80425fb` | + SYS_CHROOT, NET_RAW, MKNOD, AUDIT_WRITE |

Field note [N]: the same app on both classes in one shared project answered 20 of 20 on general-purpose and 11 of 20 on
unikernel. One run.

## 6. Ports, URLs and protocols

**Docs:** [Publish a workload](https://www.datum.net/docs/compute/compute-and-alb) · [IPv6 readiness](https://www.datum.net/docs/compute/troubleshooting#ipv6-readiness) · [Network Load Balancer](https://www.datum.net/docs/nlb/overview)

- `--http-port=P`: `https://<words>.datumproxy.net`, last line of `deploy` [C][V].
- TLS ends at the ALB, certificate managed. Plain HTTP to port P [D][V].
- Listen on `::` [D][V]. `0.0.0.0` refuses connections [V]. Per server [D]:

| Server | Listen on IPv6 |
|---|---|
| nginx | `listen [::]:80;` |
| Node.js | `app.listen(8080, "::")` |
| Python | `uvicorn app:app --host :: --port 8080`, `http.server --bind ::` |
| Go | `http.ListenAndServe(":8080", h)` (dual-stack) |
| Caddy, traefik/whoami | Listen on every address by default [V] |

- Headers to the app: `X-Forwarded-For`, `X-Envoy-External-Address`, `X-Forwarded-Proto: https` [V].
- New hostname: `503` or no DNS for a minute or two [D][V].
- gRPC: `--http2` [C]. Not tested [?].
- Public TCP/UDP: Network Load Balancer, early access, IPv6 only, the 3 Compute locations [D].
- Basic auth is console-set and covers the whole hostname, health paths included. `destroy` drops it with the URL [N].
- Custom hostnames: `HTTPProxy` with a hostname [D]. Custom domains survive `destroy` [D].
- WAF: `TrafficProtectionPolicy`, OWASP CRS, manifest only [N].
- More: [IPv6 crash course](https://www.datum.net/blog/ipv6-crash-course).

## 7. Environment, ConfigMaps and Secrets

**Docs:** [Configure a workload](https://www.datum.net/docs/compute/configuration)

### 7.1 Setting them

| Want | Flag | Manifest |
|---|---|---|
| Literal | `--env K=V` | `env: [{name: K, value: V}]` |
| One key from a ConfigMap | none | `valueFrom: {configMapKeyRef: {name, key}}` |
| One key from a Secret | none | `valueFrom: {secretKeyRef: {name, key}}` |
| Every key | `--env-from-configmap`, `--env-from-secret` | `envFrom` (`general-purpose` only) |
| Files | `--configmap NAME:/path`, `--secret NAME:/path` | `volumes` + `volumeAttachments` |

- `apiVersion: v1` ConfigMap and Secret, `datumctl apply -f` [V].
- 256 KiB per object; 1 MiB per workload per location [D].
- Applying a workload checks `get` permission on every referenced ConfigMap and Secret [D].
- Use hostnames, not IPv4 addresses, in values [D].

### 7.2 When changes land [V]

| Change | Running Instance |
|---|---|
| Mounted file content | Updated in place (atomic-writer layout, `key -> ..data/key`) |
| Value used as env | Unchanged until `compute restart` |
| `registry-credentials` | Unchanged until `compute restart` |

### 7.3 Secret gotchas

- `apply` keeps `stringData` in clear in `kubectl.kubernetes.io/last-applied-configuration`; `get secret -o yaml` shows it [V].
  Use `create` or base64 `data:`.
- Secret mount dir is `drwxrwxrwt` [V].
- Values must be valid text; console-pasted bytes caused `ConfigurationError` [N][D].
- `configMap: {name: …}` vs `secret: {secretName: …}` [D][V].

## 8. What changes what

**Docs:** [Operations](https://www.datum.net/docs/compute/operations) · [Placement and scaling](https://www.datum.net/docs/compute/placement-and-scaling) · [Configure a workload](https://www.datum.net/docs/compute/configuration)

| Change | Effect |
|---|---|
| Same image tag | No-op. Same Instances, same boot IDs [V] |
| New tag or digest | Rolling replacement [V] |
| Image re-pushed under the same tag | Not picked up. New tag or digest [D] |
| `--env` | Rolling replacement [V] |
| Mounted ConfigMap or Secret content | Live in files [V] |
| ConfigMap or Secret used as env | `compute restart` [D][V] |
| `--label` | Replaces Instances; new boot IDs [D][V] |
| `--min` | Adds or removes Instances [C] |
| `--location`, `--city` | Adds or removes placements [C][V] |
| Any flag deploy over a manifest | Template and placements replaced, §4.2 [D][V] |
| `--runtime-class` | Refused; destroy and redeploy [V] |
| `--network` | Refused; destroy and redeploy [C][D] |
| Name | Destroy and redeploy [V] |
| `compute restart` | Rolling, one at a time per location [D] |

Rollback: deploy again with the previous image and flags [D]. `compute workloads describe` suggests
`datumctl compute rollout undo NAME`; that subcommand doesn't exist in v0.12.11 [V][C].

## 9. Build

**Docs:** [Building images](https://www.datum.net/docs/datumctl/compute/building-images) · [Build and deploy a unikernel](https://www.datum.net/docs/compute/runtimes/unikernels)

```bash
datumctl compute build .                                     # local check, nothing saved
datumctl compute build --analyze -f Dockerfile .             # check the built entrypoint
datumctl compute build --fix .                               # apply exact-line Dockerfile fixes in place, rebuild
datumctl compute build --output ./img.tar .                  # OCI archive
datumctl compute build --push --output ghcr.io/USER/app:1 .  # push, no prompt
datumctl compute build inspect IMAGE --extended              # check a pushed image
datumctl compute deploy api --build --image=ghcr.io/USER/app:1 --location=us-east-1   # build, push, deploy by digest
```

- `Dockerfile.datum` wins over `Dockerfile` [C].
- BuildKit: the engine's (Docker, OrbStack, Colima, `DOCKER_HOST`) or `--buildkit-host` [C]. Container default
  `BUILDKIT_HOST=tcp://buildkitd:1234`; override with `-e BUILDKIT_HOST=tcp://HOST:1234` [V]. Rootless BuildKit inside
  rootless Podman fails on `newuidmap` [V]; `moby/buildkit` under Docker on a VM, tunnelled, works [V].
- `--build-arg`, `--target` as Docker [C]; not on `deploy --build` [C].
- Reproducible digests; `SOURCE_DATE_EPOCH` for time-stamping steps [C].
- linux/amd64 only. No `--platform` [D][C].
- `--analyze` catches [V]:

```text
error[missing-libs]: /usr/local/bin/python3 requires 3 runtime files that are not present in the image
  --> Dockerfile:3
  | + COPY --from=src /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
  | + COPY --from=src /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/libpython3.12.so.1.0
  | + COPY --from=src /lib/libc.musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1
tip: rerun with --fix to apply the suggested Dockerfile edits automatically
```

- Not flagged [V]: `VOLUME`, `HEALTHCHECK`, `USER nobody`, shell-form `ENTRYPOINT`, `ENV HOST=0.0.0.0`.
- `--fix` and `deploy --build` rewrite the Dockerfile in place, no backup [V][C].
- Push with `compute build --push`, not `skopeo copy` from the archive [V]:

```text
# skopeo-pushed                      # datumctl-pushed
Status:   Incompatible               Status:   Compatible
Package:  Filesystem: not found      Platform: kraftcloud/x86_64
                                     Filesystem: packaged, 50.7 MiB
```

- Push and `build inspect` read sign-ins from a Docker-style config in the container:
  `-v COPY_OF_AUTH:/root/.docker/config.json:ro,Z` [V].

## 10. Registry credentials

**Docs:** [Configure a workload (private registry)](https://www.datum.net/docs/compute/configuration)

```yaml
apiVersion: v1
kind: Secret
metadata: {name: registry-credentials, namespace: default}
type: kubernetes.io/dockerconfigjson
stringData:
  .dockerconfigjson: |
    {"auths":{"ghcr.io":{"username":"USER","password":"READ_ONLY_TOKEN"}}}
```

- `spec.template.spec.runtime.sandbox.imagePullSecrets` [D]. Both classes [D].
- ghcr.io: `read:packages` to pull, `write:packages` to push [V].
- Podman `auth.json` shape (base64 `auth`) also accepted on general-purpose [V].
- Read at Instance start; `compute restart` after a change [V].
- Dropped by flag deploys [D].
- Without it: anonymous pulls [D].

## 11. Networks, DNS and egress

**Docs:** [gVPC](https://www.datum.net/docs/galactic-vpc/overview) · [Addressing](https://www.datum.net/docs/galactic-vpc/networks/addressing) · [Traffic and connecting](https://www.datum.net/docs/galactic-vpc/networks/traffic) · [Private DNS for Instances](https://www.datum.net/docs/compute/private-dns) · [Private DNS limits](https://www.datum.net/docs/domain-dns/private-dns-reference) · [gVPC configuration](https://www.datum.net/docs/galactic-vpc/configuration)

Default network [V]:

```yaml
apiVersion: networking.datumapis.com/v1alpha
kind: Network
metadata: {name: default, namespace: default}
spec:
  dns: {}
  egress: {internet: {mode: Enabled}}
  ipFamilies: [IPv6]
  ipam: {mode: Auto}
  mtu: 1440
status:
  ipam: {ipv6Prefix: fd20:0:52::/48}   # per project
```

Instance network, from inside [V]:

```text
inet6 fd20:0:52:1:0:2::/96 scope global          # one /96 per Instance
default via fd20:0:52:1::1 dev eth0
nameserver fd53::53                               # don't hard-code; can change [D]
search instances.datum.internal datum.internal
mtu 1440
```

### 11.1 Inside a network

| Fact | Tag |
|---|---|
| A network spans locations; one set of DNS names across them | [D][V] |
| Same network, any port, by IPv6 address | [D][V] |
| `<instance>.instances.datum.internal`, TTL 30 s, follows the address | [D][V] |
| Bare Instance name resolves through the search list (IAD → DFW worked) | [V]. Docs: use full names, search lists can differ [D] |
| Workload name: no answer | [V] |
| Different networks: isolated (timeout) | [D][V] |
| Instance addresses reused after deletes (`fd20:0:52::1:0:0` went to three Instances over two days) | [V] |
| One network per workload, chosen at create | [D][C] |
| No custom ranges or subnets | [D] |
| `networkPolicy` field accepted, no effect. Firewall rules on the roadmap | [D] |
| Instances can't route for other addresses; overlays (VXLAN, UDP tunnel) needed | [D] |
| Private DNS zones: your own zones per network, `A`/`AAAA`/`CNAME`/`SRV`…, up to 256 per network. Zone covering `instances.datum.internal` not allowed | [D] |
| New Instance name resolves within ~30 s of ready; removed ones linger up to 30 s | [D] |

### 11.2 To the internet

| Destination | Result | Tag |
|---|---|---|
| IPv6 address or name | Works. NAT66 to a public IPv6 | [D][V] |
| IPv4-only name (github.com) | Works. DNS64 answers `64:ff9b::8c52:7204`; NAT64 at the edge | [D][V] |
| `64:ff9b::<ipv4>` literal | Connects (NAT64 prefix is the well-known `64:ff9b::/96`) | [V] |
| IPv4 literal (`1.1.1.1`) | `Network unreachable` | [D][V] |
| Private IPv4 (`10.0.0.5`) | Unreachable | [D] |
| App with its own resolver (DoH, hard-coded 8.8.8.8) | No DNS64, IPv4-only names fail | [D] |
| TCP, UDP, ICMP | All work, both families | [D] |
| Source address | Shared, unpublished, can change. Don't allowlist | [D] |
| Turning egress off | Not possible yet; on the roadmap | [D] |

IPv4-only service with no name: put an `A` record in a public zone you control, connect by that name [D].

### 11.3 Docker comparison [V]

Docker 20.10, Debian 12:

```text
# user-defined bridge appnet: name resolution works
wget http://svc-a/    -> 200
# svc-iso on another network, from appnet
wget http://svc-iso/  -> bad address 'svc-iso'
# default bridge, by name
wget http://svc-def/  -> bad address 'svc-def'
```

| | Docker | Datum |
|---|---|---|
| Name scope | User-defined network, one host | Network, every location |
| What resolves | Container name, aliases | Instance name; your Private DNS records |
| Isolation | Per network | Per network |
| Inside address family | IPv4 (IPv6 opt-in) | IPv6 |
| IPv4 internet | Native | By name, NAT64 |

## 12. Manifests

**Docs:** [Configure a workload](https://www.datum.net/docs/compute/configuration) · [Network services](https://www.datum.net/docs/galactic-vpc/networks/network-services) · [Kubernetes](https://www.datum.net/docs/platform/kubernetes)

### 12.1 Minimum that applies [V]

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
      scaleSettings: {minReplicas: 1}      # required: without it, minReplicas 0 is refused
```

`namespace` and `resources.instanceType` may be omitted; the stored type is then `datumcloud-d1-standard-2` [V].
`datumcloud/d1-standard-2` is also accepted and stored as written [V].

### 12.2 Full [V]

```yaml
apiVersion: compute.datumapis.com/v1alpha
kind: Workload
metadata: {name: app, namespace: default}
spec:
  template:
    spec:
      runtime:
        class: general-purpose
        resources: {instanceType: datumcloud/d1-standard-2}
        sandbox:
          imagePullSecrets:
            - name: registry-credentials
          containers:
            - name: app
              image: docker.io/library/python:3.12-alpine
              command: ["sh", "-c"]
              args: ["cd /srv && python3 -m http.server 8080 --bind ::"]
              ports: [{name: http, port: 8080}]
              volumeAttachments:
                - {name: app-cfg, mountPath: /cfg}
                - {name: app-sec, mountPath: /sec}
              env:
                - {name: LITERAL, value: "hi"}
                - name: FROM_CONFIGMAP
                  valueFrom: {configMapKeyRef: {name: app-cfg, key: DB_HOST}}
                - name: FROM_SECRET
                  valueFrom: {secretKeyRef: {name: app-sec, key: API_KEY}}
      volumes:
        - {name: app-cfg, configMap: {name: app-cfg}}
        - {name: app-sec, secret: {secretName: app-sec}}
      networkInterfaces:
        - network: {name: default}
  placements:
    - name: main
      locations: [{name: us-central-1}]
      scaleSettings: {minReplicas: 1}
---
apiVersion: networking.datumapis.com/v1alpha
kind: NetworkService
metadata: {name: app, namespace: default}
spec:
  networkInterfaces:
    selector: {matchLabels: {compute.datumapis.com/workload-name: app}}
  ports: [{name: http, port: 8080, protocol: TCP}]
---
apiVersion: v1
kind: ConfigMap
metadata: {name: app-cfg, namespace: default}
data: {DB_HOST: "db.example.com", app.conf: "greeting=hello\n"}
---
apiVersion: v1
kind: Secret
metadata: {name: app-sec, namespace: default}
type: Opaque
stringData: {API_KEY: "..."}      # §7.3
```

Rejected or ignored [D]: container `resources` (`Forbidden: not implemented`), `disk` volumes, more than one container,
`scaleSettings.maxReplicas`, `scaleSettings.metrics`, `networkPolicy` (ignored), a volume no container mounts.

Apply: `datumctl apply -f`, `cat F | datumctl apply -f -`, `compute deploy -f` [V]. Preview: `datumctl diff -f` [C].
Field docs: `datumctl explain workloads.spec.template.spec.runtime` [C].

### 12.3 Pod YAML is not a Workload [V]

```text
$ podman generate kube lab > pod.yaml
$ datumctl apply --dry-run=server --validate=false -f pod.yaml
error: no matches for kind "Pod" in version "v1"
$ datumctl compute deploy -f pod.yaml
Error: Workload ... is invalid: [spec.template.spec.networkInterfaces: Required value, spec.placements: Required value, ...]
# with those added:
admission webhook "vworkload.kb.io" denied the request: spec.template.spec.runtime: Required value: must specify a runtime type
```

- Containers live at `spec.template.spec.runtime.sandbox.containers`; the Pod's `containers` is never read.
- `podman generate kube` copies the host's proxy variables into env. Strip env before reuse.
- `apply` without `--validate=false`: `customresourcedefinitions.apiextensions.k8s.io is forbidden` for a user identity.

## 13. Operate: logs, exec, scale, restart, destroy

**Docs:** [Operations](https://www.datum.net/docs/compute/operations) · [Viewing logs](https://www.datum.net/docs/datumctl/compute/viewing-logs) · [Scaling and operations](https://www.datum.net/docs/datumctl/compute/scaling-and-operations) · [Destroying workloads](https://www.datum.net/docs/datumctl/compute/destroying-workloads) · [Instance shell](https://www.datum.net/docs/compute/instance-shell) · [Observability](https://www.datum.net/docs/compute/observability) · [Activity](https://www.datum.net/docs/datumctl/activity/overview)

| Task | Command | Notes |
|---|---|---|
| Inventory | `compute workloads [--health=degraded] [--location=L]`, `compute instances [--workload=W]` | [C][D] |
| Describe | `compute workloads describe W`, `compute instances describe I` | Reasons live in Instance status [D][V] |
| Logs | `compute logs W --since=15m [--location=L] [--search=err] [-o json]` | `-f` polls. Non-interactive: `--since`, `--tail` [C] |
| Previous generation | `compute logs W --previous` | [C] |
| Access logs | `compute logs W --alb` | [C] |
| Logs after destroy | Kept for the `--since` window, also across a destroy and re-create under the same name (§16.19) | [V] |
| Metrics | Per-Instance CPU and memory | [D] |
| History | `datumctl activity`, `datumctl activity events` | [D] |
| Exec | `compute exec I -it -- sh`, `--ttl` | `general-purpose`, needs `sh` in the image [D] |
| Restart | `compute restart W [--location=L]` | [C] |
| Watch | `compute rollout W` | [C] |
| Scale | `compute scale W --min=N` | [C] |
| Quota | `compute quota [--constrained]` | [C] |
| Delete | `compute destroy W --yes` | [D][V] |

No scale to zero: `minReplicas: Invalid value: 0: must be greater than 0` [V][D]. No suspend, resume or snapshot [D].
No health probes; ready means the container is running [D].

## 14. Local preflight with Podman

**Docs:** [Run a container image](https://www.datum.net/docs/compute/runtimes/general-compute)

Match a `general-purpose` Instance's capability set and no-new-privileges [V]:

```bash
# Podman: its defaults minus SYS_CHROOT
podman run --rm --cap-drop SYS_CHROOT --security-opt no-new-privileges IMAGE
# Docker: its defaults minus four
docker run --rm --cap-drop SYS_CHROOT --cap-drop MKNOD --cap-drop AUDIT_WRITE --cap-drop NET_RAW \
  --security-opt no-new-privileges IMAGE
```

Both give `CapEff: 00000000800005fb`, `NoNewPrivs: 1`, the same as an Instance [V].

Also: bind `::`, use a registry host in the image reference, check `ss -ltn` for `[::]:PORT` [D]. Not a unikernel test [D].

## 15. Errors and their causes

**Docs:** [Compute troubleshooting](https://www.datum.net/docs/compute/troubleshooting)

| Message | Cause | Fix |
|---|---|---|
| `could not be pulled anonymously` on a new workload | Default `unikernel` class, plain image [V] | `--runtime-class=general-purpose` |
| `ImageUnavailable` / "could not be pulled", arm64-only image | No linux/amd64 variant [V] | Build or pull an amd64 image |
| `could not be pulled using credentials from "registry-credentials"` on unikernel | Pushed without packaging (skopeo) [V] | `compute build --push`; `build inspect` |
| `Filesystem: not found` | Same [V] | Same |
| `could not be pulled anonymously`, unikernel, image `Compatible` on ttl.sh | Unknown [V][?] | §16.20 |
| `must include a registry` | No registry host [D] | `docker.io/library/…` |
| `cannot move to "unikernel" … cannot be changed after it is created` | Immutable class [V] | Destroy and redeploy |
| `workload name and --image are required` | Flag deploy without `--image` [V] | Add `--image` |
| `Unsupported value: "nl-west-1": supported values: "us-central-1", "us-east-1", "us-west-1"` | Not a Compute location [V] | Use one of the three |
| `minReplicas: Invalid value: 0: must be greater than 0` | `--min=0`, or manifest without `scaleSettings` [V] | `minReplicas: 1` or more |
| `RuntimeClassNotServed` | Location doesn't serve the class [D] | Another location |
| `NoMatchingLocations` | Selector matches nothing [D] | Fix the selector |
| `resources: Forbidden: not implemented` | Container CPU/memory set [D] | Remove; use `instanceType` |
| `… are not supported by the "CLASS" runtime class` | `disk`, or `envFrom`/capabilities on unikernel [D] | Remove the feature |
| `ReferencedDataNotReady` (`SourceNotFound`, `SourceTooLarge`, `SourceUnauthorized`) | Missing, >256 KiB, or unreadable ConfigMap/Secret [D] | Fix the object |
| `QuotaExceeded`, `QuotaNotGranted` | Quota used up [D] | Fewer Instances, or ask |
| `InstanceCrashing` | Process exits repeatedly [D] | Command, env, mounts; unikernel: `--analyze` |
| `ConfigurationError` | Config refused before start [D] | Env and volume references |
| `Connection refused` on an Instance address | Bound to `0.0.0.0` [V] | Bind `::` |
| `Network unreachable` | IPv4 literal [D][V] | Hostname |
| IPv4-only name fails | App's own resolver, no DNS64 [D] | Use `/etc/resolv.conf` resolvers |
| `503` on a new hostname | Edge or app still starting [D][V] | Wait |
| `sudo`/setuid permission error | no-new-privileges [D][V] | Build-time work, or `allowPrivilegeEscalation: true` |
| `Pending (RuntimeNotReady)`, no logs | Process exited before logging [V] | `instances describe` |
| `no matches for kind "Pod"` | Pod not served [V] | Workload |
| `customresourcedefinitions… forbidden` | Client-side validation [V] | `--validate=false` or `compute deploy -f` |
| `permission denied` on mounts / `workload.yaml` | SELinux [V] | `:Z` |

## 16. Experiments and transcripts

16.1–16.12: 2026-11-11. 16.13–16.20: 2026-11-13, compute plugin v0.12.11, server v1.37.1. Docker side: Debian 12 GCP VM,
Docker 20.10.24, Podman 4.3.1. All test workloads, networks, ConfigMaps, Secrets and VMs deleted afterwards. Images:
`traefik/whoami`, `library/python:3.12-alpine`, `library/caddy:2.8-alpine`. Single runs unless stated.

### 16.1 Default runtime class

| Workload | Stored class | Result |
|---|---|---|
| `lab-default` (no `--runtime-class`) | `unikernel` | `Unavailable`, `Image "docker.io/traefik/whoami:latest" for container "app" could not be pulled anonymously` |
| `lab-gp` | `general-purpose` | `Available` in 14 s, URL `200` |

```text
Error: workload "lab-gp" runs in runtime class "general-purpose" and cannot move to "unikernel",
because a workload's runtime class cannot be changed after it is created. To change it, delete the
workload with 'datumctl compute destroy lab-gp' and deploy it again, or deploy under a new name
```

### 16.2 URL

```text
X-Envoy-External-Address: <client-ip>
X-Forwarded-For: <client-ip>
X-Forwarded-Proto: https
Hostname: lab-gp-default-us-central-1-0
IP: fd20:0:52::2:0:0
```

### 16.3 IPv6 binding

`python3 -m http.server --bind 0.0.0.0` on Instance A; from Instance B to A's IPv6 address: `[Errno 111] Connection refused`.
`--bind ::` answers.

### 16.4 Env, ConfigMap, Secret

```text
FROM_CONFIGMAP=fd20:0:52::1:0:0
FROM_SECRET=key-abc-999
LITERAL_GREETING=hi-from-manifest
/cfg: DB_HOST -> ..data/DB_HOST, app.conf -> ..data/app.conf
/sec (drwxrwxrwt): API_KEY -> ..data/API_KEY, token -> ..data/token
```

### 16.5 Secret rotation, no restart

```text
file token:    lab-secret-value-ROTATED    # updated
file API_KEY:  key-ROTATED-777             # updated
env API_KEY:   key-abc-999                 # unchanged
```

### 16.6 Flag deploy over a manifest

`command`/`args` dropped, two placements became one `default`. Env, imports, mounts kept.

### 16.7 Networks (2026-11-11)

| From → To | Result |
|---|---|
| `default` → `default`, IPv6 | `200` |
| `default` → `lab-net`, IPv6 | timeout |
| `default` → `….instances.datum.internal` | `200` |
| `default` → workload name | no answer |
| `default` → IPv6 internet | connected |
| `default` → IPv4 literal | `Network unreachable` |

Second network: IPAM `fd20:0:2f::/48`.

### 16.8 Build

```text
$ datumctl compute build --analyze -f ./Dockerfile .
  finding entrypoint /usr/local/bin/python3
  running architecture check ... running runtime libraries check ...
note: wrapping the startup command to cd into /srv first (your WORKDIR)
✓ No compatibility issues found
```

### 16.9 `--analyze` / `--fix`

| Dockerfile | Result |
|---|---|
| python, exec-form `CMD`, `ENV HOST=0.0.0.0` | pass |
| shell-form `ENTRYPOINT` | pass |
| `VOLUME`, `HEALTHCHECK`, `USER nobody` | pass |
| `FROM scratch` + python binary only | `missing-libs`; `--fix` adds 3 `COPY` lines, rebuild passes |

### 16.10 Unikernel and skopeo

skopeo-pushed archive: `Incompatible`, `Filesystem: not found`, workload `ImageUnavailable`. Re-pushed with
`compute build --push`: digest equals the archive's, workload `Available`, `200` from another Instance.

### 16.11 Pod YAML

§12.3.

### 16.12 Logs after destroy

```text
$ datumctl compute logs lab-logs --since=10m
Workload "lab-logs" no longer exists; showing the logs it left behind.
[default-us-central-1-0/app] ... Starting up on port 80
$ datumctl compute logs lab-logs --previous
no earlier generation found in the window
```

### 16.13 Kernel, CPU and capabilities in two Instances

```text
$ datumctl compute exec dc-a-default-us-east-1-0 -- sh -c '…'
6.18.35
x86_64
CapEff:     00000000800005fb
CapBnd:     00000000800005fb
NoNewPrivs: 1
uid=0(root) gid=0(root)
model name: AMD EPYC 9355P 32-Core Processor
processors: 2
MemTotal:   4031092 kB
boot_id:    5704b85a-1c7c-4555-b356-0dcb96254d8f        # Instance 1: 4cf24bff-812e-43c9-b3d5-c01cb373b897
[0.000000] Command line: … systemd.unit=kata-containers.target … root=/dev/vda1 …
```

Docker/Podman on the VM, `alpine:3.20`, default flags:

```text
docker  CapEff: 00000000a80425fb  NoNewPrivs: 0  kernel 6.1.0-54-cloud-amd64  boot_id = host's
podman  CapEff: 00000000800405fb  NoNewPrivs: 0  kernel 6.1.0-54-cloud-amd64  boot_id = host's
podman --cap-drop SYS_CHROOT --security-opt no-new-privileges          CapEff: 00000000800005fb  NoNewPrivs: 1
docker --cap-drop SYS_CHROOT,MKNOD,AUDIT_WRITE,NET_RAW --security-opt no-new-privileges   same
```

### 16.14 Addresses

```text
dc-a-default-us-east-1-0          fd20:0:52:1:0:2::/96
dc-a-default-us-east-1-1          fd20:0:52:1:0:3::/96
dc-multi-default-us-central-1-0   fd20:0:52::1:0:0/96
```

`fd20:0:52::1:0:0` was also the address of a 2026-11-11 Instance (§16.4) and of `api-default-us-central-1-0` later on
2026-11-13: addresses are reused. The duplicate address in the 2026-11-11 notes (§16.2, §16.3) is reuse, not an error.

### 16.15 DNS and egress from an Instance

```text
-- github.com (IPv4-only)
64:ff9b::8c52:7204 STREAM github.com
-- ipv4only.arpa
64:ff9b::c000:aa STREAM ipv4only.arpa
-- www.google.com
2001:4860:482c:7700:: STREAM www.google.com
https://github.com/              -> ok
https://www.google.com/          -> ok
https://1.1.1.1/                 -> Network unreachable
https://[64:ff9b::8c52:7004]/    -> TCP + TLS connected (certificate name mismatch, as expected for an address)
-- names
dc-a-default-us-east-1-1                                  -> fd20:0:52:1:0:3::
dc-multi-default-us-central-1-0                           -> fd20:0:52::1:0:0     (IAD → DFW)
dc-multi-default-us-central-1-0.instances.datum.internal  -> fd20:0:52::1:0:0
dc-multi, dc-a (workload names)                           -> no answer
```

### 16.16 Instance type spelling

| Source | Stored `instanceType` | Result |
|---|---|---|
| Flag deploy (default) | `datumcloud-d1-standard-2` | `Available` |
| Manifest, field omitted | `datumcloud-d1-standard-2` | `Available` |
| Manifest, `datumcloud/d1-standard-2` | `datumcloud/d1-standard-2` | `Available` |

### 16.17 Scale to zero, and the minimal manifest

```text
$ datumctl compute deploy dc-zero … --min=0
Error: … spec.placements[0].scaleSettings.minReplicas: Invalid value: 0: must be greater than 0
$ datumctl compute deploy -f min.yaml     # §12.1 without scaleSettings
Error: … spec.placements[0].scaleSettings.minReplicas: Invalid value: 0: must be greater than 0
```

### 16.18 Locations

```text
$ datumctl compute deploy dc-multi … --city=DFW,IAD,AMS
  Placement "default": selector=[topology.datum.net/city-code in (AMS,DFW,IAD)], min=1
  Backends     2 healthy across us-central-1, us-east-1
$ datumctl compute deploy dc-ams … --location=nl-west-1
Error: … spec.placements[0].locations[0].name: Unsupported value: "nl-west-1": supported values: "us-central-1", "us-east-1", "us-west-1"
$ datumctl compute deploy api … --city=DFW,IAD,SJC
  Backends     3 healthy across us-central-1, us-east-1, us-west-1
Rollout complete in 8s.
```

### 16.19 Same tag, label, arm64, logs across re-create

| Action | Boot IDs before → after |
|---|---|
| Redeploy, same image, no other change | `1f04becc…`, `7fc019f6…` → same |
| `--label=team=web` | → `b3aaab14…`, `057b9faa…` (replaced, 28 s) |

`docker.io/arm64v8/nginx:1.27-alpine` on general-purpose: `Unavailable — ImageUnavailable`, "The instance image could not
be pulled".

`whoami` destroyed, then deployed again under the same name; `compute logs whoami --since=10m` showed both generations:

```text
[default-us-east-1-0/app] Nov 14 00:26:52.509  … Starting up on port 80
[default-us-east-1-0/app] Nov 14 00:28:43.510  … Starting up on port 80
[default-us-east-1-0/app] new generation 090aeb0f (replaced or redeployed)
```

### 16.20 Unikernel vs general-purpose start

`FROM docker.io/traefik/whoami:v1.10.3`, built with `compute build --analyze --push` against BuildKit 0.17.3, pushed to
`ttl.sh` (anonymous). `build inspect`: `Compatible`, `kraftcloud/x86_64`, `Filesystem: packaged, 7.3 MiB`.

| Run | general-purpose (`traefik/whoami`) | unikernel (`ttl.sh/…@sha256:20e1af…`) |
|---|---|---|
| 1 | `Rollout complete in 4s` | `ImageUnavailable`, `could not be pulled anonymously` after 5 min |
| 2 | `Rollout complete in 4s` | same |

The unikernel pull failure from ttl.sh is unexplained.

## 17. Limits and open questions

**Docs:** [Limitations and roadmap](https://www.datum.net/docs/compute/limitations-and-roadmap) · [Limits and quotas](https://www.datum.net/docs/compute/limits-and-quotas) · [gVPC limitations](https://www.datum.net/docs/galactic-vpc/limitations-and-roadmap)

- Unikernel start time: not measured (§16.20). Needs a registry the class pulls from.
- Unikernel anonymous pull from ttl.sh: fails with a `Compatible` image. Cause unknown.
- Unikernel fork/exec and egress: undocumented, untested.
- `--http2`, gRPC: untested.
- `--max`, `--cpu-percent`: in the CLI, unsupported per the docs; not tested.
- `compute rollout undo`: suggested by `describe`, absent from the CLI.
- Guest sees 2 CPUs and ~4 GiB; docs say 1 vCPU and 2 GiB. Enforcement not measured.
- Log retention after destroy: not measured.
- Persistent storage: none in the preview [D].

## 18. Sources

- Datum docs: [Compute overview](https://www.datum.net/docs/compute/overview),
  [Run a container image](https://www.datum.net/docs/compute/runtimes/general-compute),
  [Unikernels](https://www.datum.net/docs/compute/runtimes/unikernels),
  [Configuration](https://www.datum.net/docs/compute/configuration),
  [Troubleshooting](https://www.datum.net/docs/compute/troubleshooting),
  [Limitations and roadmap](https://www.datum.net/docs/compute/limitations-and-roadmap),
  [gVPC traffic](https://www.datum.net/docs/galactic-vpc/networks/traffic),
  [Private DNS limits](https://www.datum.net/docs/domain-dns/private-dns-reference),
  [NLB](https://www.datum.net/docs/nlb/overview).
  Several pages are pending in [docs#118](https://github.com/datum-cloud/docs/pull/118),
  [#120](https://github.com/datum-cloud/docs/pull/120) and [#157](https://github.com/datum-cloud/docs/pull/157).
- [How debugging a 503 turned into an IPv6 crash course](https://www.datum.net/blog/ipv6-crash-course).
- CLI help: `datumctl compute <command> --help`.
- [dlotterman/datumctl-container](https://github.com/dlotterman/datumctl-container).
- Docker: [`docker container run`](https://docs.docker.com/reference/cli/docker/container/run/),
  [networking](https://docs.docker.com/engine/network/).
- Podman: [`podman-run(1)`](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
  [`podman-kube-play(1)`](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html).
