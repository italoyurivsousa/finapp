# app_financas_streamlit.py

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from helpers import load_data, save_data
from datetime import datetime

st.set_page_config(
    page_title="Controle Financeiro — App",
    layout="wide",
    page_icon="💸"
)

# =====================================================
# 1. Autenticação
# =====================================================

def prepare_credentials():
    """Converte st.secrets para dict normal (essencial)."""
    creds_raw = st.secrets.get("credentials", {})
    users_block = creds_raw.get("users", {})

    credentials = {"usernames": {}}

    for username, info in users_block.items():
        credentials["usernames"][username] = {
            "name": info.get("name", ""),
            "password": info.get("password", "")
        }

    auth_settings_raw = st.secrets.get("auth_settings", {})

    return credentials, auth_settings_raw


def do_auth():
    """Executa o fluxo de autenticação."""
    try:
        credentials, auth_settings = prepare_credentials()

        authenticator = stauth.Authenticate(
            credentials,
            auth_settings.get("cookie_name", "cookie"),
            auth_settings.get("cookie_key", "key"),
            auth_settings.get("cookie_expiry_days", 3)
        )

        name, auth_status, username = authenticator.login("Login", "main")

        if auth_status:
            return True, name, username, authenticator
        elif auth_status is False:
            st.error("Usuário ou senha incorretos.")
        else:
            st.info("Informe login e senha.")

        return False, None, None, None

    except Exception as e:
        st.error(f"Erro inicializando autenticação: {e}")
        return False, None, None, None


auth_ok, auth_name, auth_user, authenticator = do_auth()

if not auth_ok:
    st.stop()

# =====================================================
# Layout
# =====================================================

st.title("Controle Financeiro — App 💸")
st.write("Registre receitas, despesas, contas e visualize tudo em um dashboard.")

authenticator.logout("Sair", "sidebar")
st.sidebar.write(f"**Logado como:** {auth_name}")

# =====================================================
# Carregamento de dados
# =====================================================

df = load_data()

# =====================================================
# Aba de navegação
# =====================================================

aba = st.sidebar.radio(
    "Menu",
    ["Registrar lançamento", "Visualizar registros", "Dashboard"]
)

# =====================================================
# 1. Registrar lançamento
# =====================================================

if aba == "Registrar lançamento":
    st.subheader("Novo lançamento")

    data = st.date_input("Data", datetime.today())
    tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
    categoria = st.text_input("Categoria")
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", step=0.01)

    if st.button("Salvar lançamento"):
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

# =====================================================
# 2. Visualizar registros
# =====================================================

elif aba == "Visualizar registros":
    st.subheader("Registros financeiros")
    st.dataframe(df)

# =====================================================
# 3. Dashboard simples
# =====================================================

elif aba == "Dashboard":
    st.subheader("Resumo financeiro")

    if df.empty:
        st.info("Nenhum dado registrado ainda.")
    else:
        receitas = df[df["tipo"] == "Receita"]["valor"].sum()
        despesas = df[df["tipo"] == "Despesa"]["valor"].sum()
        saldo = receitas - despesas

        col1, col2, col3 = st.columns(3)

        col1.metric("Receitas", f"R$ {receitas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("Despesas", f"R$ {despesas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("Saldo", f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.bar_chart(df.groupby("tipo")["valor"].sum())
