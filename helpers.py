# helpers.py

import pandas as pd

def format_brl(valor):
    try:
        s = f"{float(valor):,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def load_data():
    try:
        df = pd.read_csv("financas.csv")
        return df
    except:
        df = pd.DataFrame(columns=[
            "data", "tipo", "categoria", "descricao", "valor"
        ])
        return df

def save_data(df):
    df.to_csv("financas.csv", index=False)
