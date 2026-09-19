import pandas as pd


def parse_cdr(file_path):

    df = pd.read_csv(
        file_path,
        dtype={
            "caller": str,
            "receiver": str
        }
    )

    df = df.dropna()

    # Restore +91 prefix if CSV stored numbers without +
    df["caller"] = df["caller"].apply(
        lambda x: "+91" + x[-10:]
        if not x.startswith("+91")
        else x
    )

    df["receiver"] = df["receiver"].apply(
        lambda x: "+91" + x[-10:]
        if not x.startswith("+91")
        else x
    )

    return df.to_dict(orient="records")