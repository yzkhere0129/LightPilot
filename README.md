# LightPilot

**AI-powered standalone RAW photo editor.** Describe the look you want in natural language — the AI analyzes your photo and iteratively adjusts develop parameters until it matches your vision. No image generation, no quality loss — every pixel comes from your original file.

## Features

- **PixelPipe Engine** — Full RAW processing pipeline: decode, white balance, exposure, tone curve, HSL, color grading, detail, effects, crop, export. All processing in float32 linear RGB.
- **AI Retouching Agent** — Describe a style (e.g. *"warm cinematic"*, *"bright and airy"*), optionally provide a reference photo, and the agent iteratively adjusts parameters until converged (up to 5 rounds).
- **Non-Destructive Editing** — All edits stored as parameter sidecars (`.lightpilot.json`). Original files are never modified.
- **PySide6 GUI** — Dark-themed desktop app with Library (import, browse, rate, filter) and Develop (canvas with zoom/pan, histogram, 8 editing panels, AI panel) modules.
- **Proxy Workflow** — Interactive editing at 2MP proxy resolution; full-res export on demand.
- **Multi-Provider AI** — Supports OpenAI, Anthropic, Google, Ollama, DeepSeek, MiMo, and any OpenAI-compatible API.
- **100+ Adjustable Parameters** — Matches Lightroom Classic PV2012+ parameter set: basic, tone curve, HSL, color grading, detail, effects, lens corrections, calibration, crop.

## How It Works

```
                        PixelPipe (RAW Engine)
                        ┌───────────────────────────────────┐
    RAW photo ──────────▶ raw_decode ─▶ white_balance       │
                        │ ─▶ exposure ─▶ tone_curve         │
                        │ ─▶ hsl ─▶ color_grading           │
                        │ ─▶ detail ─▶ effects ─▶ crop      │
                        │ ─▶ output                         │
                        └───────────┬───────────────────────┘
                                    │ 2MP proxy preview
                        ┌───────────▼───────────────────────┐
                        │       AI Vision Model             │
                        │  (GPT-4o / Claude / Gemini / ...) │
                        │                                   │
                        │  "exposure is 0.5 stops under,    │
                        │   shadows need lifting,           │
                        │   add warm tone..."               │
                        │                                   │
                        │  → JSON parameter adjustments     │
                        └───────────┬───────────────────────┘
                                    │ apply & re-render
                                    ▼
                              iterate 1–5×
                            until converged
```

## Quick Start

### Requirements

- Python 3.10+
- At least one AI provider API key (or Ollama for local inference)

### Install

```bash
pip install -r requirements.txt
```

### Configure

Copy and edit `config.yaml` with your API key:

```yaml
models:
  default: openai              # or anthropic, google, ollama, deepseek, mimo, custom

  openai:
    api_key: "sk-..."
    model: "gpt-4o"

  anthropic:
    api_key: "sk-ant-..."
    model: "claude-haiku-4-5-20251001"

  google:
    api_key: "AIza..."
    model: "gemini-2.0-flash"

  ollama:
    base_url: "http://localhost:11434"
    model: "llava"

  deepseek:
    api_key: "sk-..."
    model: "deepseek-chat"

  mimo:
    api_key: "..."
    model: "mimo-v2-omni"

  custom:
    api_key: "..."
    base_url: "https://your-api.com/v1"
    model: "your-model"

agent:
  max_iterations: 5
  convergence_threshold: 0.1
```

## Usage

### GUI

```bash
python -m lightpilot
```

Launch the desktop app. Import a folder in Library, double-click a photo to enter Develop, adjust sliders or use the AI panel.

### AI CLI — Automated Retouching

```bash
# Style by text description
python -m lightpilot.ai photo.ARW -s "moody film look" -o result.jpg

# With a reference photo for style matching
python -m lightpilot.ai photo.ARW -s "match this" -r reference.jpg -o result.jpg

# Use a specific provider
python -m lightpilot.ai photo.ARW -s "bright and airy" -p anthropic -o result.jpg

# Full-resolution export
python -m lightpilot.ai photo.ARW -s "cinematic" -o result.tiff --full-res
```

### Engine CLI — Manual Processing

```bash
# Process with specific parameters
python -m lightpilot.engine photo.ARW -o out.jpg --params '{"Exposure2012": 0.5, "Shadows2012": 40}'

# Load from sidecar file
python -m lightpilot.engine photo.ARW -o out.jpg --sidecar

# Full resolution (no proxy)
python -m lightpilot.engine photo.ARW -o out.tiff --proxy 0

# Verbose timing output
python -m lightpilot.engine photo.ARW -o out.jpg -v
```

## Supported AI Models

| Provider | Models | API Key | Notes |
|----------|--------|---------|-------|
| OpenAI | GPT-4o, GPT-4o-mini | `OPENAI_API_KEY` | Best overall quality |
| Anthropic | Claude Sonnet / Haiku | `ANTHROPIC_API_KEY` | Strong reasoning |
| Google | Gemini 2.0 Flash, 1.5 Pro | `GOOGLE_API_KEY` | Fast and cheap |
| Ollama | LLaVA, moondream, etc. | None (local) | Free, runs locally |
| DeepSeek | DeepSeek-V3 | `DEEPSEEK_API_KEY` | OpenAI-compatible |
| MiMo | MiMo-v2-omni | — | OpenAI-compatible |
| Custom | Any | — | Any OpenAI-compatible endpoint |

