from experiments.helpers import cases_for

def build_cases(config, csv_path=None):
    return cases_for("quintic", config, csv_path)
