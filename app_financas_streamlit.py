import streamlit as st
import pandas as pd
from datetime import datetime
from uuid import uuid4
from supabase import create_client, Client

# ============================================================
# CONFIG — Supabase (use Streamlit secrets)
# ============================================================
st.set_page_config(page_title="FinApp — Controle Financeiro", layout="wide", page_icon="💸")

SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Por favor configure SUPABASE_URL e SUPABASE_KEY em Secrets do Streamlit Cloud.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# HELPERS — operações com Supabase (compatível com supabase-py atual)
# ============================================================

def fetch_table(table_name):
    try:
        res = supabase.table(table_name).select("*").execute()
        data = res.data or []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao buscar {table_name}: {e}")
        return pd.DataFrame()


def insert_row(table_name, row: dict):
    try:
        res = supabase.table(table_name).insert(row).execute()
        return res.data[0] if getattr(res, "data", None) else None
    except Exception as e:
        st.error(f"Erro ao inserir em {table_name}: {e}")
        return None


def update_row(table_name, row_id, updates: dict):
    if not row_id:
        st.error("update_row: row_id não informado")
        return None
    try:
        res = supabase.table(table_name).update(updates).eq("id", row_id).execute()
        return res.data if getattr(res, "data", None) is not None else []
    except Exception as e:
        st.error(f"Erro ao atualizar {table_name}: {e}")
        return None


def delete_row(table_name, row_id):
    if not row_id:
        st.error("delete_row: row_id não informado")
        return None
    try:
        res = supabase.table(table_name).delete().eq("id", row_id).execute()
        return res.data if getattr(res, "data", None) is not None else []
    except Exception as e:
        st.error(f"Erro ao deletar {table_name}: {e}")
        return None

# ============================================================
# SCHEMA column lists (for DataFrame consistency)
# ============================================================
TX_COLS = ["id", "data", "tipo", "categoria_id", "categoria_nome", "descricao", "valor", "conta_id", "conta_nome", "cartao_id", "cartao_nome"]
CARD_COLS = ["id", "nome", "limite", "vencimento"]
ACCOUNT_COLS = ["id", "nome", "saldo_inicial"]
CAT_COLS = ["id", "nome", "tipo", "default_conta_id", "default_cartao_id"]


def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

# ============================================================
# LOAD DATA FROM SUPABASE
# ============================================================
try:
    _tx = fetch_table("transactions")
    _cards = fetch_table("cards")
    _accounts = fetch_table("accounts")
    _cats = fetch_table("categories")
except Exception as e:
    st.error(f"Erro ao conectar ao Supabase: {e}")
    st.stop()

_tx = ensure_columns(_tx, TX_COLS) if not _tx.empty else pd.DataFrame(columns=TX_COLS)
_cards = ensure_columns(_cards, CARD_COLS) if not _cards.empty else pd.DataFrame(columns=CARD_COLS)
_accounts = ensure_columns(_accounts, ACCOUNT_COLS) if not _accounts.empty else pd.DataFrame(columns=ACCOUNT_COLS)
_cats = ensure_columns(_cats, CAT_COLS) if not _cats.empty else pd.DataFrame(columns=CAT_COLS)

# session state mirrors DB
if "tx" not in st.session_state:
    st.session_state.tx = _tx.copy()
if "cards" not in st.session_state:
    st.session_state.cards = _cards.copy()
if "accounts" not in st.session_state:
    st.session_state.accounts = _accounts.copy()
if "cats" not in st.session_state:
    st.session_state.cats = _cats.copy()

# utility
def id_to_name(df, id_, default=""):
    if not id_ or pd.isna(id_):
        return default
    row = df[df["id"] == id_]
    if not row.empty:
        return str(row.iloc[0]["nome"]) if "nome" in row.columns else default
    return default


def fmt(x):
    try:
        v = float(x)
    except Exception:
        v = 0.0
    s = f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s

# ============================================================
# LAYOUT
# ============================================================
st.sidebar.title("FinApp 💸")
st.title("Controle Financeiro — FinApp 💸")
st.write("Gerencie seus lançamentos, cartões, contas e categorias (agora com Supabase).")

menu = st.sidebar.radio("Menu", [
    "Registrar lançamento",
    "Visualizar registros",
    "Dashboard",
    "Gerenciar Cartões",
    "Gerenciar Contas",
    "Gerenciar Categorias",
])

