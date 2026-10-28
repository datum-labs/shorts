# Use ALB as your HTTP proxy: reference

<!-- OUTLINE. Companion page to the datum.net guide "Use ALB as your HTTP proxy" (guides/alb-as-httpd).
     Section names match the guide. Bullets are the tested facts to expand; "Example to add" marks a YAML or CLI block to write.
     Tag each fact when expanded: [tested 2026-10-28], [docs], or [docs, contradicted by test]. -->

## About this reference

- Scope: replacing an NGINX, Apache httpd, Caddy, or Traefik container that fronts an app on Datum Compute
- Basis: Datum docs plus live tests in one project on 2026-10-28, datumctl v0.23.0, alb plugin v0.32.31
- APIs are preview (`networking.datumapis.com/v1alpha`, `gateway.envoyproxy.io/v1alpha1`); recheck before relying on edge cases
- Test origins: `mendhak/http-https-echo` (echoes path, headers, Instance), `jmalloc/echo-server` (WebSocket, SSE)
- Companion guide: [Use ALB as your HTTP proxy](https://www.datum.net/docs/guides/alb-as-httpd)
- More ALB references and examples: [alb.md](../../alb.md)

## Before you begin

- One container per Instance: no proxy sidecar
- App must serve plain HTTP on a named port; TLS ends at the edge
- FastCGI (PHP-FPM) and uWSGI apps need an HTTP-serving image first (FrankenPHP, Apache mod_php, gunicorn, uvicorn)
- Instances have private IPv6 only and no private DNS: no `proxy_pass http://api:8080` between containers
- Projects without a `default` network: pass `--network NAME --yes` to `compute deploy`
- Gateway as its own workload (NGINX `fastcgi_pass` to PHP-FPM Instances by private IPv6 on the same network): follows gVPC docs (same network, any location; no cross-network traffic; no private DNS; no filtering), not tested live

## How proxy concepts map to ALB

### Resource model

- `HTTPProxy` → generated `Gateway` and `HTTPRoute` with the same name, DNS, certificates
- Policies attach to that Gateway or HTTPRoute: `TrafficProtectionPolicy` (WAF), `SecurityPolicy` (auth, IP rules, CORS), `BackendTrafficPolicy` (timeouts, rate limits, circuit breaker)
- Compute backend YAML: `backends[].networkService: {name: WORKLOAD, port: http}`; external backend: `backends[].endpoint: https://...`
- No hostnames in spec → generated `*.datumproxy.net` name in `status.canonicalHostname`
- `ClientTrafficPolicy` does not exist on Datum: no TLS version, mTLS, idle timeout, or client-IP settings

### Edge model

- Anycast hostname, Envoy fleet in every location, nearest healthy Instance
- Per-edge-node state: passive ejection and local rate limits are tracked per Envoy node, not globally
- Config propagation: 1 to 3 minutes per change; Accepted and Programmed don't mean the edge is serving it yet
- Observed on 2026-10-28 retests: force-HTTPS and URL rewrite about 10 s, BackendTrafficPolicy timeout about 45 s, WAF Enforce under 20 s; access log entries about 1 minute behind. Poll for the new behaviour rather than sleeping a fixed time
- HTTP/2 and HTTP/3 on by default (`alt-svc: h3`), TLS 1.3, Let's Encrypt certificates
- While a change propagates, a request can briefly get 503 or reach the old backend
- Wait for a change by polling for the new behaviour, bounded at 3 minutes. Example, waiting for the HTTPS redirect (replace the hostname, path and expected status after any change):

```bash
for i in $(seq 18); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://tile-desire-9gpyk.datumproxy.net/)" = "301" ] && break
  sleep 10
done
```

### Directive mapping

<!-- Table to build: columns NGINX | Apache | Caddy | Traefik | Datum | Notes. Rows: -->
- Virtual hosts: `server_name` | `ServerName` | site block | `Host()` rule → `spec.hostnames` (max 16, one-label wildcards per project opt-in)
- Locations and routes → `rules[].matches` (max 16 rules, 64 matches per rule)
- Upstream pools → `backends[]` (max 16, weight 0 to 1,000,000)
- `proxy_pass` URI semantics → `URLRewrite`
- `return` and `rewrite ... permanent` → `RequestRedirect`
- `proxy_set_header`, `add_header` → header modifier filters
- `auth_basic`, `auth_request` → `SecurityPolicy`
- `allow`, `deny` → `SecurityPolicy.authorization`
- `limit_req`, `max_conns` → `BackendTrafficPolicy`
- `proxy_read_timeout` → `BackendTrafficPolicy.timeout`
- `nginx -t`, reload → `datumctl diff`, `--dry-run=server`, `apply`

### What stays in your app

- Static files, `try_files`, `autoindex`, SPA fallback
- Response compression: the ALB sends uncompressed bodies even with `Accept-Encoding: gzip, br`
- `proxy_cache`, `expires`
- Custom error pages, maintenance pages, direct responses (`return 200`)
- Request mirroring: `RequestMirror` is in `explain` but rejected by the server
- Retries: `spec.retry: Forbidden: retry settings are not permitted`
- `proxy_redirect` (Location header rewriting)
- Body transforms: `sub_filter`, SSI, scripting

## Deploy your app without a proxy container

- `compute deploy --http-port` creates the ALB, network service, and HTTPProxy
- Example to add: deploy command with `--min=2` per location
- Rollouts replace one Instance at a time per location; one Instance means downtime during rollouts
- ALBs that `compute deploy` creates: no WAF, no HTTP to HTTPS redirect (plain HTTP returns 200)
- ALBs that `alb create` creates: WAF Enforce at paranoia 1 on the Gateway, and HTTPS forced
- Quota: 10 HTTPProxies per project, including ones `compute deploy` creates
- `compute destroy -y` removes the workload, its HTTPProxy, and its network service
- `compute destroy` leaves the TrafficProtectionPolicy that `alb waf set` created behind (seen as `ACCEPTED False` after destroy) [tested 2026-10-28]. Delete it with `datumctl delete trafficprotectionpolicy NAME`
- Unverified: whether `compute destroy` removes SecurityPolicy and BackendTrafficPolicy (deleted first in tests). Delete them yourself with `datumctl delete -f FILE`
- `compute deploy` writes `workload.yaml` to the current directory, overwriting any earlier one
- In a project with no `default` network, `compute deploy` without `--network` offers to create one; with no terminal (agents, CI) pass `--network NAME --yes`
- The `alb` plugin manages ALBs that `compute deploy` creates (same name as the workload) [tested 2026-10-28]:
  - `datumctl alb update NAME --force-https` adds a 301 redirect rule matching `x-forwarded-proto: http`
  - `datumctl alb update NAME --health-checks` turns on passive health checks (5 consecutive 5xx, 30s, max 50%)
  - `datumctl alb waf set NAME --mode Observe|Enforce --paranoia 1`
  - `datumctl alb route add NAME --path /api --network-service WORKLOAD --port http`
- First `datumctl apply` on a plugin- or deploy-created HTTPProxy warns about a missing `last-applied-configuration` annotation; it is patched automatically and harmless
- Custom hostnames (`datumctl alb hostname add`) not tested: no test domain in the project

## Translate common proxy configuration

### Route paths to different apps

- Most specific match wins regardless of rule order (tested both orders); same as NGINX prefix locations
- PathPrefix matches whole segments: `/api` matches `/api/x`, not `/apiv2`
- Path forwarded unchanged by default
- Editing: start from `datumctl get httpproxy NAME -o yaml`. A hand-written full HTTPProxy replaces every rule, and silently drops the force-HTTPS redirect rule that `alb update --force-https` added [found by a test agent 2026-10-28]
- Exact ignores the query string
- Example to add: two workloads by path

### Match on exact paths, regexes, headers, and methods

- RegularExpression is a full-path RE2 match; unanchored patterns still match the whole path
- PCRE lookaheads are accepted, report Programmed, and never match: no error anywhere
- Fields inside one match are ANDed; entries in `matches` are ORed
- Header names are case-insensitive; values exact unless RegularExpression
- Methods can route but not reject (no 405 equivalent)

### Redirect and rewrite URLs

- `ReplacePrefixMatch` needs a PathPrefix match (Exact is rejected); `ReplaceFullPath`; `urlRewrite.hostname`
- Redirect-only rules need no backends; path and query preserved; 301, 302, 303, 307, 308
- HTTP to HTTPS: rule matching header `x-forwarded-proto: http`; default status is 302 unless set
- `--force-https` from the `alb` plugin uses 301; a hand-written redirect rule without `statusCode` uses 302
- Example to add: canonical host redirect (not retested 2026-10-28)
- Prefix strip [tested 2026-10-28]: `/api/users` arrives at the app as `/users`; `alb logs` PATH shows the rewritten path

```yaml
  - matches:
    - path: {type: PathPrefix, value: /api}
    filters:
    - type: URLRewrite
      urlRewrite:
        path: {type: ReplacePrefixMatch, replacePrefixMatch: /}
    backends:
    - networkService: {name: api, port: http}
```

### Set request and response headers

- `add` appends (`client, added`), `set` replaces, `remove` deletes
- Host override: `RequestHeaderModifier set Host` had no effect on a Compute backend; `urlRewrite.hostname` works [docs, contradicted by test]
- Response modifiers apply to origin responses (200 and 500) but not the ALB's own 404
- Each origin gets its own hostname as Host unless overridden; a Host override applies to every origin in the rule

### Allow cross-origin requests

- `type: CORS` with `cors.allowOrigins`, `allowMethods`, `allowHeaders`, `exposeHeaders`, `allowCredentials`, `maxAge`
- Preflight answered at the edge; `max-age` defaulted to 5 seconds

### Pass the client IP to your app

- App receives `X-Forwarded-For` (client IP), `X-Forwarded-Proto: https`, `X-Envoy-External-Address`, `X-Request-Id`
- Client-supplied `X-Forwarded-For` is appended to: read the rightmost entry or `X-Envoy-External-Address`
- Client-supplied `X-Request-ID` is replaced
- Frameworks must trust `X-Forwarded-Proto` (Django `SECURE_PROXY_SSL_HEADER`, Express `trust proxy`)

### Require sign-in

- See Access control below

## Load balancing and rollouts

- Weights are per origin (workload), not per Instance: 1:1 between a 2-Instance and a 1-Instance workload gave 99/101
- Weight 0 drains; all weights 0 is accepted by the API and then returns 500 [docs, contradicted by test]
- YAML algorithm values: `LeastRequest` (default), `RoundRobin`, `Random`, `ConsistentHash` (CLI uses lowercase)
- Consistent hash on a header is sticky per value; with weights, the hash picks the origin, not the weight: no weighted sticky canary
- Passive health checks: three 5xx ejected an Instance and traffic moved to its sibling; control without checks alternated 5/5
- Ejection is per edge node: a client on another node still reaches the failing Instance
- No active health checks; Compute has no readiness probes
- Locality: requests from California all went to the us-west-1 Instance
- Failover `Backend` kind with `fallback` exists, but HTTPProxy backends can't reference it

## Timeouts, streaming, WebSockets, and gRPC

- Default response timeout about 15 seconds total: 10 s delay returned 200, 20 to 130 s returned 504 at 15.07 s
- Datum HTML error page on 504
- Raise it: `BackendTrafficPolicy` `timeout.http.requestTimeout` targeting the Gateway; 300s let SSE run 45 s
- Lower works too (5s cut at 5.06 s); intermittent failures for about 2 minutes after applying
- No per-rule timeout field in HTTPProxy
- NGINX `proxy_read_timeout` limits the gap between reads; this limits the whole response
- Streaming: bytes and SSE events arrive progressively; `proxy_buffering off` not needed
- WebSockets to Compute: 101, held 71 s with a 30 s idle gap, not subject to the 15 s cap
- WebSockets to HTTPS `endpoint` origins fail: 502 `UPE` (echo.websocket.org), 503 `UC` (Datum ALB as endpoint); consistent with HTTP/2 to origin
- gRPC: `--http2`; WebSockets then also use HTTP/2 to the app, so serve them on a separate HTTP/1.1 port through a network service

## Access control

- IP allow and deny: `SecurityPolicy.authorization` with `clientCIDRs`; default Allow plus Deny rule → 403; default Deny plus Allow rule → 200
- Basic auth via `alb auth set`: 401 without or with wrong credentials, 200 with correct; `auth set` replaces the user list
- Manifest basic auth: only `{SHA}` hashes; bcrypt returns 500 for every request with no status explanation
- Secrets need label `networking.datumapis.com/gateway-sync: "true"`; without it, correct credentials got 401 (docs say 500)
- OIDC: 302 to the provider with the right client ID and redirect URI
- OIDC authenticates only; restrict users in the identity provider (oauth2-proxy `--email-domain` has no equivalent)
- WAF plus OIDC: no conflict reproduced (docs warn of 500)
- Schema also has `jwt`, `apiKeyAuth`, `extAuth`, and HTTPProxy rule filter `externalAuth` (untested)

## Protection

### WAF

- Observe passes SQLi and XSS probes (200); Enforce returns 403; benign requests stay 200
- Both `HTTPRoute` and `Gateway` targets work
- Bodies of 10 MB and above get 413 with any WAF policy, Observe included; 1 MB passed but took 7 to 12 s (0.5 s without WAF)
- Portal sets paranoia 1 or 2 only; CLI sets 1 to 4
- Attachment from `alb create` is best-effort; verify with `alb waf describe`

### Rate limits

- `BackendTrafficPolicy` `rateLimit` type Local on the Gateway; HTTPRoute targets stay Conflicted
- Per edge node: 10/min allowed 11 of 30 on one connection; fresh connections got 9 more from other nodes
- 429 with `x-ratelimit-limit`, `-remaining`, `-reset` and body `local_rate_limited`
- `clientSelectors` with `sourceCIDR` or `headers` type Distinct gives separate buckets per value
- Global type passes dry-run; untested

### Circuit breaker

- `circuitBreaker` maxConnections, maxPendingRequests, maxParallelRequests: limits of 1 gave two 200s and eight fast 503s of ten concurrent

## Verify the migration

Test through the ALB hostname while the old proxy still serves production. Don't switch DNS first. Set `ALB` to the hostname that `compute deploy` printed:

```bash
ALB=tile-desire-9gpyk.datumproxy.net
```

Wait 1 to 3 minutes after each change before checking (see Edge model).

### Route checks

Check which backend answered, not just the status code. A 200 from the wrong workload looks like success. Use something only that app returns: a version endpoint, a response header, or the Instance name.

```bash
for p in / /api/users /static/app.css; do
  printf '%-20s ' "$p"; curl -s -o /dev/null -w '%{http_code}\n' "https://$ALB$p"
done
```

| Path | Expect |
|---|---|
| `/` | 200 from the web workload |
| `/api/...` | 200 from the api workload (most specific match wins, whatever the rule order) |
| `/apiv2` | the `/` workload, not api: PathPrefix matches whole segments |
| a path no rule matches | 404 from the ALB (Datum's page, without your response headers) |

With an echo origin such as `mendhak/http-https-echo`, the body's `os.hostname` names the Instance that answered.

### Redirect and rewrite checks

Don't follow redirects (`-L`); check status and `Location`:

```bash
curl -sI "http://$ALB/pricing" | grep -iE '^(HTTP|location)'
```

```text
HTTP/1.1 301 Moved Permanently
location: https://tile-desire-9gpyk.datumproxy.net/pricing
```

For rewrites, confirm the path the app received, in the app's own logs or in the ALB access log (PATH is after rewrite):

```bash
datumctl alb logs NAME --since 10m --limit 5
```

### Sign-in checks

Without a session, the ALB redirects to the identity provider [tested 2026-10-28, Google issuer, dummy client]:

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' "https://$ALB/"
```

```text
302 https://accounts.google.com/o/oauth2/v2/auth?client_id=CLIENT_ID.apps.googleusercontent.com&code_challenge=...
```

- Check `client_id` and `redirect_uri` in the `Location` are yours
- Sign in in a browser and confirm the app loads; then sign in as a user who should be refused and confirm the identity provider refuses them (the ALB doesn't restrict users)
- 401 with correct basic-auth credentials: Secret is missing the `gateway-sync` label

### Production review checks

| Item | Check | Expect |
|---|---|---|
| Response timeout | Your slowest real request; with an echo origin, `curl -H 'x-set-response-delay-ms: 20000' https://$ALB/slow` | 504 at about 15 s by default; 200 after raising `requestTimeout` [tested 2026-10-28: 504 at 15.13 s, then 200 at 20.16 s with 120s] |
| Uploads | `curl -F file=@big.bin https://$ALB/upload` with your largest real upload | 413 at 10 MB and above with any WAF policy; slow but passing at 1 MB |
| WebSockets | `websocat wss://$ALB/ws`, hold past 15 s | 101, stays open; fails to HTTPS `endpoint` origins |
| Streaming / SSE | `curl -N https://$ALB/events` | events arrive progressively; cut at the response timeout |
| Rate limits | Burst on one connection (one `curl` with `--next`) | 429 with `x-ratelimit-*` headers; fresh connections may hit other nodes and pass |
| Client IP | App logs or an echo endpoint | `x-forwarded-for` and `x-envoy-external-address` carry your IP; spoofed `X-Forwarded-For` is appended to, so read the rightmost entry |
| Health checks | `datumctl alb describe NAME` | `Health checks: passive: ...`, not `off` (off by default on deploy-created ALBs) |
| WAF | `datumctl alb waf describe NAME`; SQLi probe `curl "https://$ALB/?id=1%27%20OR%20%271%27=%271"` | Observe: 200; Enforce: 403 [tested 2026-10-28] |

### Log and metric checks

Every check above should appear in the access log within a minute or two:

```bash
datumctl alb logs NAME --since 15m --limit 5
datumctl alb logs NAME --since 15m --code 504 -o wide   # adds REQUEST ID and UPSTREAM (the Instance's private IPv6)
```

```text
TIME       METHOD   STATUS   PATH                            HOST                               DURATION
19:36:31   GET      200      /?id=1%27%20OR%20%271%27=%271   tile-desire-9gpyk.datumproxy.net   105ms
19:34:40   GET      504      /slow                           tile-desire-9gpyk.datumproxy.net   15058ms
19:34:25   HEAD     301      /pricing                        -                                  3ms
```

For metrics (request rate, error rate, latency, WAF blocks), open the ALB in the Cloud Portal or see the ALB observability docs page. Metric retention and alerting were not checked.

### Cut over

1. A day or more before: lower the TTL on the record you'll change (for example to 60 s), so a rollback propagates quickly
2. Add the custom hostname to the ALB (`datumctl alb hostname add NAME app.example.com`) and wait in `datumctl alb describe NAME` until claimed, ownership verified, and certificate are done. The DNS record step finishes when you switch DNS
3. Switch the record to the ALB, as the custom-domains docs page describes
4. Watch `datumctl alb logs NAME --since 10m --code 502`, `--code 503`, `--code 504` and the Portal error rate for the first hour
5. Keep the old proxy container deployed and unchanged for the rollback window. To roll back, point the record back at it; the low TTL makes this fast
6. After the window: raise the TTL again, then retire the old proxy, its config, and certificate renewal jobs

Not tested end to end on 2026-10-28 (no test domain).

## Verify and debug

- `datumctl alb logs NAME --since 1h --code 502 -o wide` (request ID, upstream)
- `datumctl telemetry logs '{response_code=~"50[23]"}'`: full Envoy fields including `response_flags`, `upstream_host`, edge pod
- Response flags seen: `UPE` upstream protocol error, `UC` upstream connection termination
- Test with one reused connection to see per-node behaviour; fresh connections spread across nodes
- Wait for propagation before measuring
- Transient `Your request took too long to be checked against your quota` (Forbidden) on `apply`: seen again 2026-10-28; retry after a minute

## Troubleshooting

<!-- Table to build: symptom | cause | fix -->
- 504 at 15 s → default timeout → raise requestTimeout
- 413 on upload → WAF body limit → separate rule or ALB without WAF
- 500 on every request with basic auth → bcrypt hash → use `{SHA}`
- 401 with correct password → Secret missing `gateway-sync` label
- 502 or 503 on WebSocket → `endpoint` origin over HTTP/2 → use a Compute backend
- Regex never matches → PCRE syntax → rewrite as RE2
- Response header missing on 404 → ALB-generated response → expected
- Create refused with quota error → 10 HTTPProxies per project
- Change not visible → propagation, 1 to 3 minutes
- `apply` Forbidden "took too long to be checked against your quota" → transient control-plane issue → retry
- All requests 500 after weight change → every weight 0

## Limits and quotas

- 16 hostnames, 16 rules, 64 matches per rule, 128 matches total, 16 backends per rule per HTTPProxy
- 17 rules or hostnames → `Too many: 17: must have at most 16 items`
- 10 HTTPProxies per project
- One ALB per workload through `compute deploy`
- WAF request body limit between 1 MB and 10 MB
- Default response timeout about 15 s

## Docs inconsistencies found

- First-match-wins (path-routing page, HTTPRoute skill) vs most specific (routes page); test: most specific
- Host override via RequestHeaderModifier (docs) vs no effect on Compute backend (test)
- All-zero weights refused (docs) vs accepted then 500 (test)
- Missing gateway-sync label returns 500 (docs) vs 401 (test)
- WAF plus OIDC 500 (Auth0 guide) vs no conflict (test)
- ClientTrafficPolicy in the client-traffic skill vs not available
- TrafficProtectionPolicy target: HTTPRoute (WAF page) vs Gateway (ALB skill); both work
- `explain` lists `requestMirror`, server rejects it
