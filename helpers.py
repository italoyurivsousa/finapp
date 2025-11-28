import pandas as pd
import os

FILE_PATH = "finapp_data.csv"

def load_data():
    if os.path.exists(FILE_PATH):
        try:
            return pd.read_csv(FILE_PATH)
        except:
            return pd.DataFrame(columns=["data", "tipo", "categoria", "descricao", "valor"])
    else:
        return pd.DataFrame(columns=["data", "tipo", "categoria", "descricao", "valor"])


def save_data(df):
    df.to_csv(FILE_PATH, index=False)