# ============================================================
# 1 - REGISTRAR LANÇAMENTO (INSERT via Supabase)
# ============================================================
if menu == "Registrar lançamento":
    st.subheader("Novo lançamento")

    with st.form("form_tx"):
        data = st.date_input("Data", datetime.today())
        tipo = st.selectbox("Tipo", ["Receita", "Despesa"])

        cat_map = {r["nome"]: r["id"] for _, r in st.session_state.cats.iterrows()} if not st.session_state.cats.empty else {}
        cat_options = ["-- Nova categoria --"] + list(cat_map.keys())
        cat_choice = st.selectbox("Categoria", cat_options)
        if cat_choice == "-- Nova categoria --":
            nova_cat = st.text_input("Nome da nova categoria")
            nova_cat_tipo = st.selectbox("Tipo da categoria", ["Despesa", "Receita", "Ambas"])
        else:
            nova_cat = None
            nova_cat_tipo = None

        descricao = st.text_input("Descrição")
        valor = st.number_input("Valor", step=0.01, format="%.2f")

        acc_map = {r["nome"]: r["id"] for _, r in st.session_state.accounts.iterrows()} if not st.session_state.accounts.empty else {}
        acc_choice = st.selectbox("Conta (opcional)", ["-- Nenhuma --"] + list(acc_map.keys()))

        card_map = {r["nome"]: r["id"] for _, r in st.session_state.cards.iterrows()} if not st.session_state.cards.empty else {}
        card_choice = st.selectbox("Cartão (opcional)", ["-- Nenhum --"] + list(card_map.keys()))

        submitted = st.form_submit_button("Salvar")

        if submitted:
            # create category if needed
            if nova_cat:
                cid = str(uuid4())
                # não enviamos default_conta_id/default_cartao_id se vazios
                new_cat = {"id": cid, "nome": nova_cat, "tipo": nova_cat_tipo or "Ambas"}
                created = insert_row("categories", new_cat)
                if created is not None:
                    st.session_state.cats = pd.concat([st.session_state.cats, pd.DataFrame([created])], ignore_index=True)
                    categoria_id = cid
                    categoria_nome = nova_cat
                else:
                    st.error("Falha ao criar categoria. Operação abortada.")
                    st.stop()
            else:
                categoria_id = cat_map.get(cat_choice)
                categoria_nome = cat_choice if cat_choice != "-- Nenhuma --" else None

            tx_id = str(uuid4())
            acc_id = acc_map.get(acc_choice)
            acc_name = acc_choice if acc_choice not in ["-- Nenhuma --"] else None
            card_id = card_map.get(card_choice)
            card_name = card_choice if card_choice not in ["-- Nenhum --"] else None

            # construir payload evitando enviar "" para campos UUID
            novo = {
                "id": tx_id,
                "data": data.strftime("%Y-%m-%d"),
                "tipo": tipo,
                "descricao": descricao,
                "valor": float(valor),
            }
            if categoria_id:
                novo["categoria_id"] = categoria_id
                novo["categoria_nome"] = categoria_nome
            if acc_id:
                novo["conta_id"] = acc_id
                novo["conta_nome"] = acc_name
            if card_id:
                novo["cartao_id"] = card_id
                novo["cartao_nome"] = card_name

            inserted = insert_row("transactions", novo)
            if inserted:
                # padroniza os campos no DataFrame local (usar None -> vazio para exibição)
                df_row = inserted.copy()
                st.session_state.tx = pd.concat([st.session_state.tx, pd.DataFrame([df_row])], ignore_index=True)
                st.success("Lançamento registrado com sucesso!")

