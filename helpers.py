import pandas as pd
import os

FILE_PATH = "finapp_data.csv"
CARDS_FILE_PATH = "finapp_cards.csv"

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


def load_cards():
    if os.path.exists(CARDS_FILE_PATH):
        try:
            return pd.read_csv(CARDS_FILE_PATH)
        except:
            return pd.DataFrame(columns=["nome", "limite", "vencimento"])
    else:
        return pd.DataFrame(columns=["nome", "limite", "vencimento"])


def save_cards(df_cards):
    df_cards.to_csv(CARDS_FILE_PATH, index=False)
