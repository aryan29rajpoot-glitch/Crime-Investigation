import pandas as pd


def parse_bank(file_path):
    df = pd.read_csv(file_path)

    df = df.dropna()

    return df.to_dict(orient="records")