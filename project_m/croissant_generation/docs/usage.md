# Usage

## Running the full pipeline

From the `scripts/` folder:

```bash
python createCroissant_run.py ../ML_Task1a/MLTask_config.json
python createCroissant_run.py ../ML_Task1b/MLTask_config.json
python createCroissant_run.py ../ML_Task2/MLTask_config.json
```

## Running individual steps

You can also run individual scripts with a task-specific config file. Example:
```bash
python MLTask_csvgen.py ../ML_Task1a/MLTask_config.json
python MLTask_build_croissant_from_dcat.py ../ML_Task1a/MLTask_config.json
python MLTask_apply_user_inputs_to_croissant.py ../ML_Task1a/MLTask_config.json
python MLTask_build_croissant_recordsets.py ../ML_Task1a/MLTask_config.json
python MLTask_compute_croissant_distribution_fields.py ../ML_Task1a/MLTask_config.json
```