# ============================================================
# 2 - VISUALIZAR E EDITAR (UPDATE / DELETE via Supabase)
# ============================================================
elif menu == "Visualizar registros":
    st.subheader("Registros financeiros")

    if st.session_state.tx.empty:
        st.info("Nenhum registro ainda.")
    else:
        df_view = st.session_state.tx.copy()
        cols = st.multiselect("Colunas a exibir", df_view.columns.tolist(), default=["data", "tipo", "categoria_nome", "descricao", "valor", "conta_nome", "cartao_nome"]) 
        df_view_to_show = df_view[cols]
        st.dataframe(df_view_to_show)

        st.markdown("---")
        st.write("### Editar / Excluir lançamento")
        id_map = {r["id"]: f"{r['data']} - {r['descricao']} ({fmt(r['valor'])})" for _, r in st.session_state.tx.iterrows()}
        sel = st.selectbox("Selecione lançamento", ["--" ] + [f"{k} | {v}" for k, v in id_map.items()])
        if sel and sel != "--":
            tx_id = sel.split(" | ")[0]
            row = st.session_state.tx[st.session_state.tx["id"] == tx_id].iloc[0]

            with st.form("edit_tx"):
                new_data = st.date_input("Data", datetime.strptime(row["data"], "%Y-%m-%d"))
                new_tipo = st.selectbox("Tipo", ["Receita", "Despesa"], index=0 if row["tipo"]=="Receita" else 1)
                new_desc = st.text_input("Descrição", value=row["descricao"])
                new_val = st.number_input("Valor", value=float(row["valor"]), step=0.01)
                if st.form_submit_button("Salvar alterações"):
                    updates = {"data": new_data.strftime("%Y-%m-%d"), "tipo": new_tipo, "descricao": new_desc, "valor": float(new_val)}
                    res = update_row("transactions", tx_id, updates)
                    if res is not None:
                        st.session_state.tx.loc[st.session_state.tx["id"] == tx_id, ["data","tipo","descricao","valor"]] = [updates["data"], updates["tipo"], updates["descricao"], updates["valor"]]
                        st.success("Registro atualizado.")

            if st.button("Excluir lançamento", key=f"del_{tx_id}"):
                res = delete_row("transactions", tx_id)
                if res is not None:
                    st.session_state.tx = st.session_state.tx[st.session_state.tx["id"] != tx_id]
                    st.success("Registro excluído.")

# ============================================================
# 3 - DASHBOARD
# ============================================================
elif menu == "Dashboard":
    st.subheader("Resumo financeiro")

    df = st.session_state.tx.copy()
    if df.empty:
        st.info("Nenhum dado registrado ainda.")
    else:
        df["valor"] = df["valor"].astype(float)

        receitas = df[df["tipo"] == "Receita"]["valor"].sum()
        despesas = df[df["tipo"] == "Despesa"]["valor"].sum()
        saldo = receitas - despesas

        col1, col2, col3 = st.columns(3)
        col1.metric("Receitas", fmt(receitas))
        col2.metric("Despesas", fmt(despesas))
        col3.metric("Saldo (Receitas - Despesas)", fmt(saldo))

        st.markdown("---")
        st.write("### Saldo por conta")
        accounts = st.session_state.accounts.copy()
        if not accounts.empty:
            accounts["saldo_inicial"] = accounts["saldo_inicial"].astype(float)
            account_saldos = []
            for _, a in accounts.iterrows():
                aid = a["id"]
                movimento = df[df["conta_id"] == aid]["valor"].sum()
                total = a["saldo_inicial"] + movimento
                account_saldos.append({"conta": a["nome"], "saldo": total})
            st.dataframe(pd.DataFrame(account_saldos))

        st.markdown("---")
        st.write("### Uso por categoria")
        cat_sum = df.groupby("categoria_nome")["valor"].sum().sort_values(ascending=False)
        st.bar_chart(cat_sum)

        st.markdown("---")
        st.write("### Cartões — limite x usado")
        cards = st.session_state.cards.copy()
        if not cards.empty:
            cards["limite"] = cards["limite"].astype(float)
            card_summaries = []
            for _, c in cards.iterrows():
                cid = c["id"]
                usado = df[df["cartao_id"] == cid]["valor"].sum()
                restante = c["limite"] - usado
                card_summaries.append({"cartao": c["nome"], "limite": c["limite"], "usado": usado, "restante": restante})
            st.dataframe(pd.DataFrame(card_summaries))

        st.markdown("---")
        st.write("### Séries temporais — lançamentos por mês")
        df["data"] = pd.to_datetime(df["data"]) 
        monthly = df.set_index("data").resample('M')["valor"].sum()
        st.line_chart(monthly)

