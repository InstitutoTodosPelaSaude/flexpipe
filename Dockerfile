FROM condaforge/miniforge3:latest

WORKDIR /app

# Install conda environment
COPY config/nextstrain.yml /tmp/nextstrain.yml
RUN conda env create -f /tmp/nextstrain.yml && \
    conda clean -afy

# Copy source and install the package into the nextstrain env
COPY . /app
RUN conda run -n nextstrain pip install --no-deps -e .

# Default entrypoint runs flexpipe-run inside the nextstrain env.
# Override CMD to pass --config and --workdir at runtime:
#   docker run --rm -v $(pwd)/builds:/builds -v $(pwd)/workdir:/workdir \
#     flexpipe flexpipe-run --config /builds/yfv-brazil/config.yaml \
#                           --workdir /workdir/yfv-brazil
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "nextstrain"]
CMD ["flexpipe-run", "--help"]
