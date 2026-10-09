FROM gcc:14-bookworm@sha256:5e927c284bf55a7dc796262e311a0703344f62f41f5621eb56843111b1d37e15 AS build
RUN apt-get update && apt-get install -y --no-install-recommends cmake ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY instrument/ .
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug \
    && cmake --build build -j2 && ctest --test-dir build --output-on-failure
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587 AS runtime
RUN useradd --create-home --uid 10001 instrument
COPY --from=build /src/build/instrument /usr/local/bin/instrument
USER 10001
EXPOSE 9000 9001
ENTRYPOINT ["instrument"]