# ============================================================
# 4 - GERENCIAR CARTÕES (CRUD)
# ============================================================
elif menu == "Gerenciar Cartões":
    st.subheader("Cadastro de Cartões de Crédito — CRUD")

    cards = st.session_state.cards

    with st.expander("Cadastrar novo cartão"):
        with st.form("form_cartao"):
            nome = st.text_input("Nome do Cartão (Ex: Nubank, Inter)")
            limite = st.number_input("Limite Total (R$)", min_value=0.0, step=50.0)
            vencimento = st.number_input("Dia de Vencimento da Fatura", min_value=1, max_value=31, step=1)
            if st.form_submit_button("Cadastrar Cartão"):
                if nome:
                    cid = str(uuid4())
                    novo = {"id": cid, "nome": nome, "limite": float(limite), "vencimento": int(vencimento)}
                    inserted = insert_row("cards", novo)
                    if inserted is not None:
                        st.session_state.cards = pd.concat([st.session_state.cards, pd.DataFrame([inserted])], ignore_index=True)
                        st.success(f"Cartão '{nome}' cadastrado.")
                else:
                    st.error("Preencha o nome do cartão.")

    st.markdown("---")
    st.write("### Cartões cadastrados")
    if st.session_state.cards.empty:
        st.info("Nenhum cartão cadastrado ainda.")
    else:
        st.dataframe(st.session_state.cards)

        st.write("#### Editar / Excluir cartão")
        sel = st.selectbox("Selecione cartão", ["--"] + st.session_state.cards["nome"].tolist())
        if sel and sel != "--":
            row = st.session_state.cards[st.session_state.cards["nome"] == sel].iloc[0]
            with st.form("edit_card"):
                n_nome = st.text_input("Nome", value=row["nome"])
                n_limite = st.number_input("Limite", value=float(row["limite"]), step=50.0)
                n_venc = st.number_input("Vencimento", value=int(row["vencimento"]), min_value=1, max_value=31)
                if st.form_submit_button("Salvar alterações"):
                    updates = {"nome": n_nome, "limite": float(n_limite), "vencimento": int(n_venc)}
                    res = update_row("cards", row["id"], updates)
                    if res is not None:
                        st.session_state.cards.loc[st.session_state.cards["id"] == row["id"], ["nome","limite","vencimento"]] = [n_nome, float(n_limite), int(n_venc)]
                        st.success("Cartão atualizado.")
            if st.button("Excluir cartão"):
                linked = st.session_state.tx[st.session_state.tx["cartao_id"] == row["id"]]
                if not linked.empty:
                    st.warning("Existem lançamentos vinculados a esse cartão. Ao excluir, as referências serão removidas.")
                    if st.button("Confirmar exclusão deste cartão"):
                        # limpar referências em transactions usando NULL
                        try:
                            supabase.table("transactions").update({"cartao_id": None, "cartao_nome": None}).eq("cartao_id", row["id"]).execute()
                        except Exception as e:
                            st.error(f"Falha ao limpar referências do cartão: {e}")
                        res = delete_row("cards", row["id"])
                        if res is not None:
                            st.session_state.tx.loc[st.session_state.tx["cartao_id"] == row["id"], ["cartao_id","cartao_nome"]] = [None, None]
                            st.session_state.cards = st.session_state.cards[st.session_state.cards["id"] != row["id"]]
                            st.success("Cartão excluído e referências limpas.")
                else:
                    res = delete_row("cards", row["id"])
                    if res is not None:
                        st.session_state.cards = st.session_state.cards[st.session_state.cards["id"] != row["id"]]
                        st.success("Cartão excluído.")

