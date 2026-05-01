"""Style preset library with concrete parameter recipes.

Each preset is a proven starting point. The AI adapts it to the specific photo
rather than inventing adjustments from scratch — like a chef following a recipe
but adjusting seasoning to taste.
"""

STYLE_PRESETS = {
    "japanese": {
        "keywords": ["日系", "japanese", "japan", "jpn", "和风"],
        "name_zh": "日系",
        "name_en": "Japanese",
        "description": (
            "Soft, airy, slightly desaturated. Lifted shadows create a gentle fade. "
            "Warm but not orange — think golden afternoon light filtered through curtains. "
            "Greens shift toward cyan/teal. Skin tones stay natural and soft."
        ),
        "params": {
            "Exposure2012": 0.3,
            "Contrast2012": -20,
            "Highlights2012": -25,
            "Shadows2012": 50,
            "Whites2012": -10,
            "Blacks2012": 25,
            "Temperature": 6500,
            "Tint": -8,
            "Vibrance": 5,
            "Saturation": -18,
            "Clarity2012": -10,
            "SaturationAdjustmentOrange": -10,
            "SaturationAdjustmentBlue": -25,
            "LuminanceAdjustmentOrange": 10,
            "LuminanceAdjustmentGreen": 15,
            "HueAdjustmentGreen": 30,
            "ColorGradeShadowHue": 160,
            "ColorGradeShadowSat": 12,
            "ColorGradeHighlightHue": 45,
            "ColorGradeHighlightSat": 8,
        },
        "avoid": "Do NOT over-warm. Do NOT crush blacks. Keep shadows soft and lifted.",
    },

    "retro": {
        "keywords": ["复古", "retro", "vintage", "怀旧", "老照片"],
        "name_zh": "复古",
        "name_en": "Retro / Vintage",
        "description": (
            "Warm, faded film look. Lifted blacks create a matte/fade effect. "
            "Orange-teal split toning. Slight desaturation with warm color cast. "
            "Grain adds analog texture."
        ),
        "params": {
            "Exposure2012": 0.1,
            "Contrast2012": -10,
            "Highlights2012": -35,
            "Shadows2012": 30,
            "Blacks2012": 35,
            "Temperature": 7200,
            "Tint": 5,
            "Saturation": -15,
            "Vibrance": -5,
            "Clarity2012": -5,
            "SaturationAdjustmentBlue": -30,
            "SaturationAdjustmentAqua": -20,
            "HueAdjustmentOrange": 5,
            "ColorGradeShadowHue": 200,
            "ColorGradeShadowSat": 20,
            "ColorGradeHighlightHue": 40,
            "ColorGradeHighlightSat": 15,
            "GrainAmount": 30,
            "GrainSize": 35,
            "PostCropVignetteAmount": -25,
        },
        "avoid": "Do NOT make it too dark. The fade should feel nostalgic, not muddy.",
    },

    "fresh": {
        "keywords": ["清新", "fresh", "clean", "明亮", "通透", "airy", "bright"],
        "name_zh": "清新",
        "name_en": "Fresh / Clean",
        "description": (
            "Bright, clean, uplifting. Generous exposure lift with open shadows. "
            "Slightly cool or neutral temperature. Boosted vibrance for lively but not "
            "oversaturated colors. High clarity for crispness."
        ),
        "params": {
            "Exposure2012": 0.5,
            "Contrast2012": -15,
            "Highlights2012": -30,
            "Shadows2012": 45,
            "Whites2012": 15,
            "Blacks2012": 15,
            "Temperature": 5800,
            "Tint": -5,
            "Vibrance": 25,
            "Saturation": -5,
            "Clarity2012": 10,
            "Dehaze": 5,
            "LuminanceAdjustmentOrange": 10,
            "LuminanceAdjustmentGreen": 15,
            "LuminanceAdjustmentBlue": 10,
            "SaturationAdjustmentGreen": 10,
            "ColorGradeShadowHue": 200,
            "ColorGradeShadowSat": 5,
        },
        "avoid": "Do NOT make it washed out. Keep colors lively. Avoid a cold/clinical feel.",
    },

    "cinematic": {
        "keywords": ["电影", "cinematic", "movie", "电影感", "film"],
        "name_zh": "电影感",
        "name_en": "Cinematic",
        "description": (
            "Teal-orange color grading. Strong contrast with rich shadows. "
            "Warm highlights, cool shadows. Slight vignette draws the eye inward. "
            "Feels like a movie still."
        ),
        "params": {
            "Exposure2012": 0.0,
            "Contrast2012": 25,
            "Highlights2012": -20,
            "Shadows2012": -15,
            "Blacks2012": -10,
            "Temperature": 6800,
            "Saturation": -10,
            "Vibrance": 10,
            "Clarity2012": 15,
            "SaturationAdjustmentOrange": 15,
            "SaturationAdjustmentAqua": 15,
            "SaturationAdjustmentBlue": -10,
            "HueAdjustmentOrange": -5,
            "ColorGradeShadowHue": 200,
            "ColorGradeShadowSat": 25,
            "ColorGradeHighlightHue": 35,
            "ColorGradeHighlightSat": 20,
            "PostCropVignetteAmount": -35,
        },
        "avoid": "Do NOT make shadows too crushed. Keep some detail in dark areas.",
    },

    "moody": {
        "keywords": ["暗调", "moody", "dark", "情绪", "低调"],
        "name_zh": "暗调/情绪",
        "name_en": "Moody / Dark",
        "description": (
            "Dark, atmospheric, dramatic. Underexposed with deep shadows and "
            "selective highlights. Desaturated with a color accent. Heavy vignette."
        ),
        "params": {
            "Exposure2012": -0.4,
            "Contrast2012": 30,
            "Highlights2012": -25,
            "Shadows2012": -25,
            "Blacks2012": -15,
            "Temperature": 6200,
            "Saturation": -20,
            "Vibrance": -10,
            "Clarity2012": 20,
            "Dehaze": 10,
            "ColorGradeShadowHue": 220,
            "ColorGradeShadowSat": 15,
            "ColorGradeHighlightHue": 40,
            "ColorGradeHighlightSat": 10,
            "PostCropVignetteAmount": -45,
        },
        "avoid": "Do NOT make it completely black. Keep some tonal range. Avoid pure B&W.",
    },

    "film": {
        "keywords": ["胶片", "胶卷", "film", "analog", "analogue", "kodak", "fuji", "portra"],
        "name_zh": "胶片",
        "name_en": "Film Emulation",
        "description": (
            "Classic film stock look. Lifted blacks for the characteristic matte finish. "
            "Warm midtones, slightly faded highlights. Grain is essential. "
            "Colors are muted but have character — not digitally perfect."
        ),
        "params": {
            "Exposure2012": 0.2,
            "Contrast2012": -5,
            "Highlights2012": -20,
            "Shadows2012": 20,
            "Blacks2012": 30,
            "Temperature": 6800,
            "Tint": 5,
            "Saturation": -12,
            "Vibrance": -5,
            "Clarity2012": -8,
            "SaturationAdjustmentRed": -5,
            "SaturationAdjustmentBlue": -20,
            "HueAdjustmentGreen": 15,
            "ColorGradeShadowHue": 50,
            "ColorGradeShadowSat": 15,
            "ColorGradeHighlightHue": 45,
            "ColorGradeHighlightSat": 10,
            "GrainAmount": 35,
            "GrainSize": 40,
        },
        "avoid": "Do NOT over-grain. Do NOT over-fade. Keep midtone richness.",
    },

    "portrait": {
        "keywords": ["人像", "portrait", "肖像", "人物"],
        "name_zh": "人像",
        "name_en": "Portrait",
        "description": (
            "Flattering skin tones. Soft contrast, gentle highlights. "
            "Warm temperature for inviting feel. Slight clarity reduction for skin smoothing. "
            "Orange luminance boost for glowing skin."
        ),
        "params": {
            "Exposure2012": 0.2,
            "Contrast2012": -10,
            "Highlights2012": -20,
            "Shadows2012": 25,
            "Temperature": 6500,
            "Vibrance": 10,
            "Saturation": -5,
            "Clarity2012": -15,
            "Texture": 15,
            "LuminanceAdjustmentOrange": 20,
            "LuminanceAdjustmentRed": 10,
            "SaturationAdjustmentOrange": -8,
        },
        "avoid": "Do NOT over-smooth. Do NOT make skin orange or red. Keep eyes sharp.",
    },

    "landscape": {
        "keywords": ["风光", "风景", "landscape", "scenery", "自然"],
        "name_zh": "风光",
        "name_en": "Landscape",
        "description": (
            "Rich, vivid, full dynamic range. Strong clarity and dehaze for depth. "
            "Boosted vibrance for sky and foliage. Full tonal range from blacks to whites."
        ),
        "params": {
            "Exposure2012": 0.1,
            "Contrast2012": 15,
            "Highlights2012": -40,
            "Shadows2012": 35,
            "Whites2012": 10,
            "Blacks2012": -10,
            "Temperature": 5500,
            "Vibrance": 30,
            "Saturation": 5,
            "Clarity2012": 25,
            "Dehaze": 15,
            "Texture": 20,
            "SaturationAdjustmentBlue": 15,
            "SaturationAdjustmentGreen": 10,
            "LuminanceAdjustmentBlue": -10,
        },
        "avoid": "Do NOT over-saturate. Keep it natural. Avoid neon-looking colors.",
    },
}


