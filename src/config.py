"""Central configuration — all literals live here, never scattered."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
GEN_TEMPERATURE = 0.3
JUDGE_TEMPERATURE = 0.0
MAX_TOKENS = 1024

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"
RESULTS_DIR = BASE_DIR / "results"
SCENARIOS_PATH = DATA_DIR / "scenarios.json"

METRIC_WEIGHTS = {
    "length_ratio": 0.3,
    "sentence_length": 0.2,
    "filler_density": 0.2,
    "clarity": 0.3,
}
