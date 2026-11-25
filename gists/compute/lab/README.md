# Lab: rerun the Compute short

Sources for [`shorts/datumctl-docker-podman.md`](../../../shorts/datumctl-docker-podman.md): the terminal scenes, the data behind the three-panel animation, and the scripts that make the GIFs. Measured values are in [reference §16.21](../datumctl-docker-podman-reference.md#1621-three-cities-end-to-end-2026-11-25).

Prerequisites: Podman, a logged-in `datumctl` (`datumctl compute access` says Active), a Datum project with Compute, ImageMagick, `ffmpeg`, and the [asciinema agg](https://github.com/asciinema/agg) v1.5.0 binary. Name every resource you create with a unique prefix and destroy it afterwards.

| Step | Command |
|---|---|
| Terminal scene to cast | `python3 castrec.py scenes/30-same-image.scene out.cast --cols 100 --rows 24` |
| Cap idle gaps at 1 s | `python3 tight.py out.cast out-tight.cast 1.0` |
| Cast to GIF | `./cast2gif.sh out-tight.cast out.gif 3` (needs the `agg-datum` image from the reference) |
| Three-panel animation | `python3 build_three_cities.py` (reads `data/`, needs `fonts/` with JetBrains Mono and DejaVu Sans) |

`scenes/*.scene` use `$` for a typed command, `#` for a typed comment, ` \` to continue a line, `$URL` for the last `*.datumproxy.net` URL printed, and `~` for a silent setup line. `env.sh` is sourced by `castrec.py`. Scene 31 runs `dcs3-web` and scene 30 `dcs3-whoami`.

`data/` is real run 1 of `datumctl compute deploy api --city=DFW,IAD,SJC`. The animation shows the workload as `api`; it was named `dcs2-api`. Three terminal lines of the animation (`created`, `Rollout complete`, `Backends`/`Edge`) have estimated on-screen times; the rest follows the recorded timestamps.

Teardown: `datumctl compute destroy NAME --yes` for each workload, then `datumctl compute workloads | grep PREFIX` must print nothing.
