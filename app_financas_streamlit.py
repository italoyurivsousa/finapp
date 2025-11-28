import streamlit as st
import pandas as pd
from datetime import datetime
from helpers import load_data, save_data, load_cards, save_cards # Importando as novas funções


# ============================================================
# CONFIGURAÇÃO DO APP
# ============================================================
st.set_page_config(
    page_title="FinApp — Controle Financeiro",
    layout="wide",
    page_icon="💸",
)


# ============================================================
# LAYOUT / SIDEBAR (Sem autenticação)
# ============================================================
st.sidebar.title("FinApp 💸")

st.title("Controle Financeiro — FinApp 💸")
st.write("Gerencie seus lançamentos de forma simples e segura.")


# ============================================================
# CARREGAR DADOS E INICIALIZAR SESSION STATE
# ============================================================
df = load_data()

# Inicializa o session_state para df_cards se ainda não existir
if "df_cards" not in st.session_state:
    st.session_state["df_cards"] = load_cards()


# ============================================================
# MENU
# ============================================================
aba = st.sidebar.radio(
    "Menu",
    ["Registrar lançamento", "Visualizar registros", "Dashboard", "Gerenciar Cartões"] # Adicionando nova aba
)


# ============================================================
# 1 — REGISTRAR
# ============================================================
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


# ============================================================
# 2 — VISUALIZAÇÃO
# ============================================================
elif aba == "Visualizar registros":
    st.subheader("Registros financeiros")
    st.dataframe(df)


# ============================================================
# 3 — DASHBOARD
# ============================================================
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


# ============================================================
# 4 — GERENCIAR CARTÕES
# ============================================================
elif aba == "Gerenciar Cartões":
    st.subheader("Cadastro de Cartões de Crédito")

    with st.form("form_cartao"):
        nome = st.text_input("Nome do Cartão (Ex: Nubank, Inter)")
        limite = st.number_input("Limite Total (R$)", min_value=0.0, step=100.0)
        vencimento = st.number_input("Dia de Vencimento da Fatura", min_value=1, max_value=31, step=1)
        
        submitted = st.form_submit_button("Cadastrar Cartão")

        if submitted:
            if nome and limite > 0 and 1 <= vencimento <= 31:
                novo_cartao = pd.DataFrame([{
                    "nome": nome,
                    "limite": limite,
                    "vencimento": vencimento,
                }])

                # Usa st.session_state para modificar o DataFrame
                st.session_state["df_cards"] = pd.concat([st.session_state["df_cards"], novo_cartao], ignore_index=True)
                save_cards(st.session_state["df_cards"])
                st.success(f"Cartão '{nome}' cadastrado com sucesso!")
            else:
                st.error("Por favor, preencha todos os campos corretamente.")

    st.markdown("---")
    st.subheader("Cartões Cadastrados")
    if st.session_state["df_cards"].empty:
        st.info("Nenhum cartão cadastrado ainda.")
    else:
        st.dataframe(st.session_state["df_cards"])
