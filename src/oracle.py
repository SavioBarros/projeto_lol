import os
import pandas as pd

class OracleLoader:
    def __init__(self, data_dir="./oracle_csvs"):
        self.data_dir = data_dir

    def load_latest(self):
        files = [f for f in os.listdir(self.data_dir) if f.endswith(".csv")]
        if not files:
            raise FileNotFoundError("Nenhum CSV encontrado em oracle_csvs")
        latest = sorted(files)[-1]
        return pd.read_csv(os.path.join(self.data_dir, latest))