# ============================================================
# 5 - GERENCIAR CONTAS (CRUD)
# ============================================================
elif menu == "Gerenciar Contas":
    st.subheader("Gerenciar Contas Bancárias — CRUD")

    with st.expander("Cadastrar nova conta"):
        with st.form("form_conta"):
            nome = st.text_input("Nome da Conta (Ex: Corrente Itaú)")
            saldo = st.number_input("Saldo inicial (R$)", step=10.0)
            if st.form_submit_button("Cadastrar Conta"):
                if nome:
                    aid = str(uuid4())
                    novo = {"id": aid, "nome": nome, "saldo_inicial": float(saldo)}
                    inserted = insert_row("accounts", novo)
                    if inserted is not None:
                        st.session_state.accounts = pd.concat([st.session_state.accounts, pd.DataFrame([inserted])], ignore_index=True)
                        st.success(f"Conta '{nome}' cadastrada.")
                else:
                    st.error("Preencha o nome da conta.")

    st.markdown("---")
    st.write("### Contas cadastradas")
    if st.session_state.accounts.empty:
        st.info("Nenhuma conta cadastrada ainda.")
    else:
        st.dataframe(st.session_state.accounts)
        st.write("#### Editar / Excluir conta")
        sel = st.selectbox("Selecione conta", ["--"] + st.session_state.accounts["nome"].tolist())
        if sel and sel != "--":
            row = st.session_state.accounts[st.session_state.accounts["nome"] == sel].iloc[0]
            with st.form("edit_acc"):
                n_nome = st.text_input("Nome", value=row["nome"])
                n_saldo = st.number_input("Saldo inicial", value=float(row["saldo_inicial"]), step=10.0)
                if st.form_submit_button("Salvar alterações"):
                    updates = {"nome": n_nome, "saldo_inicial": float(n_saldo)}
                    res = update_row("accounts", row["id"], updates)
                    if res is not None:
                        st.session_state.accounts.loc[st.session_state.accounts["id"] == row["id"], ["nome","saldo_inicial"]] = [n_nome, float(n_saldo)]
                        st.success("Conta atualizada.")
            if st.button("Excluir conta"):
                linked = st.session_state.tx[st.session_state.tx["conta_id"] == row["id"]]
                if not linked.empty:
                    st.warning("Existem lançamentos vinculados a essa conta. Ao excluir, as referências serão removidas.")
                    if st.button("Confirmar exclusão desta conta"):
                        try:
                            supabase.table("transactions").update({"conta_id": None, "conta_nome": None}).eq("conta_id", row["id"]).execute()
                        except Exception as e:
                            st.error(f"Falha ao limpar referências da conta: {e}")
                        res = delete_row("accounts", row["id"])
                        if res is not None:
                            st.session_state.tx.loc[st.session_state.tx["conta_id"] == row["id"], ["conta_id","conta_nome"]] = [None, None]
                            st.session_state.accounts = st.session_state.accounts[st.session_state.accounts["id"] != row["id"]]
                            st.success("Conta excluída e referências limpas.")
                else:
                    res = delete_row("accounts", row["id"])
                    if res is not None:
                        st.session_state.accounts = st.session_state.accounts[st.session_state.accounts["id"] != row["id"]]
                        st.success("Conta excluída.")

