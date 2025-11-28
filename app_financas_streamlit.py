import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from datetime import datetime
from helpers import load_data, save_data
import copy

# -------------------------------------------------------
# CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="FinApp — Controle Financeiro",
    layout="wide",
    page_icon="💸"
)

# -------------------------------------------------------
# 🔐 CARREGA CREDENCIAIS
# -------------------------------------------------------
def load_credentials():
    try:
        raw_creds = st.secrets["credentials"]
        raw_auth = st.secrets["auth"]

        # converter para dict normal (sem deepcopy)
        credentials = {
            "usernames": {}
        }

        for username, data in raw_creds["usernames"].items():
            credentials["usernames"][username] = {
                "email": data["email"],
                "name": data["name"],
                "password": data["password"],
            }

        auth_settings = {
            "cookie_name": raw_auth["cookie_name"],
            "key": raw_auth["key"],
            "expiry_days": raw_auth["expiry_days"],
        }

        return credentials, auth_settings

    except Exception as e:
        st.error(f"Erro carregando credenciais: {e}")
        st.stop()


# -------------------------------------------------------
# 🔐 AUTENTICAÇÃO
# -------------------------------------------------------
def do_auth():
    credentials, auth_settings = load_credentials()

    authenticator = stauth.Authenticate(
        credentials,
        auth_settings["cookie_name"],
        auth_settings["key"],
        auth_settings["expiry_days"]
    )

    name, auth_status, username = authenticator.login("Login", location="main")

    return auth_status, name, username, authenticator

# -------------------------------------------------------
# INICIA AUTENTICAÇÃO
# -------------------------------------------------------
auth_ok, auth_name, auth_user, authenticator = do_auth()

if not auth_ok:
    st.stop()

# -------------------------------------------------------
# LAYOUT PRINCIPAL
# -------------------------------------------------------
st.sidebar.title("FinApp 💸")
st.sidebar.write(f"**Logado como:** {auth_name}")
authenticator.logout("Sair", "sidebar")

st.title("Controle Financeiro — FinApp 💸")
st.write("Gerencie seus lançamentos de forma simples e segura.")

# -------------------------------------------------------
# CARREGAMENTO DE DADOS
# -------------------------------------------------------
df = load_data()

# -------------------------------------------------------
# MENU
# -------------------------------------------------------
aba = st.sidebar.radio(
    "Menu",
    ["Registrar lançamento", "Visualizar registros", "Dashboard"]
)

# -------------------------------------------------------
# 1. REGISTRAR LANÇAMENTO
# -------------------------------------------------------
if aba == "Registrar lançamento":
    st.subheader("Novo lançamento")

    data = st.date_input("Data", datetime.today())
    tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
    categoria = st.text_input("Categoria")
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", step=0.01)

    if st.button("Salvar"):
        novo = pd.DataFrame([{
            "data": data.strftime("%Y-%m-%d"),
            "tipo": tipo,
            "categoria": categoria,
            "descricao": descricao,
            "valor": float(valor),
        }])

        df = pd.concat([df, novo], ignore_index=True)
        save_data(df)
        st.success("Lançamento registrado!")

# -------------------------------------------------------
# 2. VISUALIZAR REGISTROS
# -------------------------------------------------------
elif aba == "Visualizar registros":
    st.subheader("Registros financeiros")
    st.dataframe(df)

# -------------------------------------------------------
# 3. DASHBOARD
# -------------------------------------------------------
elif aba == "Dashboard":
    st.subheader("Resumo financeiro")

    if df.empty:
        st.info("Nenhum dado registrado ainda.")
    else:
        receitas = df[df["tipo"] == "Receita"]["valor"].sum()
        despesas = df[df["tipo"] == "Despesa"]["valor"].sum()
        saldo = receitas - despesas

        col1, col2, col3 = st.columns(3)

        def fmt(x):
            return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        col1.metric("Receitas", fmt(receitas))
        col2.metric("Despesas", fmt(despesas))
        col3.metric("Saldo", fmt(saldo))

        st.bar_chart(df.groupby("tipo")["valor"].sum())