def match_styles(user_input: str) -> list[dict]:
    """Match user's style description to presets via keyword matching.

    Returns matched presets sorted by relevance (most keywords matched first).
    Supports Chinese and English keywords.
    """
    user_lower = user_input.lower()
    scored = []

    for key, preset in STYLE_PRESETS.items():
        hits = sum(1 for kw in preset["keywords"] if kw in user_lower)
        if hits > 0:
            scored.append((hits, key, preset))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [preset for _, _, preset in scored]


def blend_presets(presets: list[dict]) -> dict:
    """Blend multiple preset parameter sets, averaging overlapping values.

    First preset has highest priority for non-overlapping params.
    """
    if not presets:
        return {}
    if len(presets) == 1:
        return dict(presets[0]["params"])

    # Collect all params with weights (earlier = higher weight)
    param_values: dict[str, list[tuple[float, float]]] = {}
    for i, preset in enumerate(presets):
        weight = 1.0 / (i + 1)  # 1.0, 0.5, 0.33, ...
        for k, v in preset["params"].items():
            if k not in param_values:
                param_values[k] = []
            param_values[k].append((v, weight))

    result = {}
    for k, entries in param_values.items():
        total_weight = sum(w for _, w in entries)
        result[k] = sum(v * w for v, w in entries) / total_weight

        # Round appropriately
        if k in ("Exposure2012",):
            result[k] = round(result[k], 2)
        elif k == "Temperature":
            result[k] = int(round(result[k] / 100) * 100)
        else:
            result[k] = round(result[k])

    return result
