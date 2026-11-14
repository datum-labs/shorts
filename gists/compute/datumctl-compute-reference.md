---
title: "Technical reference: datumctl compute for Docker and Podman users"
author: Daniel Lotterman
date: Draft, Nov 2026
---

# Technical reference: datumctl compute for Docker and Podman users

Companion to the short [You already know datumctl compute](../../shorts/datumctl-compute-vs-docker.md). The short is the
picture. This file is everything behind it: the command map, every flag, what changes what, transcripts, errors, and what is
still open.

Every claim carries a tag:

| Tag | Meaning |
|---|---|
| **[V]** | Verified by experiment against a live Datum project (dates in §16) |
| **[D]** | From the Datum docs: [containers](https://www.datum.net/docs/compute/containers), [unikernels](https://www.datum.net/docs/compute/unikernels), [configuration](https://www.datum.net/docs/compute/configuration) |
| **[C]** | From `datumctl ... --help` (CLI text, current `datumctl-container` image) |
| **[N]** | From field notes of earlier real deploys, not re-tested here |
| **[?]** | Open. Not tested, or tested with an unclear result (§17) |

Compute is in preview, and the API is `v1alpha`. Flags, defaults and messages can change. Re-check before relying on any of it.

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

| Concept | Docker / Podman | datumctl compute |
|---|---|---|
| What you run | A container: one process tree on the host kernel | A **Workload**: a declaration, placed in one or more locations, that owns **Instances**. Each Instance is its own small VM [D] |
| Where it runs | The host the engine is on | Datum locations (cities). 16 visible in the test project: DFW, IAD, LGA, SJC, TOR, GRU, SCL, LHR, AMS, FRA, DXB, BOM, SIN, TYO, SYD, JNB [V] |
| Who you talk to | A local daemon (Docker) or no daemon (Podman); `DOCKER_HOST` / `podman --remote` for a remote one | The Datum API, always. `datumctl` is a client like `docker -H` [C] |
| Create and start | `docker run -d IMAGE` | `datumctl compute deploy NAME --image=IMAGE --location=L --runtime-class=general-purpose` [C] |
| Publish | `-p 8080:80`, a host port | `--http-port=80`, a managed HTTPS URL [C][V] |
| Config | `-e`, `--env-file`, `-v` | `--env`, `--env-from-configmap`, `--env-from-secret`, `--configmap`, `--secret` [C] |
| Declarative | `compose.yaml`; `podman kube play pod.yaml` | `datumctl compute deploy -f workload.yaml` or `datumctl apply -f` (Kubernetes-shaped `apiVersion/kind/spec`) [C][V] |
| Image | Any OCI image | Any OCI image on `general-purpose` [D][V]. A packaged image on `unikernel` [D][V] |
| Kernel | Shared with the host | One per Instance [D] (see §17 for what was measured) |
| Address family | IPv4 by default, IPv6 opt-in | IPv6 only [D][V] |

The default `runtime-class` is **not** `general-purpose`. See §5.

## 2. Command map

| Docker | Podman | datumctl | Notes |
|---|---|---|---|
| `docker login` | `podman login` | `datumctl login` | Signs in to Datum. Registry sign-in is a Secret, §10 [C] |
| `docker context use` | `podman system connection default` | `datumctl ctx` | Switches org/project context [C] |
| `docker run -d IMAGE` | `podman run -d IMAGE` | `datumctl compute deploy NAME --image=IMAGE --location=L --runtime-class=general-purpose --yes` | Returns after the rollout [V] |
| `docker run -it --rm IMAGE sh` | same | none | No one-off interactive run. Deploy, then `compute exec` [?] |
| `docker ps` | `podman ps` | `compute workloads`, `compute instances` | `--health=degraded` filters [C] |
| `docker inspect` | `podman inspect` | `compute workloads describe NAME`, `compute instances describe NAME`, `-o yaml` | `describe` shows env sources, not values [V] |
| `docker logs -f C` | `podman logs -f C` | `compute logs NAME -f --since=15m` | Merged across Instances. Polls, does not stream. `--alb` for access logs [C][V] |
| `docker exec -it C sh` | `podman exec -it C sh` | `compute exec INSTANCE -it -- sh` | Takes an Instance name, not a Workload name. `-c` picks a container. `--ttl` 1m–1h, default 15m [C][V] |
| `docker restart C` | `podman restart C` | `compute restart NAME [--location=L]` | Rolling [C] |
| `docker rm -f C` | `podman rm -f C` | `compute destroy NAME --yes` | Removes Instances and URLs. Secrets, ConfigMaps and custom domains stay [D][V] |
| `docker build -t T .` | `podman build -t T .` | `compute build .` | Default is a local check. Publishes nothing [C] |
| `docker push T` | `podman push T` | `compute build --push --output REG/IMG:TAG .` | Packages for unikernel. A plain push of the archive does not [V] |
| `docker build -o type=tar` | `podman save` | `compute build --output ./img.tar .` | OCI archive [C] |
| `docker compose up --scale web=3` | `podman-compose up --scale` | `compute scale NAME --min=N --max=M` | Per location. `--max=0` disables autoscaling [C] |
| `docker compose -f c.yaml up` | `podman kube play pod.yaml` | `compute deploy -f workload.yaml` / `datumctl apply -f` | Workload kind only. Pod YAML is refused, §12 [V] |
| `docker network create N` | `podman network create N` | `datumctl apply -f network.yaml`, or let `deploy --network=N` offer to create it | §11 [C][V] |
| `docker stats` | `podman stats` | none found [?] | `compute quota` shows quota, not usage [C] |
| `docker cp` | `podman cp` | none found [?] | Use a ConfigMap, a Secret or the image |
| `docker events` | `podman events` | `compute rollout NAME` | Watches one rollout live [C] |
| `docker pull` | `podman pull` | none: Instances pull at start | A new tag or digest is the refresh, §8 [V] |
| `docker port C` | `podman port C` | URL is the last line of `deploy`; `compute workloads` lists it [V] | |
| `docker version` | `podman version` | `datumctl version` | Shows client and API server versions [C] |
| plugins (`docker compose`, `docker buildx`) | `podman` extensions | `datumctl plugin` | Same idea: subcommands from separate binaries [C] |

kubectl-shaped verbs come with it too: `get`, `describe`, `apply`, `diff`, `edit`, `patch`, `label`, `annotate`, `delete`,
`explain`, `api-resources` [C]. No Kubernetes knowledge is required to use `compute` [C].

## 3. The CLI is a client

- `datumctl` talks to the Datum API, the way `docker` talks to `dockerd` and `podman --remote` talks to a Podman service [C].
- Contexts: `datumctl ctx` lists and switches org/project, like `docker context` [C]. `--org` and `--project` override per
  command [C]. `DATUM_SESSION` runs one command as another signed-in account [C].
- CI: `datumctl login --credentials ./key.json` signs in as a service account [C].
- Access: `datumctl compute access` must say `Active` before anything else works. `compute access request` asks for it [C][V].
- Plugins: `datumctl plugin` manages plugin binaries, the same model as Docker CLI plugins [C].
- Running it in a container: [dlotterman/datumctl-container](https://github.com/dlotterman/datumctl-container) packages the CLI
  as an image. It is what every transcript here used [V]:

```bash
podman run --rm -i -v datumctl-config:/root/.datumctl docker.io/dlotterman/datumctl-container:latest compute workloads
```

Container notes [V]:
- The entrypoint is `datumctl`. Use `--entrypoint sh` to look inside.
- Login state lives in the named volume (`datumctl-config` above).
- On SELinux hosts, bind mounts need `:Z` (`-v "$PWD":/work:Z`), or reads fail and `workload.yaml` writes fail with
  `permission denied`, even as root.
- `--http-proxy=false` if the host's proxy variables point somewhere the container can't reach.

## 4. Deploy: flags and semantics

### 4.1 Flags, with Docker equivalents [C]

| datumctl compute deploy | Docker / Podman | Meaning |
|---|---|---|
| `NAME` (positional) | `--name` | Workload name. Immutable [V] |
| `--image` | `IMAGE` | Needs a registry host: `docker.io/library/python:3.12-alpine`, not `python:3.12-alpine` [D]. Required on every flag deploy, even to an existing workload [V] |
| `--location=a,b` | none | One or more locations |
| `--city=DFW,IAD` | none | Every location in those cities. Shorthand for a selector on `topology.datum.net/city-code` |
| `--location-selector='…'` | none | Any topology label selector, e.g. `topology.datum.net/region in (us-east-1,eu-west-1)` |
| `--runtime-class` | none (closest: `--runtime`) | `general-purpose` or `unikernel`. Default is the platform default, which is `unikernel` [V]. Immutable |
| `--network` | `--network` | Default `default`. Immutable. Offers to create a missing network |
| `--http-port` | `-p H:C` | Publishes a managed HTTPS URL; the app gets plain HTTP |
| `--http2` | none | The container speaks HTTP/2 on `--http-port` (gRPC). Every request reaches it as HTTP/2. Sticky until `--http2=false` |
| `--no-http` | remove `-p` | Removes the HTTP service and the URL datumctl published |
| `--env K=V` / `K-` | `-e K=V` | Set or remove one variable |
| `--env-from-configmap NAME[:PREFIX_]` | `--env-file` | Import every key; `NAME-` removes the import |
| `--env-from-secret NAME[:PREFIX_]` | `--env-file` | Same, from a Secret |
| `--configmap NAME:/path` / `NAME-` | `-v` | Mount keys as files |
| `--secret NAME:/path` / `NAME-` | `-v` / `--secret` (Podman) | Mount keys as files |
| `--label k=v` / `k-` | `--label` | On the Workload **and** its Instances. Setting one **replaces the Instances** |
| `--instance-type` | `--cpus`, `--memory` | Default `datumcloud-d1-standard-2` (1 vCPU, 2 GiB [D]). The only type documented |
| `--min` | `--scale` | Minimum Instances **per location**. Default 1 |
| `--max` | none | Autoscaling ceiling. `0` disables autoscaling |
| `--cpu-percent`, `--memory-percent` | none | Autoscaling targets. `0` removes the metric |
| `--build[=DIR]` | `docker build && docker push && docker run` | Builds, pushes to `--image`, deploys that **digest**. Also applies `--fix`, which **rewrites the Dockerfile in place** |
| `-f FILE` | `compose -f`, `kube play` | Manifest deploy, §12 |
| `-y, --yes` | none | Skip confirmations |
| (no args) | none | Interactive prompts |

Not offered [C]: `--platform`, `--restart`, `--health-cmd`, `--init`, `--user`, `--read-only`, `--cap-add`, `--pull`,
`--entrypoint`, `--command`. Command and args are manifest-only.

### 4.2 Carry-forward

- A deploy that does not mention an env var, an import, a mount or a label keeps it [C][V]. A routine image bump changes
  nothing else. Remove with a trailing `-`. Docker's `run` always starts fresh; this is closer to `compose up` on an edited file.
- **What does not carry forward [V]:** a flag deploy on a manifest-defined workload rewrites the container from flags. It
  dropped `command` and `args` (PID 1 became the image's default), and collapsed two placements into one called `default`.
- A flag deploy removes registry credentials [D]. Use `-f` for private images.
- Don't mix flag and manifest deploys on one workload. Pick one.
- Omitting `--http-port` on an existing workload keeps its port and never publishes a new URL [C].
- Flag deploys write `workload.yaml` into the current directory [D]. Don't commit it.

### 4.3 Many places from one command

```bash
datumctl compute deploy api --image=ghcr.io/acme/api:1.4.2 --city=DFW,IAD,AMS --http-port=8080 --runtime-class=general-purpose --yes
```

One Workload, one placement per location, `--min` Instances in each, one URL [C]. `docker run` has no equivalent: the
closest is running the same compose file on three hosts and putting a load balancer in front.

Instance names follow `<workload>-<placement>-<location>-<n>`, e.g. `lab-env-us-central-us-central-1-0` [V]. With flags,
the placement is named `default` [V].

## 5. Runtime classes

|  | general-purpose | unikernel |
|---|---|---|
| Default? | No | **Yes**, the platform default [V] |
| Image | Any OCI image, unchanged [D][V] | Must be packaged by `compute build` [D][V] |
| Build step | Optional: `docker build`/`podman build` + push work [D] | Required [D] |
| Arch | x86_64 hosts; arm64-only images [?] (§17) | x86_64 only [D] |
| Memory | 2 GiB Instance | Root filesystem lives in memory and counts against the 2 GiB [D] |
| Capabilities | All dropped, then a class default adds some back (CHOWN, NET_BIND_SERVICE, SETUID and others). A custom list replaces the default [D]. Measured set: §16.13 | None can be added; `securityContext` has no effect [D] |
| Dynamic loading | Normal | Everything loaded at runtime must be in the image, including `dlopen` plugins [D] |
| `envFrom` | Yes [D] | No; use `env[].valueFrom` [D] |
| `sudo`/`su`/setuid | Fail [D]; `chown` at build time | n/a |
| Startup | Seconds (14 s to `Available` in one run [V]) | "A fraction of a second" [D]; not measured here [?] |
| Debugging | Logs and exec | Logs and exec; crash detail is thin. Stuck in `Starting` means run `compute build --analyze` [D] |
| Local test | Same image under Podman with the Datum restrictions, §14 | A container run is not a unikernel test [D] |
| Change later? | No. Destroy and redeploy, or use a new name [V] | Same |

Unknown for unikernel: fork/exec, and internet egress [?].

Field note [N]: the same app run on both classes in one shared project answered 20 of 20 on general-purpose and 11 of 20 on
unikernel. One project, one run.

## 6. Ports, URLs and protocols

- `--http-port=P` gives `https://<random-words>.datumproxy.net`, printed as the last line of `deploy` [C][V].
- TLS ends at Datum's edge with a certificate Datum manages. The app gets plain HTTP on port P [D][V].
- The app must listen on IPv6. Bind `::` (Python `--bind ::`, Node `HOST=::`). A `0.0.0.0` listener refuses connections on
  the Instance's IPv6 address [V]. The `HOST=0.0.0.0` default in many Dockerfiles starts but never answers [N].
- Headers the app sees [V]: `X-Forwarded-For` and `X-Envoy-External-Address` (the client), `X-Forwarded-Proto: https`. The
  edge is Envoy.
- A brand-new hostname can return `503` from the edge for about a minute while the Workload already says `Available` [V].
  Resolve through a public resolver (1.1.1.1) and retry.
- gRPC and anything else HTTP/2: `--http2` [C]. Not tested here [?].
- Non-HTTP ports: a `NetworkService` gives other Instances a port without a URL (§12) [V]. Public TCP is the Network Load
  Balancer, in early access, out of scope here.
- Basic auth is set in the console and applies to the whole URL, including health paths. A `destroy` changes the URL and drops
  the basic auth [N].
- Custom hostnames: an `HTTPProxy` with a hostname. Attaching one adds an ALIAS record in the zone [N]. Custom domains outlive
  `destroy` [D].
- WAF: a `TrafficProtectionPolicy` with the OWASP CRS, manifest only [N].

## 7. Environment, ConfigMaps and Secrets

### 7.1 How to set them

| You want | Flag | Manifest |
|---|---|---|
| One literal | `--env K=V` | `env: [{name: K, value: V}]` |
| One key from a ConfigMap | none | `valueFrom: {configMapKeyRef: {name, key}}` |
| One key from a Secret | none | `valueFrom: {secretKeyRef: {name, key}}` |
| Every key | `--env-from-configmap NAME`, `--env-from-secret NAME[:PREFIX_]` | `envFrom` (general-purpose only [D]) |
| Files | `--configmap NAME:/path`, `--secret NAME:/path` | `volumes` + `volumeAttachments` |

ConfigMaps and Secrets are ordinary Kubernetes-shaped objects (`apiVersion: v1`), created with `datumctl apply -f` [V].
Limits [D]: 256 KiB per object, 1 MiB per location in total.

### 7.2 When they take effect [V]

| Change | Running Instance sees it? |
|---|---|
| Edit a Secret or ConfigMap mounted as **files** | **Yes, in place.** Kubernetes atomic-writer layout (`key -> ..data/key`) |
| Edit a Secret or ConfigMap used as **env** | **No.** Env is read when the Instance starts. `compute restart NAME` |
| Change `registry-credentials` | No. Restart [V] |

Docker comparison: `-v` bind mounts are also live, and `-e` is also fixed at start, so the split is familiar. What is new is
that the config is an object with a name, not a file on a host.

### 7.3 Secret handling gotchas

- **`apply` stores plaintext [V].** `kubectl.kubernetes.io/last-applied-configuration` keeps `stringData` verbatim, while
  `data` is base64. `datumctl get secret NAME -o yaml` shows both to anyone who can read the Secret. Use `create` or
  `data:` (base64) for anything sensitive, and don't `apply` secrets from a shared terminal.
- The Secret mount directory is `drwxrwxrwt` (world-writable, sticky) [V]. The key files are symlinks into `..data`.
- Values must be valid text. Raw bytes from the console form broke Instances with `ConfigurationError` [N]. Create Secrets
  from the CLI and keep values ASCII, single-line except PEM.
- Manifest field names differ: `configMap: {name: …}` but `secret: {secretName: …}` [V][D].

## 8. What changes what

| You change | What happens | Docker habit it replaces |
|---|---|---|
| Image tag, same tag as before | **Nothing.** The Instance keeps running, its age keeps counting [V] | `docker pull && docker restart` refreshes `:latest` |
| Image tag, new tag | Rolling replacement [V] | `docker run` new tag |
| Image by digest (`@sha256:`) | Rolling replacement; recommended [N]. `deploy --build` pins by digest [C] | |
| `--env` | Rolling replacement [V] | `docker run -e` again |
| Mounted ConfigMap or Secret content | Live in the files, no restart [V] | Edit the bind-mounted file |
| ConfigMap or Secret used as env | Nothing until `compute restart` [V] | |
| `--label` | Replaces Instances [C] | Labels on a running container are fixed too |
| `--min`, `--max` | Adds or removes Instances [C] | `--scale` |
| `--location` / `--city` | Adds or removes placements [C][V] | |
| `--runtime-class` | **Refused.** Destroy and redeploy [V] | |
| `--network` | **Refused.** Destroy and redeploy [C] | `docker network connect` works live |
| Workload name | Can't. Destroy and redeploy [V] | `docker rename` |
| `compute restart` | Rolling restart [C] | `docker restart` |

Rollouts are `OrderedReady` [N]: a failed Instance blocks the next one. Users can't delete a single Instance (`Forbidden`) [N];
destroy the Workload.

## 9. Build

```bash
datumctl compute build .                         # local check only, nothing saved
datumctl compute build --analyze -f Dockerfile . # check the built entrypoint
datumctl compute build --fix .                   # apply exact-line Dockerfile fixes, rebuild (edits in place)
datumctl compute build --output ./img.tar .      # OCI archive
datumctl compute build --push --output ghcr.io/USER/app:1 .   # push, no confirmation
datumctl compute build inspect IMAGE --extended  # check a pushed image
datumctl compute deploy api --build --image=ghcr.io/USER/app:1 --location=us-east-1   # build + push + deploy by digest
```

- Input is a plain Dockerfile and context. `Dockerfile.datum` wins over `Dockerfile` if both exist [C].
- Runs on BuildKit: your engine's (Docker, OrbStack, Colima; honours `DOCKER_HOST`) or `--buildkit-host` [C]. The container
  image defaults to `BUILDKIT_HOST=tcp://buildkitd:1234`; point it at a real one with `-e BUILDKIT_HOST=tcp://HOST:1234` [V].
  Rootless BuildKit inside rootless Podman failed on `newuidmap` [V].
- `--build-arg` and `--target` work as in Docker [C]. `deploy --build` doesn't take them [C].
- Reproducible: same files, same digest. Set `SOURCE_DATE_EPOCH` if a step stamps the time [C].
- linux/amd64 only. No `--platform` [D][C].
- **What `--analyze` catches [V]:** missing runtime libraries in a `FROM scratch` image, with the exact `COPY` lines:

```text
error[missing-libs]: /usr/local/bin/python3 requires 3 runtime files that are not present in the image
  --> Dockerfile:3
  | + COPY --from=src /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
  | + COPY --from=src /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/libpython3.12.so.1.0
  | + COPY --from=src /lib/libc.musl-x86_64.so.1 /lib/libc.musl-x86_64.so.1
tip: rerun with --fix to apply the suggested Dockerfile edits automatically
```

- **Not flagged [V]:** `VOLUME`, `HEALTHCHECK`, `USER nobody`, shell-form `ENTRYPOINT`, `ENV HOST=0.0.0.0`. The last one will
  still break the app (§6).
- **`--fix` rewrites the Dockerfile in place, with no backup [V].** The diff was exactly the three `COPY` lines. Run it on a
  copy or a clean git tree. `deploy --build` does the same [C].
- **Push with `compute build --push`, not `skopeo copy` from the archive [V].** skopeo pushed a plain manifest without the
  packaged filesystem; the unikernel class then reported it as a pull failure. `build inspect` tells them apart:

```text
# skopeo-pushed                      # datumctl-pushed
Status:   Incompatible               Status:   Compatible
Package:  Filesystem: not found      Platform: kraftcloud/x86_64
                                     Filesystem: packaged, 50.7 MiB
```

- Push and `build inspect` read registry sign-ins from a Docker-style config inside the container. Mount a private copy:
  `-v COPY_OF_AUTH:/root/.docker/config.json:ro,Z` [V].

## 10. Registry credentials

```yaml
apiVersion: v1
kind: Secret
metadata: {name: registry-credentials, namespace: default}
type: kubernetes.io/dockerconfigjson
stringData:
  .dockerconfigjson: |
    {"auths":{"ghcr.io":{"username":"USER","password":"READ_ONLY_TOKEN"}}}
```

- Reference it under `spec.template.spec.runtime.sandbox.imagePullSecrets` [D].
- ghcr.io: a token with `read:packages` to pull, `write:packages` to push [V].
- Podman's `auth.json` shape (a base64 `auth` field) also worked on general-purpose [V]. Use the documented shape.
- Instances read it at start. Restart after changing it [V].
- Flag deploys drop it [D]. Use `-f`.
- Without it, pulls are anonymous [D].

## 11. Networks, DNS and egress

The default network, as stored [V]:

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

| Fact | Tag |
|---|---|
| A network spans locations: Instances in different cities reach each other privately | [N] |
| Another network is the same object with another name; IPAM picks a new `/48` | [V] |
| Attach at create time only (`--network`). One interface per workload with flags; more needs a manifest | [C][V] |
| Same network, by IPv6 literal: works | [V] |
| Same network, by `<instance>.instances.datum.internal`: works | [V] |
| Same network, by workload name: does **not** resolve | [V] |
| Different networks: isolated (connection timed out) | [V] |
| Egress to an IPv6 internet address: works | [V] |
| Egress to an IPv4 address: `Network unreachable` | [V] |
| DNS for public names: AAAA answers come back | [V] |
| NAT64 / DNS64 for IPv4-only names (e.g. github.com) | [?] §16.15 |
| MTU 1440 | [V] |

Docker comparison [V], Docker 20.10 on a Debian 12 VM:

```text
# user-defined bridge appnet: name resolution works
wget http://svc-a/    -> 200
# svc-iso on another network, called from appnet
wget http://svc-iso/  -> bad address 'svc-iso'
# default bridge, by name
wget http://svc-def/  -> bad address 'svc-def'
```

Docker resolves container names only inside a user-defined network on one host. Datum resolves Instance names across a
network that spans locations, and the platform enforces the boundary between networks.

## 12. Manifests

### 12.1 Workload, verified on general-purpose [V]

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
          imagePullSecrets:                    # private images only
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
        - {name: app-sec, secret: {secretName: app-sec}}   # secretName, not name
      networkInterfaces:
        - network: {name: default}
  placements:                                  # under spec, not top level
    - name: main
      locations: [{name: us-central-1}]
      scaleSettings: {minReplicas: 1}
---
apiVersion: networking.datumapis.com/v1alpha
kind: NetworkService                           # a port for other Instances, no public URL
metadata: {name: app, namespace: default}
spec:
  networkInterfaces:
    selector: {matchLabels: {compute.datumapis.com/workload-name: app}}
  ports: [{name: http, port: 8080, protocol: TCP}]
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata: {name: app-cfg, namespace: default}
data: {DB_HOST: "fd20:0:52::1:0:0", app.conf: "greeting=hello\n"}
---
apiVersion: v1
kind: Secret
metadata: {name: app-sec, namespace: default}
type: Opaque
stringData: {API_KEY: "..."}      # see §7.3 before using stringData with apply
```

Apply: `datumctl apply -f FILE`, `cat FILE | datumctl apply -f -`, or `datumctl compute deploy -f FILE` [V]. Preview:
`datumctl diff -f FILE` [C]. Field docs: `datumctl explain workloads.spec.template.spec.runtime` [C].

The instance type is written `datumcloud/d1-standard-2` in stored manifests and `datumcloud-d1-standard-2` in the flag's help
text. See §16.16.

### 12.2 Pod YAML is not a Workload [V]

```text
$ podman generate kube lab > pod.yaml
$ datumctl apply --dry-run=server --validate=false -f pod.yaml
error: no matches for kind "Pod" in version "v1"
$ datumctl compute deploy -f pod.yaml
Error: Workload ... is invalid: [spec.template.spec.networkInterfaces: Required value, spec.placements: Required value, ...]
# with those added:
admission webhook "vworkload.kb.io" denied the request: spec.template.spec.runtime: Required value: must specify a runtime type
```

The server never reads the Pod's `containers`. Containers live at `spec.template.spec.runtime.sandbox.containers`. Same
`apiVersion/kind/metadata/spec` shape, different kind: rewrite by hand from §12.1.

Also: `podman generate kube` copied the host's proxy variables into the Pod's env. Strip env from generated YAML before reuse.

`apply` without `--validate=false` failed with `customresourcedefinitions.apiextensions.k8s.io is forbidden` for a user
identity, so client-side validation of any kind doesn't work [V].

## 13. Operate: logs, exec, scale, restart, destroy

| Task | Command | Notes |
|---|---|---|
| Inventory | `compute workloads [--health=degraded]`, `compute instances [--workload=NAME]` | [C] |
| Describe | `compute workloads describe NAME`, `compute instances describe NAME` | Status conditions are where `RuntimeNotReady` reasons live [V] |
| Logs | `compute logs NAME --since=15m [--location=L] [--search=err] [-o json]` | Polls every couple of seconds with `-f`. Agents: use `--since`/`--tail`, not `-f` [C] |
| Previous generation | `compute logs NAME --previous` | [C] |
| Access logs | `compute logs NAME --alb` | [C] |
| Logs after destroy | Still returned for the `--since` window: `Workload "NAME" no longer exists; showing the logs it left behind.` Retention not measured | [V] |
| Exec | `compute exec INSTANCE -it -- sh`, `-c CONTAINER`, `--ttl=15m` | [C][V] |
| Restart | `compute restart NAME [--location=L]` | Rolling [C] |
| Watch | `compute rollout NAME` | [C] |
| Scale | `compute scale NAME --min=N --max=M --cpu-percent=P` | Per location [C] |
| Quota | `compute quota [--constrained]` | [C] |
| Delete | `compute destroy NAME --yes` | URL and Instances go; Secrets, ConfigMaps, custom domains stay [D][V] |

Scale to zero: see §16.17.

## 14. Local preflight with Podman

Run the image under restrictions close to general-purpose before deploying [D]:

```bash
podman run -d --name preflight --security-opt no-new-privileges --cap-drop ALL \
  --cap-add CHOWN,NET_BIND_SERVICE,SETUID,SETGID \
  -p '[::1]:18080:8080' IMAGE
curl -s "http://[::1]:18080/"
```

Use the capability set measured on a real Instance (§16.13) rather than this list if they differ. Also bind the app to `::`,
and use an image reference with a registry host. None of this exercises the unikernel class [D].

## 15. Errors and their causes

| Message | Cause | Fix |
|---|---|---|
| `could not be pulled anonymously` on a new workload | No `--runtime-class`, so the unikernel default; a plain image isn't a unikernel package [V] | `--runtime-class=general-purpose`, or build with `compute build` |
| `could not be pulled using credentials from "registry-credentials"` on unikernel | Image pushed without packaging (skopeo) [V] | `compute build --push`; check `build inspect` |
| `Filesystem: not found` / `packaged filesystem layer was not found` | Same [V] | Same |
| `cannot move to "unikernel" … cannot be changed after it is created` | Runtime class is immutable [V] | Destroy and redeploy, or a new name |
| `workload name and --image are required` | Flag deploy without `--image` [V] | Add `--image` |
| `Unsupported value: "us-central-1"` | Locations not provisioned for the project yet [N] | Wait until `datumctl get locations` lists them |
| `Connection refused` on an Instance's IPv6 address | App bound to `0.0.0.0` [V] | Bind `::` |
| `Network unreachable` | IPv4 destination; egress is IPv6 only [V] | Use IPv6 destinations |
| `503` from a new `*.datumproxy.net` for ~1 min | Edge still programming [V] | Retry |
| `Pending (RuntimeNotReady)` and no logs | Process exited before logging [V] | `compute instances describe`; run the image locally |
| `Forbidden` deleting an Instance | Users can't delete Instances [N] | Destroy the Workload |
| `ConfigurationError` | A Secret value isn't valid text [N] | Recreate it from the CLI |
| `permission denied` on `workload.yaml` or a mount | SELinux label [V] | `:Z` on the mount |
| `no matches for kind "Pod"` | Pod isn't served [V] | Workload manifest |
| `customresourcedefinitions.apiextensions.k8s.io is forbidden` | Client-side validation [V] | `--validate=false`, or `compute deploy -f` |
| Command didn't run after a flag deploy | Flag deploy dropped manifest `command`/`args` [V] | Re-apply the manifest |

## 16. Experiments and transcripts

Experiments 16.1–16.12 ran on 2026-11-11 against a test project, plus a Debian 12 GCP VM with Docker 20.10.24 and
Podman 4.3.1. Every workload, network, ConfigMap and Secret was deleted afterwards. Images: `docker.io/traefik/whoami`
(listens on every address, port 80) and `docker.io/library/python:3.12-alpine`. Single runs unless stated.

### 16.1 The default runtime class

```bash
datumctl compute deploy lab-default --image=docker.io/traefik/whoami:latest --location=us-central-1 --http-port=80 --yes
datumctl compute deploy lab-gp --image=docker.io/traefik/whoami:latest --location=us-central-1 --runtime-class=general-purpose --http-port=80 --yes
```

| Workload | Stored `runtime.class` | After 4 min | Reason |
|---|---|---|---|
| `lab-default` | `unikernel` (platform default) | `Unavailable`, 0/1 | `Image "docker.io/traefik/whoami:latest" for container "app" could not be pulled anonymously` |
| `lab-gp` | `general-purpose` | `Available` 1/1 after 14 s; URL returned `200` | |

A public GHCR image on the default class fails with the identical text. Changing the class afterwards:

```text
Error: workload "lab-gp" runs in runtime class "general-purpose" and cannot move to "unikernel",
because a workload's runtime class cannot be changed after it is created. To change it, delete the
workload with 'datumctl compute destroy lab-gp' and deploy it again, or deploy under a new name
```

### 16.2 The URL

```text
GET / HTTP/1.1
X-Envoy-External-Address: <client-ip>
X-Forwarded-For: <client-ip>
X-Forwarded-Proto: https
Hostname: lab-gp-default-us-central-1-0
IP: fd20:0:52::2:0:0
```

### 16.3 IPv6 binding

```python
# Instance A: python3 -m http.server 8080 --bind 0.0.0.0
# Instance B, same network, to A's IPv6 address:
urllib.request.urlopen('http://[<A-ipv6>]:8080/')
# -> URLError: [Errno 111] Connection refused
```

Same server with `--bind ::` answers. (The 2026-11-11 notes recorded the same address for A as for `lab-gp` in 16.2;
re-checked in 16.14.)

### 16.4 Env, ConfigMap and Secret in one Instance

Workload: §12.1 with a command that dumps what it got. Read back with `compute exec`:

```text
FROM_CONFIGMAP=fd20:0:52::1:0:0
FROM_SECRET=key-abc-999
LITERAL_GREETING=hi-from-manifest
--- /cfg
DB_HOST -> ..data/DB_HOST
app.conf -> ..data/app.conf
--- /sec   (drwxrwxrwt)
API_KEY -> ..data/API_KEY
token -> ..data/token
```

### 16.5 Rotating a Secret without a restart

```text
file token:    lab-secret-value-ROTATED    # file: updated in place
file API_KEY:  key-ROTATED-777             # file: updated in place
env API_KEY:   key-abc-999                 # env: still the start-time value
```

### 16.6 Flag deploy over a manifest deploy

`compute deploy lab-env --image=… --configmap=… --secret=… --http-port=8080` after a manifest deploy dropped `command` and
`args` (the server never started), and turned two placements into one named `default`. Env, imports and mounts survived.

### 16.7 Networks

| From → To | Result |
|---|---|
| `default` → `default`, IPv6 literal | `200` |
| `default` → `lab-net`, IPv6 literal | timeout |
| `default` → `lab-gp-default-us-central-1-0.instances.datum.internal` | `200` |
| `default` → `lab-gp` (workload name) | no answer from `getent` |
| `default` → an IPv6 internet address | `403` from a Cloudflare address: connected |
| `default` → an IPv4 literal; `www.datum.net` over IPv4 | `Network unreachable` |

Second network: same `Network` object, IPAM gave `fd20:0:2f::/48`.

### 16.8 Build

```dockerfile
FROM docker.io/library/python:3.12-alpine
WORKDIR /srv
COPY index.html /srv/index.html
EXPOSE 8080
CMD ["python3", "-m", "http.server", "8080", "--bind", "::"]
```

```text
$ datumctl compute build --analyze -f ./Dockerfile .
Analyzing image filesystem ...
  finding entrypoint /usr/local/bin/python3
  running architecture check ... running runtime libraries check ...
note: wrapping the startup command to cd into /srv first (your WORKDIR)
✓ No compatibility issues found
Preview complete. The image wasn't saved: add --output ./work.tar to save it,
or --output <registry>/<account>/work:latest to push it.
```

### 16.9 `--analyze` on other Dockerfiles

| Dockerfile | `--analyze` |
|---|---|
| python image, exec-form `CMD`, `ENV HOST=0.0.0.0` | pass |
| shell-form `ENTRYPOINT python3 …` | pass |
| `VOLUME`, `HEALTHCHECK`, `USER nobody` | pass |
| `FROM scratch` + `COPY --from=src /usr/local/bin/python3` | **fail: `missing-libs`**, §9 |

`--fix` added the three lines after line 3, nothing else, rebuilt, and the second analysis passed.

### 16.10 Unikernel: the skopeo push

Built with `compute build --output ./unikernel-image.tar`, pushed with `skopeo copy oci-archive:…`. The workload sat at
`Unavailable — ImageUnavailable`, `could not be pulled using credentials from "registry-credentials"`, though the same
credentials pulled on general-purpose. `build inspect` on the pushed image: `Incompatible`, `Filesystem: not found`. Pushed
again with `compute build --push --output ghcr.io/USER/lab-unikernel:2 .`: pushed digest equals the archive digest, workload
`Available`, `curl http://[<ipv6>]:8080/` from another Instance returns `200`.

### 16.11 Pod YAML

Transcript in §12.2.

### 16.12 Logs after destroy

```text
$ datumctl compute destroy lab-logs --yes
$ datumctl compute logs lab-logs --since=10m
Workload "lab-logs" no longer exists; showing the logs it left behind.
[default-us-central-1-0/app] ... Starting up on port 80
$ datumctl compute logs lab-logs --previous
no earlier generation found in the window
```

### 16.13 Capabilities inside a general-purpose Instance

Pending (2026-11-13 run).

### 16.14 Kernel per Instance, and address reuse

Pending (2026-11-13 run).

### 16.15 IPv4-only destinations (NAT64 / DNS64)

Pending (2026-11-13 run).

### 16.16 Instance type spelling

Pending (2026-11-13 run).

### 16.17 Scale to zero

Pending (2026-11-13 run).

### 16.18 Multi-location deploy

Pending (2026-11-13 run).

## 17. Limits and open questions

- arm64-only images on general-purpose: not tested. Builds are amd64 only.
- Unikernel boot time vs general-purpose: not measured.
- Unikernel fork/exec and internet egress: undocumented, untested.
- `HEALTHCHECK`: not flagged by `--analyze`; whether the platform honours it is unknown.
- `--http2` and gRPC: not tested.
- Persistent storage: Instance storage is ephemeral [N]. No volume type beyond ConfigMap and Secret was found.
- `docker stats`, `docker cp`, `docker run -it --rm`: no equivalent found.
- Log retention after destroy: not measured.
- Pricing: not measured. Compute is free during the beta.

## 18. Sources

- Datum docs: [containers](https://www.datum.net/docs/compute/containers),
  [unikernels](https://www.datum.net/docs/compute/unikernels),
  [configuration](https://www.datum.net/docs/compute/configuration).
- CLI help: `datumctl compute <command> --help`, no login needed.
- The CLI in a container: [dlotterman/datumctl-container](https://github.com/dlotterman/datumctl-container).
- Docker: [`docker container run`](https://docs.docker.com/reference/cli/docker/container/run/),
  [networking](https://docs.docker.com/engine/network/).
- Podman: [`podman-run(1)`](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
  [`podman-kube-play(1)`](https://docs.podman.io/en/latest/markdown/podman-kube-play.1.html).
