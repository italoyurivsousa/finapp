import streamlit as st
import streamlit_authenticator as stauth
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# -------------------------------------------------------
#  PRIMEIRO: AUTENTICAÇÃO — SEM deepcopy, SEM recursão
# -------------------------------------------------------

def load_credentials_and_settings():
    # ---- CREDENCIAIS ----
    if "credentials" in st.secrets:
        creds = st.secrets["credentials"]
    else:
        # fallback seguro
        creds = {
            "usernames": {
                "admin": {
                    "name": "Administrador",
                    "email": "admin@example.com",
                    "password": "1234"  # pode mudar depois
                }
            }
        }

    # ---- CONFIGURAÇÕES DE COOKIE ----
    # Se existir "auth" no secrets, pega; senão usa defaults
    auth_settings = {
        "cookie_name": st.secrets.get("auth", {}).get("cookie_name", "finapp_cookie"),
        "key": st.secrets.get("auth", {}).get("key", "fallback_key_123"),
        "expiry_days": st.secrets.get("auth", {}).get("expiry_days", 1)
    }

    return creds, auth_settings

import streamlit_authenticator as stauth

def do_auth():
    creds, auth_settings = load_credentials_and_settings()

    try:
        authenticator = stauth.Authenticate(
            creds,
            auth_settings["cookie_name"],
            auth_settings["key"],
            auth_settings["expiry_days"]
        )

        name, status, username = authenticator.login("Login", "main")

        if status is False:
            st.error("Usuário ou senha incorretos.")
        elif status is None:
            st.warning("Digite usuário e senha.")

        return status, name, username, authenticator

    except Exception as e:
        st.error(f"Erro inicializando autenticação: {e}")
        return None, None, None, None



# -------------------------------------------------------
#  BANCO DE DADOS
# -------------------------------------------------------

DB = "financas.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            limite REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor REAL NOT NULL,
            conta_id INTEGER,
            FOREIGN KEY(conta_id) REFERENCES contas(id)
        )
    """)

    conn.commit()
    conn.close()

def exec_query(query, params=()):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

def fetch_query(query, params=()):
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# -------------------------------------------------------
#  PÁGINAS DO APP
# -------------------------------------------------------

def page_registro():
    st.header("Registrar Receita / Despesa")

    tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
    categoria = st.text_input("Categoria (ex: Água, Internet, Cartão X, Salário...)")
    valor = st.number_input("Valor", min_value=0.0, step=0.01)
    data = st.date_input("Data", datetime.now())
    contas = fetch_query("SELECT id, nome FROM contas")

    conta_id = st.selectbox("Conta", contas["nome"].tolist()) if len(contas) else None
    if conta_id:
        conta_id = contas[contas["nome"] == conta_id]["id"].iloc[0]

    if st.button("Salvar"):
        exec_query(
            "INSERT INTO transacoes (data, tipo, categoria, valor, conta_id) VALUES (?, ?, ?, ?, ?)",
            (data.isoformat(), tipo, categoria, valor, conta_id)
        )
        st.success("Transação salva!")

def page_contas():
    st.header("Gerenciar Contas e Cartões")

    nome = st.text_input("Nome da Conta / Cartão")
    tipo = st.selectbox("Tipo", ["Conta Bancária", "Cartão de Crédito"])
    limite = st.number_input("Limite (se for cartão)", min_value=0.0, step=10.0)

    if st.button("Salvar"):
        exec_query(
            "INSERT INTO contas (nome, tipo, limite) VALUES (?, ?, ?)",
            (nome, tipo, limite)
        )
        st.success("Conta salva!")

    st.subheader("Contas Registradas")
    st.dataframe(fetch_query("SELECT * FROM contas"))


def page_dashboard():
    st.header("Dashboard Financeiro")

    df = fetch_query("SELECT * FROM transacoes")

    if df.empty:
        st.warning("Sem transações registradas.")
        return

    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.to_period("M")

    st.subheader("Resumo Mensal")
    st.dataframe(
        df.groupby(["mes", "tipo"])["valor"].sum().unstack().fillna(0)
    )

    st.subheader("Por Categoria")
    st.dataframe(
        df.groupby(["categoria"])["valor"].sum().sort_values(ascending=False)
    )


# -------------------------------------------------------
#  MAIN
# -------------------------------------------------------

def main():
    st.set_page_config(page_title="Finanças", layout="wide")

    st.title("Controle Financeiro — App")
    st.caption("Registre receitas, despesas, contas, cartões e visualize tudo em um dashboard.")

    init_db()

    auth_ok, auth_name, auth_user, authenticator = do_auth()

    if auth_ok:
        authenticator.logout("Sair", "sidebar")

        página = st.sidebar.radio(
            "Navegação",
            ["Registro", "Contas/Cartões", "Dashboard"]
        )

        if página == "Registro":
            page_registro()
        elif página == "Contas/Cartões":
            page_contas()
        elif página == "Dashboard":
            page_dashboard()

    elif auth_ok is False:
        st.error("Usuário ou senha incorretos.")
    else:
        st.info("Informe login e senha.")


if __name__ == "__main__":
    main()