## Supported RAW Formats

ARW (Sony), CR2/CR3 (Canon), NEF (Nikon), DNG (Adobe), RAF (Fujifilm), ORF (Olympus), RW2 (Panasonic), PEF (Pentax), SRW (Samsung), X3F (Sigma), IIQ (Phase One), 3FR (Hasselblad)

Also supports JPEG, PNG, and TIFF as input.

## Project Structure

```
LightPilot/
├── config.yaml                              # API keys & agent settings
├── requirements.txt
├── lightpilot/
│   ├── __main__.py                          # GUI entry point
│   ├── engine/
│   │   ├── __main__.py                      # Engine CLI
│   │   ├── pixelpipe.py                     # Pipeline orchestrator (smart caching)
│   │   ├── buffer.py                        # Float32 RGB image buffer
│   │   └── modules/
│   │       ├── raw_decode.py                # RAW decoding (rawpy / OpenCV)
│   │       ├── white_balance.py             # Temperature & tint
│   │       ├── exposure.py                  # Exposure, contrast, highlights, shadows
│   │       ├── tone_curve.py                # Parametric tone curve + gamma
│   │       ├── hsl.py                       # 8-channel HSL + vibrance/saturation
│   │       ├── color_grading.py             # Shadow/midtone/highlight/global color wheels
│   │       ├── detail.py                    # Sharpening + noise reduction
│   │       ├── effects.py                   # Vignette + grain
│   │       ├── crop.py                      # Crop & rotation
│   │       └── output.py                    # JPEG/TIFF/PNG export
│   ├── ai/
│   │   ├── __main__.py                      # AI CLI
│   │   ├── agent.py                         # Iterative convergence loop (max 5 rounds)
│   │   ├── pipeline_bridge.py               # Connects AI agent to PixelPipe
│   │   ├── prompts.py                       # System/user prompt builder
│   │   ├── style_learner.py                 # Learn from user's editing history
│   │   └── vision/
│   │       ├── base.py                      # VisionModel ABC + AdjustmentResult
│   │       ├── factory.py                   # Provider factory (7 providers)
│   │       ├── openai_vision.py             # OpenAI / DeepSeek / MiMo / custom
│   │       ├── anthropic_vision.py          # Anthropic Claude
│   │       ├── google_vision.py             # Google Gemini
│   │       └── ollama_vision.py             # Local Ollama
│   ├── catalog/
│   │   ├── database.py                      # SQLite photo catalog
│   │   └── sidecar.py                       # .lightpilot.json param files
│   └── gui/
│       ├── app.py                           # QApplication setup
│       ├── main_window.py                   # Main window (Library / Develop)
│       ├── common/
│       │   └── slider.py                    # Custom parameter slider widget
│       ├── library/
│       │   └── library_view.py              # Thumbnail grid, import, rating, filter
│       └── develop/
│           ├── canvas.py                    # Image display (zoom / pan)
│           ├── histogram.py                 # Real-time RGB histogram
│           └── panels/
│               ├── basic_panel.py           # Exposure, WB, contrast, etc.
│               ├── tone_curve_panel.py      # Parametric tone curve
│               ├── hsl_panel.py             # HSL color mixer
│               ├── color_grading_panel.py   # Color wheels
│               ├── detail_panel.py          # Sharpening & noise reduction
│               ├── effects_panel.py         # Vignette & grain
│               ├── crop_panel.py            # Crop controls
│               └── ai_panel.py              # AI style input & controls
└── tests/
    └── test_offline.py
```

## Architecture

### PixelPipe Engine

The engine processes images through a fixed 10-module pipeline. Each module reads parameters from a shared dict and modifies the `ImageBuffer` (float32 RGB, shape `H x W x 3`, range [0, 1]).

- Modules 1–4 (raw_decode through tone_curve) operate in **linear sRGB**
- Module 4 (tone_curve) applies gamma encoding
- Modules 5–10 operate in **gamma-encoded sRGB**
- Smart caching: only re-runs from the first module whose parameters changed

### AI Agent

The `RetouchAgent` runs an iterative loop:

1. Render a 2MP proxy preview via `PipelineBridge`
2. Send preview + style prompt to the vision model
3. Model returns JSON with parameter adjustments + confidence score
4. Apply adjustments, re-render, repeat
5. Stop when: model reports converged, confidence plateaus, or max iterations reached

### Non-Destructive Catalog

- **SQLite database** tracks imported photos with metadata (camera, lens, ISO, aperture, etc.)
- **Sidecar JSON files** (`photo.ARW.lightpilot.json`) store editing parameters
- Edits can be loaded, modified, and re-exported at any time without touching the original

## Token Cost Estimate (AI)

| Model | ~Cost per photo (5 iterations) |
|-------|-------------------------------|
| GPT-4o-mini | $0.01 – $0.03 |
| GPT-4o | $0.05 – $0.15 |
| Claude Haiku | $0.02 – $0.05 |
| Gemini 2.0 Flash | $0.005 – $0.02 |
| Ollama (local) | Free |

## License

MIT
