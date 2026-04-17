# Task Structure

The Croissant generation code is shared across tasks, while inputs and outputs are task-specific.

## Shared components

These are generally reused across tasks:

- `croissantConstantsTemplate.json`
- `croissantFieldsThatMapToDCAT.csv`
- `croissantFieldsThatNeedToBeComputed.txt`
- pipeline scripts in `scripts/`

## Task-specific components

Each task has its own folder, for example:

- `ML_Task1a/`
- `ML_Task1b/`
- `ML_Task2/`

These folders contain task-specific files such as:

- `MLTask_config.json`
- `croissantFieldsFromUserInputs_MLTaskX.json`
- `datasetFields.json`
- task-specific CSV files
- output Croissant metadata files

## Configuration-driven design

The pipeline scripts are designed to work from the task config file, so the same shared code can be reused for different tasks.