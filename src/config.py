
"""Load and validate the project configuration from config/settings.yml."""
from pathlib import Path
import yaml

# Anchor paths to this file's location, so the pipeline works no matter which folder the command was run from. 
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yml"

# Without this check the pipeline would run on and fail later with a bare KeyError,halfway through a load,
# with no indication which key was wrong.

REQUIRED_KEYS = [
    ("paths","raw_data"),
    ("paths","output"),
    ("paths","logs"),
    ("paths", "database"),
    ("materiality","tangible","absolute_threshold"),   
    ("materiality","tangible","percent_threshold"),
    ("materiality","intangible","absolute_threshold"),   
    ("materiality","intangible","percent_threshold"),
    ("extracts",),
]

def load_settings():
    """Read settings.yml, verify the keys the pipeline depends on, and return it."""
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"No settings file found at: {SETTINGS_PATH}")

    with open(SETTINGS_PATH, "r") as f: 
        settings = yaml.safe_load(f)        

    # report every missing key at once, not just the first one found. 
    missing = []
    for path in REQUIRED_KEYS:
        # walk down one level at a time. here starts as the whole settings dic and moves deeper with each key
        # in the path, so one loop handles keys at any depth.
        here = settings
        for key in path:
            # isinstance(x,dict) asks "is this still something I can look inside? "
            # if a key holds a plan number, there is nothing underneath it to keep walking into.
            if not isinstance(here, dict) or key not in here:
                missing.append(".".join(path))
                break
            here = here[key]

    if missing:
        raise ValueError(f"settings.yml is missing required keys: {', '.join(missing)}")

    return settings


if __name__ == "__main__":
    # run this file directly to test the settings file. 
    settings = load_settings()

    print(f"Loaded {len[settings]} sections from {SETTINGS_PATH.name}")

    for family, limits in settings["materiality"].item():
        print(
            f". {family:<12}   ${limits['absolute_threshold']:>8,.0f}"
            f". and {limits['percent_threshold']:.1f}%"
            )
    
    print(f"  {len(settings['extracts'])} extracts declared")
