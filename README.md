# LR AI Agent

AI-powered Lightroom Classic retouching agent. Analyzes your photos using vision AI and applies non-destructive develop parameter adjustments — **no image generation, full original quality preserved**.

## How It Works

```
LR Classic (Lua plugin)
    ↓ exports 1600px JPEG preview + current develop params
Python backend
    ↓ sends preview to AI vision model (your API key)
AI (GPT-4o / Claude / Gemini / Ollama)
    ↓ returns JSON parameter deltas
Python backend
    ↓ writes pending_update.json
LR Classic (Lua plugin)
    ↓ applies param deltas to current photo (non-destructive)
    ↑ loop 3-5 times until converged
```

## Supported Models

| Provider | Models | API Key |
|----------|--------|---------|
| OpenAI | GPT-4o, GPT-4o-mini | `OPENAI_API_KEY` in config |
| Anthropic | Claude Haiku / Sonnet | `ANTHROPIC_API_KEY` in config |
| Google | Gemini 1.5 Flash/Pro, 2.0 Flash | `GOOGLE_API_KEY` in config |
| Ollama | LLaVA, moondream (local) | No key needed |
| Any OpenAI-compatible API | Custom | Fill `base_url` in config |

## Setup

### 1. Python Backend

```bash
cd lr-ai-agent
pip install -r requirements.txt
```

Edit `config.yaml` and fill in at least one model's API key.

### 2. Lightroom Plugin

1. In Lightroom Classic: **File → Plug-in Manager → Add**
2. Navigate to `lightroom-plugin/lr-ai-agent.lrplugin`
3. Click **Add Plug-in**

### 3. Verify AI Works (Phase 0 — no LR needed)

```bash
python backend/phase0_test.py your_photo.jpg --style "moody film look"
python backend/phase0_test.py your_photo.jpg --reference reference.jpg --style "match this style"
```

## Usage

### Start a Session

1. Open Lightroom Classic, select a photo in Develop
2. **Library / File menu → AI Retouch — Start Session**
3. In terminal:

```bash
# Basic: style by text description
python -m backend.main --style "warm golden hour, lifted shadows"

# With reference photo
python -m backend.main --style "match reference" --reference ./ref.jpg

# Use a specific model
python -m backend.main --style "cinematic" --provider anthropic

# Custom iteration count
# Edit config.yaml → agent.max_iterations
```

LR will update the photo in real time as each iteration completes.

## Configuration (`config.yaml`)

```yaml
models:
  default: openai          # Which provider to use by default

  openai:
    api_key: "sk-..."
    model: "gpt-4o"
    base_url: ""           # Optional: proxy or compatible API (e.g. Azure, Groq)

  anthropic:
    api_key: "sk-ant-..."
    model: "claude-haiku-4-5-20251001"

  google:
    api_key: "AIza..."
    model: "gemini-1.5-flash"

  ollama:
    base_url: "http://localhost:11434"
    model: "llava"

agent:
  max_iterations: 5
  convergence_threshold: 0.1

bridge:
  directory: "~/.lr-ai-agent"
  poll_interval: 0.5
  timeout: 30
```

## Token Cost Estimate

| Model | Cost per photo (5 iterations) |
|-------|-------------------------------|
| GPT-4o-mini | ~$0.01–0.03 |
| GPT-4o | ~$0.05–0.15 |
| Claude Haiku | ~$0.02–0.05 |
| Gemini 1.5 Flash | ~$0.005–0.02 |
| Ollama (local) | Free |

## Project Structure

```
lr-ai-agent/
├── config.yaml                          # User configuration + API keys
├── requirements.txt
├── backend/
│   ├── main.py                          # CLI entry point
│   ├── agent.py                         # Iterative retouching loop
│   ├── lr_bridge.py                     # File-system IPC with LR plugin
│   ├── phase0_test.py                   # Standalone AI validation script
│   └── vision/
│       ├── base.py                      # Abstract VisionModel + AdjustmentResult
│       ├── factory.py                   # Provider factory
│       ├── openai_vision.py             # GPT-4o
│       ├── anthropic_vision.py          # Claude
│       ├── google_vision.py             # Gemini
│       └── ollama_vision.py             # Local LLaVA etc.
└── lightroom-plugin/
    └── lr-ai-agent.lrplugin/
        ├── Info.lua                     # Plugin metadata
        ├── Main.lua                     # Menu handlers
        ├── FileWatcher.lua              # Bridge loop (export / apply)
        └── JSON.lua                     # Bundled JSON library
```
