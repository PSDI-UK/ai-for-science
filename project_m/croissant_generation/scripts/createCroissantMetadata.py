import json
from pathlib import Path


def load_config(config_file):
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def main(config_file="MLTask_config.json"):
    """
    Create a Croissant metadata file from a template.

    Reads the template and output filename from the task-specific
    configuration file and creates the base Croissant JSON.

    Parameters
    ----------
    config_file : str or pathlib.Path
        Path to the MLTask_config.json file.
    """

    config_path = Path(config_file).resolve()
    base_dir = config_path.parent

    config = load_config(config_path)

    template_file = config.get("croissant_template_file", "croissantConstantsTemplate.json")
    output_file = config["croissant_output_file"]

    template_path = (base_dir / template_file).resolve()
    output_path = (base_dir / output_file).resolve()

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=4)

    print(f"Created {output_path} from template")


if __name__ == "__main__":
    main()