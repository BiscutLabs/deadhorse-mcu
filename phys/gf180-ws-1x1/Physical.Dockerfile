FROM nixos/nix@sha256:7a007c766426c1877758ddc5cb87a965ac131fc78c582ce0083d922d51ae945c
# Build context is an authenticated template materialization, not the repo root.
COPY flake.nix flake.lock /opt/wafer-template/
RUN nix --extra-experimental-features 'nix-command flakes' develop path:/opt/wafer-template --accept-flake-config --no-write-lock-file --command true
WORKDIR /work
ENTRYPOINT ["nix", "--extra-experimental-features", "nix-command flakes", "develop", "path:/opt/wafer-template", "--accept-flake-config", "--no-write-lock-file", "--offline", "--command"]
