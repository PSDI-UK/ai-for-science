from pathlib import Path
import sys

from MLTask_build_croissant_from_dcat import main as build_from_dcat_main
from MLTask_apply_user_inputs_to_croissant import main as apply_inputs_main
from MLTask_build_croissant_recordsets import main as build_recordsets_main
from MLTask_compute_croissant_distribution_fields import main as compute_fields_main


def run_all(config_file):
    """
    Run the full Croissant generation pipeline for a given task.

    Parameters
    ----------
    config_file : str or pathlib.Path
        Path to the MLTask_config.json file for the task.

    Usage example
    -------------
    python createCroissant_run.py ../MLTask1b/MLTask_config.json
    """

    config_path = Path(config_file).resolve()

    build_from_dcat_main(config_path)
    apply_inputs_main(config_path)
    build_recordsets_main(config_path)
    compute_fields_main(config_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python createCroissant_run.py <path_to_config>")
        sys.exit(1)

    run_all(sys.argv[1])