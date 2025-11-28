import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit_authenticator as stauth
from helpers import load_data, save_data

# -------------------------------------------------------
# CONFIGURAÇÕES DO APP
# -------------------------------------------------------
st.set_page_config(
    page_title="FinApp — Controle Financeiro",
    layout="wide",
    page_icon="💸"
)

# -------------------------------------------------------
# AUTENTICAÇÃO
# -------------------------------------------------------
def do_auth():
    try:
        credentials = st.secrets["credentials"]
        auth_settings = st.secrets["auth"]
    except Exception as e:
        st.error(f"Erro carregando credenciais: {e}")
        st.stop()

    authenticator = stauth.Authenticate(
        credentials,
        auth_settings["cookie_name"],
        auth_settings["key"],
        auth_settings["expiry_days"]
    )

    name, auth_status, username = authenticator.login(
        "Login",
        "main"
    )

    return auth_status, name, username, authenticator


auth_ok, auth_name, auth_user, authenticator = do_auth()

if not auth_ok:
    st.stop()

# -------------------------------------------------------
# INTERFACE PRINCIPAL
# -------------------------------------------------------
st.sidebar.title("FinApp 💸")
st.sidebar.write(f"**Logado como:** {auth_name}")

authenticator.logout("Sair", "sidebar")

st.title("Controle Financeiro — FinApp 💸")
st.write("Gerencie seus lançamentos financeiros de forma simples e segura.")

# -------------------------------------------------------
# CARREGAR DADOS
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
        st.success("Lançamento registrado com sucesso!")

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

        col1.metric("Receitas", f"R$ {receitas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("Despesas", f"R$ {despesas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("Saldo", f"R$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        resumo = df.groupby("tipo")["valor"].sum()
        st.bar_chart(resumo)
