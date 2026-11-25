# Shell shims used by castrec.py. Source order: podman and curl behave normally; adjust datumctl to your install.
# Everything runs at low CPU priority so a recording doesn't load the box.
podman() { if [ "$1" = run ]; then shift; nice -n 19 command podman run "$@"; else nice -n 19 command podman "$@"; fi; }
# datumctl via the container image (not installed on the host here); login state lives in the datumctl-config volume.
datumctl() { nice -n 19 command podman run --rm -i -v datumctl-config:/root/.datumctl docker.io/dlotterman/datumctl-container:latest "$@" 2>&1; }
curl() { command curl "$@"; }
