from __future__ import annotations

import json
from pathlib import Path

from dataguard.sample_data_generator import main as generate_sample

ROOT = Path(__file__).resolve().parents[1]


def make_project(tmp_path: Path) -> Path:
    """Create an isolated data + config fixture for tests."""
    data_dir = tmp_path / "data" / "raw"
    generate_sample(output_dir=data_dir)
    config = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    for source in config["sources"].values():
        source["path"] = str(data_dir / Path(source["path"]).name)
    config["base_dir"] = str(tmp_path)
    config_path = tmp_path / "rules.json"
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return config_path
