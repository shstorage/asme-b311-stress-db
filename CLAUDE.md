# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

This project tests **PaddleOCR-VL** (a vision-language model) for extracting structured data (e.g., chemical composition tables) from document images. Input images live in `image/h2/`, and results are saved to `output/`.

## Environment

The GPU runtime lives inside a Docker container built from the offline PaddleOCR image:

```bash
# Build and run the container (exposes JupyterLab on port 8888)
docker build -t paddle-test .
docker run --gpus all -p 8888:8888 -v $(pwd):/workspace paddle-test
```

The container is also assumed to expose a **vLLM server on port 8080** serving the `PaddleOCR-VL-1.5-0.9B` model via an OpenAI-compatible API.

## Running Scripts

```bash
# Run with uv (manages the Python environment)
uv run python test.py    # raw requests to vLLM server at localhost:8080
uv run python test2.py   # same, using the openai SDK client
uv run python main.py    # placeholder entry point
```

## Architecture

There are two distinct usage patterns in this repo:

1. **Direct PaddleOCR pipeline** (`Untitled.ipynb`) — runs inside the Docker container where `paddleocr` is installed. Calls `PaddleOCRVL.predict()` directly, saves results as Markdown and JSON to `./output`.

2. **vLLM API client** (`test.py`, `test2.py`) — sends base64-encoded images to the vLLM inference server (`http://localhost:8080/v1/chat/completions`) using the OpenAI chat completions format. `test.py` uses `requests`; `test2.py` uses the `openai` SDK.

Both paths target the same model (`PaddleOCR-VL-1.5-0.9B`) but differ in whether the model runs in-process or via a remote server.

## Key Environment Variable

```bash
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True  # suppresses model source validation inside the container
```
