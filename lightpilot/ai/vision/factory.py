"""Factory function to instantiate the correct vision model from config."""
from .base import VisionModel


def create_vision_model(full_config: dict, provider: str | None = None) -> VisionModel:
    """
    Create a VisionModel instance from the full config dict.

    Args:
        full_config: The parsed config.yaml dict.
        provider: Provider name override (openai/anthropic/google/ollama).
                  Defaults to full_config["models"]["default"].
    """
    if provider is None:
        provider = full_config["models"]["default"]

    provider = provider.lower()
    model_cfg = full_config["models"].get(provider)
    if not model_cfg:
        raise ValueError(f"No config found for provider '{provider}'")

    if provider == "openai":
        from .openai_vision import OpenAIVision
        return OpenAIVision(model_cfg)

    elif provider == "anthropic":
        from .anthropic_vision import AnthropicVision
        return AnthropicVision(model_cfg)

    elif provider == "google":
        from .google_vision import GoogleVision
        return GoogleVision(model_cfg)

    elif provider == "ollama":
        from .ollama_vision import OllamaVision
        return OllamaVision(model_cfg)

    elif provider == "deepseek":
        from .openai_vision import OpenAIVision
        # DeepSeek uses OpenAI-compatible API
        cfg = dict(model_cfg)
        if not cfg.get("base_url"):
            cfg["base_url"] = "https://api.deepseek.com"
        return OpenAIVision(cfg)

    elif provider == "mimo":
        from .openai_vision import OpenAIVision
        # MiMo (Xiaomi) uses OpenAI-compatible API
        cfg = dict(model_cfg)
        if not cfg.get("base_url"):
            cfg["base_url"] = "https://api.xiaomimimo.com/v1"
        if not cfg.get("model"):
            cfg["model"] = "mimo-v2-omni"
        return OpenAIVision(cfg)

    elif provider == "custom":
        from .openai_vision import OpenAIVision
        # Generic OpenAI-compatible endpoint
        if not model_cfg.get("base_url"):
            raise ValueError("'custom' provider requires base_url in config")
        return OpenAIVision(model_cfg)

    else:
        raise ValueError(
            f"Unknown provider '{provider}'. "
            "Supported: openai, anthropic, google, ollama, deepseek, mimo, custom"
        )
