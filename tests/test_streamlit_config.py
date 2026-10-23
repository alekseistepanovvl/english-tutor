import tomllib
from pathlib import Path


def test_streamlit_hides_system_error_details() -> None:
    config_path = Path(__file__).parents[1] / ".streamlit" / "config.toml"

    with config_path.open("rb") as config_file:
        config = tomllib.load(config_file)

    assert config["client"]["showErrorDetails"] == "none"
