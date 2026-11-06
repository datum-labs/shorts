---
title: Use ALB as your HTTP proxy
author: Daniel Lotterman
date: Draft, Nov 2026
---

If an NGINX, Apache httpd, Caddy or Traefik container sits in front of your app on Datum Compute, the Application Load Balancer can do its jobs at the edge, and you only deploy your app.

Start with the Datum guide, which covers the common cases:

**[Use ALB as your HTTP proxy](https://www.datum.net/docs/guides/alb-as-httpd)**

Then keep the [ALB as httpd reference](../gists/alb/alb-as-httpd-reference.md) open for the rest: a directive-by-directive mapping, load balancing and rollouts, timeouts, streaming, WebSockets and gRPC, access control and the WAF, how to verify the migration, troubleshooting, and the docs inconsistencies found while testing it.

More ALB gists: [alb.md](../alb.md)
