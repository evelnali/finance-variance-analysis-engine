
"""Load and validate the project configuration from config/settings.yml."""
from pathlib import Path
import yaml

# Anchor paths to this file's location, so the pipeline works no matter with folder the command was run from. 
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.yml"

# Without this check the pipeline would run on and fail later with a bare KeyError,halfway through a load,
# with no indication which key was wrong.

REQUIRED_KEYS = [
    ("paths","raw_data"),
    ("paths","output"),
    ("paths","logs"),
    ("paths", "database"),
    ("materiality","absolute_threshold"),   
    ("materiality","percent_threshold"),
]

def load_settings():
    """Read settings.yml, verify the keys the pipeline depends on, and return it."""
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"No settings file found at: {SETTINGS_PATH}")

    with open(SETTINGS_PATH, "r") as f: 
        settings = yaml.safe_load(f)        

        # report every missing key at once, not just the first one found. 
    missing = []
    for section,key in REQUIRED_KEYS:
        if settings.get(section) is None or key not in settings[section]:
            missing.append(f"{section}.{key}")

        if missing:
            raise ValueError(f"settings.yml is missing required keys: {', '.join(missing)}")

    return settings

if __name__ == "__main__":
    # run this file directly to test the settings file. 
    settings = load_settings()
    threshold = settings["materiality"]["absolute_threshold"]
    percent = settings["materiality"]["percent_threshold"]

    print(f"Loaded {len(settings)} sections from {SETTINGS_PATH.name}")
    print(f"Materiality: ${threshold:,.2f} and {percent:.1f}%")
