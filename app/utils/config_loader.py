import yaml
import os
from dotenv import load_dotenv

# Load environment variables once at module level
load_dotenv()

def load_config(config_path: str = "app/config/config.yaml") -> dict:
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    return config