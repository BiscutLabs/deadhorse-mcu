# Base digest is also recorded in lock.json and checked by run.py.
FROM curlimages/curl:8.17.0@sha256:43ebaa53d3806db6b1ce4353b6b26ae638ec1c167ee351524b05690f988bb20d AS trust
FROM ubuntu:24.04@sha256:77eb101c607d6e3d4f5ad0c8a02c2136c689b98aba1f359e6502ba517e5c57ec
COPY --from=trust /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|http://snapshot.ubuntu.com/ubuntu/20261113T000000Z/|; s|http://security.ubuntu.com/ubuntu/|http://snapshot.ubuntu.com/ubuntu/20261113T000000Z/|' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends ca-certificates python3.12
COPY tools/env/lock.json /opt/deadhorse-env/
RUN python3.12 -c "import json, subprocess; p=json.load(open('/opt/deadhorse-env/lock.json'))['apt_packages']; subprocess.run(['apt-get','install','-y','--no-install-recommends',*p],check=True)"
COPY tools/env/install.py /opt/deadhorse-env/
RUN --mount=type=cache,target=/opt/downloads python3.12 /opt/deadhorse-env/install.py
COPY tools/env/entrypoint.py tools/env/check.py /opt/deadhorse-env/
# Prefer Ubuntu Python (3.12 + tkinter); use OSS CAD's own wrappers for its tools.
ENV PATH="/opt/yowasp/bin:/opt/openocd/bin:/opt/opensta/bin:/opt/firtool/bin:/opt/sbt/bin:/opt/oss-cad-suite/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 CHISEL_FIRTOOL_PATH=/opt/firtool/bin
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /work
ENTRYPOINT ["python3", "/opt/deadhorse-env/entrypoint.py"]
CMD ["python3", "tools/ci.py"]