# ============================================================
# 6 - GERENCIAR CATEGORIAS (CRUD + vinculo)
# ============================================================
elif menu == "Gerenciar Categorias":
    st.subheader("Gerenciar Categorias — CRUD e vinculação")

    with st.expander("Cadastrar nova categoria"):
        with st.form("form_cat"):
            nome = st.text_input("Nome da Categoria")
            tipo = st.selectbox("Tipo", ["Despesa", "Receita", "Ambas"]) 
            acc_names = ["-- Nenhuma --"] + st.session_state.accounts["nome"].tolist() if not st.session_state.accounts.empty else ["-- Nenhuma --"]
            card_names = ["-- Nenhum --"] + st.session_state.cards["nome"].tolist() if not st.session_state.cards.empty else ["-- Nenhum --"]
            def_acc = st.selectbox("Conta padrão (opcional)", acc_names)
            def_card = st.selectbox("Cartão padrão (opcional)", card_names)
            if st.form_submit_button("Cadastrar Categoria"):
                if nome:
                    cid = str(uuid4())
                    # traduzir seleção para id ou None
                    def_acc_id = None
                    def_card_id = None
                    if def_acc not in ["-- Nenhuma --"] and not st.session_state.accounts.empty:
                        def_acc_id = st.session_state.accounts[st.session_state.accounts["nome"] == def_acc]["id"].iloc[0]
                    if def_card not in ["-- Nenhum --"] and not st.session_state.cards.empty:
                        def_card_id = st.session_state.cards[st.session_state.cards["nome"] == def_card]["id"].iloc[0]

                    novo = {"id": cid, "nome": nome, "tipo": tipo}
                    if def_acc_id:
                        novo["default_conta_id"] = def_acc_id
                    if def_card_id:
                        novo["default_cartao_id"] = def_card_id

                    inserted = insert_row("categories", novo)
                    if inserted is not None:
                        st.session_state.cats = pd.concat([st.session_state.cats, pd.DataFrame([inserted])], ignore_index=True)
                        st.success("Categoria criada.")
                else:
                    st.error("Nome é obrigatório.")

    st.markdown("---")
    st.write("### Categorias cadastradas")
    if st.session_state.cats.empty:
        st.info("Nenhuma categoria cadastrada ainda.")
    else:
        cats_show = st.session_state.cats.copy()
        cats_show["default_conta_nome"] = cats_show["default_conta_id"].apply(lambda x: id_to_name(st.session_state.accounts, x))
        cats_show["default_cartao_nome"] = cats_show["default_cartao_id"].apply(lambda x: id_to_name(st.session_state.cards, x))
        st.dataframe(cats_show)

        st.write("#### Editar / Excluir categoria")
        sel = st.selectbox("Selecione categoria", ["--"] + st.session_state.cats["nome"].tolist())
        if sel and sel != "--":
            row = st.session_state.cats[st.session_state.cats["nome"] == sel].iloc[0]
            with st.form("edit_cat"):
                n_nome = st.text_input("Nome", value=row["nome"])
                n_tipo = st.selectbox("Tipo", ["Despesa","Receita","Ambas"], index=["Despesa","Receita","Ambas"].index(row["tipo"]) if row["tipo"] in ["Despesa","Receita","Ambas"] else 2)
                acc_names = ["-- Nenhuma --"] + st.session_state.accounts["nome"].tolist() if not st.session_state.accounts.empty else ["-- Nenhuma --"]
                card_names = ["-- Nenhum --"] + st.session_state.cards["nome"].tolist() if not st.session_state.cards.empty else ["-- Nenhum --"]
                cur_acc = id_to_name(st.session_state.accounts, row.get("default_conta_id")) or "-- Nenhuma --"
                cur_card = id_to_name(st.session_state.cards, row.get("default_cartao_id")) or "-- Nenhum --"
                n_def_acc = st.selectbox("Conta padrão", acc_names, index=acc_names.index(cur_acc) if cur_acc in acc_names else 0)
                n_def_card = st.selectbox("Cartão padrão", card_names, index=card_names.index(cur_card) if cur_card in card_names else 0)
                if st.form_submit_button("Salvar alterações"):
                    def_acc_id = None
                    def_card_id = None
                    if n_def_acc not in ["-- Nenhuma --"] and not st.session_state.accounts.empty:
                        def_acc_id = st.session_state.accounts[st.session_state.accounts["nome"] == n_def_acc]["id"].iloc[0]
                    if n_def_card not in ["-- Nenhum --"] and not st.session_state.cards.empty:
                        def_card_id = st.session_state.cards[st.session_state.cards["nome"] == n_def_card]["id"].iloc[0]

                    updates = {"nome": n_nome, "tipo": n_tipo}
                    if def_acc_id is not None:
                        updates["default_conta_id"] = def_acc_id
                    else:
                        updates["default_conta_id"] = None
                    if def_card_id is not None:
                        updates["default_cartao_id"] = def_card_id
                    else:
                        updates["default_cartao_id"] = None

                    res = update_row("categories", row["id"], updates)
                    if res is not None:
                        # atualizar localmente
                        st.session_state.cats.loc[st.session_state.cats["id"] == row["id"], ["nome","tipo","default_conta_id","default_cartao_id"]] = [n_nome, n_tipo, updates.get("default_conta_id"), updates.get("default_cartao_id")]
                        st.success("Categoria atualizada.")
            if st.button("Excluir categoria"):
                linked = st.session_state.tx[st.session_state.tx["categoria_id"] == row["id"]]
                if not linked.empty:
                    st.warning("Existem lançamentos vinculados a essa categoria. Ao excluir, as referências serão removidas.")
                    if st.button("Confirmar exclusão desta categoria"):
                        try:
                            supabase.table("transactions").update({"categoria_id": None, "categoria_nome": None}).eq("categoria_id", row["id"]).execute()
                        except Exception as e:
                            st.error(f"Falha ao limpar referências da categoria: {e}")
                        res = delete_row("categories", row["id"])
                        if res is not None:
                            st.session_state.tx.loc[st.session_state.tx["categoria_id"] == row["id"], ["categoria_id","categoria_nome"]] = [None, None]
                            st.session_state.cats = st.session_state.cats[st.session_state.cats["id"] != row["id"]]
                            st.success("Categoria excluída e referências limpas.")
                else:
                    res = delete_row("categories", row["id"])
                    if res is not None:
                        st.session_state.cats = st.session_state.cats[st.session_state.cats["id"] != row["id"]]
                        st.success("Categoria excluída.")

# footer
st.markdown("---")
st.write("Migrado para Supabase: substituí CSV por chamadas ao banco; mantive o fluxo original de UI e garanti que UUIDs vazios não são enviados (uso de NULL).")
