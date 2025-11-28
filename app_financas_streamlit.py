# app_financas_streamlit.py
"""
Controle Financeiro com Streamlit + SQLite
- Autenticação opcional via streamlit-authenticator
- Tabelas: tipos, cartoes, contas, registros
- Migração automática simples de CSVs antigos (se existirem)
- Dashboard: agregações mensais, anuais e por categoria
- Uso: streamlit run app_financas_streamlit.py
"""

import os
import re
import copy
import sqlite3
import datetime
from typing import Optional
import pandas as pd
import streamlit as st

# --- Tentativa de importar streamlit-authenticator (opcional) ---
try:
    import streamlit_authenticator as stauth
    STAUTH_AVAILABLE = True
except Exception:
    STAUTH_AVAILABLE = False

# ---------------------------
# Page config (pode ficar antes do login)
# ---------------------------
st.set_page_config(layout="wide", page_title="Controle Financeiro")

# ---------------------------
# Carrega st.secrets de forma segura (somente leitura)
# ---------------------------
try:
    _SECRETS = dict(st.secrets)
except Exception:
    _SECRETS = {}

# ---------------------------
# Helpers: parser numérico e formatação BR
# ---------------------------
def _parse_num_str(s):
    if pd.isna(s):
        return 0.0
    s = str(s).strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    s = s.replace(" ", "")
    s = re.sub(r'[^0-9\.,\-]', '', s)
    if '.' in s and ',' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        if s.count(',') > 1:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif '.' in s and ',' not in s:
        if s.count('.') > 1:
            parts = s.split('.')
            s = ''.join(parts[:-1]) + '.' + parts[-1]
    if s.count('-') > 1:
        s = s.replace('-', '')
    if s in ['', '.', '-']:
        return 0.0
    try:
        return float(s)
    except:
        digits = re.sub(r'[^0-9\-]', '', s)
        if digits in ['', '-', None]:
            return 0.0
        try:
            return float(digits)
        except:
            return 0.0

def format_brl(valor):
    try:
        s = f"{float(valor):,.2f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

# ---------------------------
# Prepara credentials e auth settings (sem imprimir nada)
# ---------------------------
def prepare_credentials_and_authsettings():
    """
    Retorna (credentials_copy, auth_settings).
    - credentials_copy: dict no formato exigido por streamlit-authenticator (cópia)
    - auth_settings: dict com cookie_name, cookie_key, cookie_expiry_days
    Observação: não imprime nada — qualquer mensagem ao usuário deve ser exibida
    somente após a autenticação (para evitar render antes do login).
    """
    default_auth = {
        "cookie_name": "finapp_cookie",
        "cookie_key": "change_this_cookie_key",
        "cookie_expiry_days": 1
    }

    # auth settings
    raw_auth = _SECRETS.get("auth", {}) if isinstance(_SECRETS, dict) else {}
    auth_settings = {
        "cookie_name": raw_auth.get("cookie_name") or raw_auth.get("cookie") or default_auth["cookie_name"],
        "cookie_key": raw_auth.get("cookie_key") or raw_auth.get("cookie_secret") or default_auth["cookie_key"],
        "cookie_expiry_days": int(raw_auth.get("cookie_expiry_days") or raw_auth.get("cookie_expiry") or default_auth["cookie_expiry_days"])
    }

    # credentials (deep copy to avoid mutating st.secrets)
    creds_raw = _SECRETS.get("credentials") if isinstance(_SECRETS, dict) else None
    credentials = copy.deepcopy(creds_raw) if creds_raw else None

    # If no credentials in secrets, prepare None — caller will decide fallback mode
    return credentials, auth_settings

# ---------------------------
# Função de autenticação (renderiza o widget de login no 'main' sem nada antes)
# ---------------------------
def do_auth():
    """
    Retorna (auth_ok: bool, name, username, info_message (str or None))
    - auth_ok True => login ok (ou stauth ausente e modo dev)
    - info_message pode conter aviso sobre fallback (ex.: credenciais padrão)
    """
    credentials, auth_settings = prepare_credentials_and_authsettings()
    info_message = None

    if not STAUTH_AVAILABLE:
        # Modo dev: streamlit-authenticator não está instalado -> não há tela de login do pacote.
        # Decidimos: modo aberto (autenticado automaticamente) — isso evita render extra antes.
        return True, None, None, "streamlit-authenticator não instalado. App em modo aberto (dev)."

    # Se existe credentials vindo do secrets, use (mas faça uma cópia defensiva)
    creds_use = None
    if credentials:
        creds_use = copy.deepcopy(credentials)
    else:
        # fallback: nenhuma credencial definida nas secrets - cria credencial 'admin' com senha 'admin'
        # Para segurança: esse fallback é apenas para desenvolvimento local, e será comunicado.
        # Geramos hash em memória para a senha 'admin' se possible.
        try:
            hashed = stauth.Hasher(["admin"]).generate()[0]
            creds_use = {
                "usernames": {
                    "admin": {
                        "name": "Administrador",
                        "email": "admin@example.com",
                        "password": hashed
                    }
                }
            }
            info_message = "Usando credencial fallback 'admin' (senha 'admin') — apenas para desenvolvimento. Configure secrets para produção."
        except Exception:
            # se Hasher falhar, usamos senha em texto (inseguro) — ainda assim só para dev
            creds_use = {
                "usernames": {
                    "admin": {
                        "name": "Administrador",
                        "email": "admin@example.com",
                        "password": "admin"
                    }
                }
            }
            info_message = "Usando credencial fallback (senha em texto) — apenas para desenvolvimento."

    # Se as senhas vieram em texto no secrets, precisamos hashear NA CÓPIA antes de passar ao stauth
    # (não tocamos st.secrets)
    try:
        # procura senhas não-hash (heurística simples)
        usernames = creds_use.get("usernames", {})
        plaintext_list = []
        keys = []
        for uname, data in usernames.items():
            pw = data.get("password", "")
            if isinstance(pw, str) and not (pw.startswith("$2b$") or pw.startswith("$2a$") or pw.startswith("$argon2")):
                plaintext_list.append(str(pw))
                keys.append(uname)
        if plaintext_list and STAUTH_AVAILABLE:
            hashed_list = stauth.Hasher(plaintext_list).generate()
            for i, uname in enumerate(keys):
                creds_use["usernames"][uname]["password"] = hashed_list[i]
    except Exception:
        # se algo falhar no hashing, ignore — stauth pode aceitar texto dependendo da versão
        pass

    # agora inicializa o authenticator e renderiza o login no local 'main'
    try:
        authenticator = stauth.Authenticate(creds_use, auth_settings["cookie_name"], auth_settings["cookie_key"], auth_settings["cookie_expiry_days"])
    except Exception as e:
        # devolve erro (mostra mensagem após)
        return False, None, None, f"Erro inicializando autenticação: {e}"

    # render login (sempre em 'main')
    try:
        # preferimos named arg 'location' — mas aceitamos fallback por compatibilidade
        try:
            name, auth_status, username = authenticator.login("Acesso — Controle Financeiro", location="main")
        except TypeError:
            name, auth_status, username = authenticator.login("Acesso — Controle Financeiro", "main")
    except Exception as e:
        return False, None, None, f"Erro exibindo login: {e}"

    # tratamento do status
    if auth_status is True:
        # coloca logout no sidebar (usamos named arg)
        try:
            try:
                authenticator.logout("Sair", location="sidebar")
            except TypeError:
                authenticator.logout("Sair", "sidebar")
        except Exception:
            pass
        return True, name, username, info_message
    elif auth_status is False:
        return False, None, None, "Usuário/senha incorretos."
    else:
        # None -> ainda não logou: mostra alerta simples (retornamos falso para parar app)
        return False, None, None, "Por favor faça login."

# ===========================
# EXECUTA AUTENTICAÇÃO (logo no começo)
# ===========================
auth_ok, auth_name, auth_user, auth_info = do_auth()

# Se auth não ok ou ainda não logado, mostramos a mensagem (retornada) e interrompemos para evitar render prévio.
if not auth_ok:
    # Mostra mensagem de contexto para o usuário (permitimos texto simples aqui)
    if auth_info:
        st.error(auth_info)
    st.stop()

# Se chegou até aqui, login foi bem sucedido (ou estamos em modo dev). A partir deste ponto podemos renderizar o app.
# (agora sim usamos títulos, sidebar e tudo)
if auth_info:
    st.info(auth_info)

st.title("Controle Financeiro — App")
st.caption("Registro de receitas/despesas, contas, cartões e dashboard. Guarde isto como um diário organizado.")

# ---------------------------
# DB (SQLite) helpers — DB_PATH lido de _SECRETS com fallback
# ---------------------------
DB_PATH = (_SECRETS.get("database") or {}).get("sqlite_path", "financas.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        observacao TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cartoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        bandeira TEXT,
        limite REAL DEFAULT 0,
        fechamento INTEGER,
        vencimento INTEGER,
        saldo_utilizado REAL DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        banco TEXT NOT NULL,
        tipo TEXT,
        saldo REAL DEFAULT 0,
        limite REAL DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo_de_entrada TEXT NOT NULL,
        tipo_id INTEGER,
        observacao TEXT,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        metodo TEXT,
        metodo_id INTEGER,
        nota TEXT,
        criado_em TEXT DEFAULT (date('now'))
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------------------------
# Migração CSV -> SQLite (opcional)
# ---------------------------
def try_migrate_csvs():
    conn = get_conn()
    cur = conn.cursor()
    def table_empty(name):
        cur.execute(f"SELECT COUNT(1) c FROM {name}")
        row = cur.fetchone()
        return row[0] == 0

    # tipos.csv
    if os.path.exists("tipos.csv") and table_empty("tipos"):
        try:
            df = pd.read_csv("tipos.csv", sep=";", dtype=str).fillna("")
            for _, r in df.iterrows():
                cur.execute("INSERT INTO tipos (tipo, observacao) VALUES (?,?)", (r.get("tipo"), r.get("observacao")))
            conn.commit()
        except Exception:
            pass

    # cartoes.csv
    if os.path.exists("cartoes.csv") and table_empty("cartoes"):
        try:
            df = pd.read_csv("cartoes.csv", sep=";", dtype=str).fillna("")
            for _, r in df.iterrows():
                limite = _parse_num_str(r.get("limite", 0))
                fechamento = int(r.get("fechamento")) if r.get("fechamento") else None
                vencimento = int(r.get("vencimento")) if r.get("vencimento") else None
                cur.execute("INSERT INTO cartoes (nome,bandeira,limite,fechamento,vencimento,saldo_utilizado) VALUES (?,?,?,?,?,?)",
                            (r.get("nome"), r.get("bandeira"), limite, fechamento, vencimento, 0))
            conn.commit()
        except Exception:
            pass

    # contas.csv
    if os.path.exists("contas.csv") and table_empty("contas"):
        try:
            df = pd.read_csv("contas.csv", sep=";", dtype=str).fillna("")
            for _, r in df.iterrows():
                saldo = _parse_num_str(r.get("saldo", 0))
                limite = _parse_num_str(r.get("limite", 0))
                cur.execute("INSERT INTO contas (banco,tipo,saldo,limite) VALUES (?,?,?,?)", (r.get("banco"), r.get("tipo"), saldo, limite))
            conn.commit()
        except Exception:
            pass

    # registros.csv
    if os.path.exists("registros.csv") and table_empty("registros"):
        try:
            df = pd.read_csv("registros.csv", sep=";", dtype=str).fillna("")
            for _, r in df.iterrows():
                tipo_de_entrada = r.get("tipo_de_entrada") or "Despesa"
                observ = r.get("observacao_escolhida") or r.get("observacao") or None
                valor = _parse_num_str(r.get("valor", 0))
                data = r.get("data") or datetime.date.today().isoformat()
                cur.execute("INSERT INTO registros (tipo_de_entrada, tipo_id, observacao, valor, data, metodo, metodo_id, nota) VALUES (?,?,?,?,?,?,?,?)",
                            (tipo_de_entrada, None, observ, valor, data, None, None, "MigradoCSV"))
            conn.commit()
        except Exception:
            pass

    conn.close()

try_migrate_csvs()

# ---------------------------
# CRUD helpers
# ---------------------------
def fetch_df(query, params=()):
    conn = get_conn()
    try:
        df = pd.read_sql_query(query, conn, params=params, parse_dates=["data", "criado_em"])
        return df
    finally:
        conn.close()

def insert_tipo(tipo, observacao):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO tipos (tipo, observacao) VALUES (?,?)", (tipo, observacao))
    conn.commit(); conn.close()

def insert_cartao(nome, bandeira, limite, fechamento, vencimento):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO cartoes (nome,bandeira,limite,fechamento,vencimento) VALUES (?,?,?,?,?)",
                (nome, bandeira, float(limite), int(fechamento) if fechamento else None, int(vencimento) if vencimento else None))
    conn.commit(); conn.close()

def insert_conta(banco, tipo_conta, saldo, limite):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO contas (banco,tipo,saldo,limite) VALUES (?,?,?,?)", (banco, tipo_conta, float(saldo), float(limite)))
    conn.commit(); conn.close()

def insert_registro(tipo_de_entrada, tipo_id, observacao, valor, data_str, metodo, metodo_id, nota):
    conn = get_conn(); cur = conn.cursor()
    valor_f = float(valor)
    if metodo == "conta" and metodo_id:
        cur.execute("SELECT saldo, limite FROM contas WHERE id = ?", (metodo_id,))
        row = cur.fetchone()
        if row:
            saldo = row["saldo"] or 0.0; limite = row["limite"] or 0.0
            new_saldo = saldo - valor_f if tipo_de_entrada == "Despesa" else saldo + valor_f
            if tipo_de_entrada == "Despesa" and new_saldo < -abs(limite):
                conn.close(); raise ValueError("Saldo insuficiente na conta (considerando limite).")
            cur.execute("UPDATE contas SET saldo = ? WHERE id = ?", (new_saldo, metodo_id))
    if metodo == "cartao" and metodo_id:
        cur.execute("SELECT limite, saldo_utilizado FROM cartoes WHERE id = ?", (metodo_id,))
        row = cur.fetchone()
        if row:
            limite = row["limite"] or 0.0; usado = row["saldo_utilizado"] or 0.0
            new_usado = usado + valor_f if tipo_de_entrada == "Despesa" else used - valor_f if False else usado - valor_f
            if tipo_de_entrada == "Despesa" and new_usado > limite:
                conn.close(); raise ValueError("Limite do cartão excedido.")
            cur.execute("UPDATE cartoes SET saldo_utilizado = ? WHERE id = ?", (new_usado, metodo_id))
    cur.execute("INSERT INTO registros (tipo_de_entrada, tipo_id, observacao, valor, data, metodo, metodo_id, nota) VALUES (?,?,?,?,?,?,?,?)",
                (tipo_de_entrada, tipo_id if tipo_id else None, observacao, valor_f, data_str, metodo, metodo_id if metodo_id else None, nota))
    conn.commit(); conn.close()

# ---------------------------
# UI: sidebar (menu) e páginas
# ---------------------------
with st.sidebar:
    st.header("Navegação")
    menu = st.radio("Ir para:", ["Dashboard", "Novo Registro", "Tipos", "Cartões", "Contas", "Backup/Export"])

def page_tipos():
    st.header("Tipos (Categorias)")
    df = fetch_df("SELECT * FROM tipos ORDER BY tipo, observacao")
    if df.empty:
        st.info("Nenhum tipo cadastrado.")
    else:
        st.dataframe(df)
    with st.form("form_tipo", clear_on_submit=True):
        novo = st.text_input("Nome do tipo (ex: Aluguel, Salário)")
        obs = st.text_input("Observação (opcional)")
        if st.form_submit_button("Salvar tipo"):
            if not novo.strip():
                st.warning("Nome do tipo é obrigatório.")
            else:
                insert_tipo(novo.strip(), obs.strip() or None)
                st.success("Tipo salvo.")
                st.experimental_rerun()

def page_cartoes():
    st.header("Cartões")
    df = fetch_df("SELECT * FROM cartoes ORDER BY nome")
    if df.empty:
        st.info("Nenhum cartão cadastrado.")
    else:
        d = df.copy()
        d["limite"] = d["limite"].map(format_brl)
        d["saldo_utilizado"] = d["saldo_utilizado"].map(format_brl)
        st.dataframe(d)
    with st.form("form_cartao", clear_on_submit=True):
        nome = st.text_input("Nome do cartão")
        bandeira = st.text_input("Bandeira (opcional)")
        limite = st.number_input("Limite", value=0.0, step=50.0)
        fechamento = st.number_input("Dia de fechamento (1-31)", min_value=1, max_value=31, value=1)
        vencimento = st.number_input("Dia de vencimento (1-31)", min_value=1, max_value=31, value=10)
        if st.form_submit_button("Salvar cartão"):
            if not nome.strip():
                st.warning("Nome do cartão é obrigatório.")
            else:
                insert_cartao(nome.strip(), bandeira.strip() or None, limite, fechamento, vencimento)
                st.success("Cartão salvo.")
                st.experimental_rerun()

def page_contas():
    st.header("Contas Bancárias")
    df = fetch_df("SELECT * FROM contas ORDER BY banco")
    if df.empty:
        st.info("Nenhuma conta cadastrada.")
    else:
        d = df.copy()
        d["saldo"] = d["saldo"].map(format_brl)
        d["limite"] = d["limite"].map(format_brl)
        st.dataframe(d)
    with st.form("form_conta", clear_on_submit=True):
        banco = st.text_input("Banco / descrição")
        tipo = st.selectbox("Tipo de conta", ["Corrente", "Poupança", "Pagamento"])
        saldo = st.number_input("Saldo inicial", value=0.0, step=10.0)
        limite = st.number_input("Limite (cheque especial)", value=0.0, step=10.0)
        if st.form_submit_button("Salvar conta"):
            if not banco.strip():
                st.warning("Informe o banco.")
            else:
                insert_conta(banco.strip(), tipo, saldo, limite)
                st.success("Conta salva.")
                st.experimental_rerun()

def page_novo_registro():
    st.header("Novo Lançamento")
    tipos = fetch_df("SELECT * FROM tipos ORDER BY tipo, observacao")
    cartoes = fetch_df("SELECT * FROM cartoes ORDER BY nome")
    contas = fetch_df("SELECT * FROM contas ORDER BY banco")

    tipos_opts = ["(Sem categoria)"] + [f"{r['id']} — {r['tipo']}" + (f" ({r['observacao']})" if r['observacao'] else "") for _, r in tipos.iterrows()] if not tipos.empty else ["(Sem categoria)"]

    col1, col2 = st.columns([2,1])
    with col1:
        tipo_de_entrada = st.selectbox("Tipo de entrada", ["Despesa", "Receita"])
        tipo_sel = st.selectbox("Categoria", tipos_opts)
        tipo_id = None
        if tipo_sel != "(Sem categoria)":
            tipo_id = int(tipo_sel.split(" — ")[0])
        observ = st.text_input("Observação livre")
        valor_raw = st.text_input("Valor (use vírgula ou ponto)", value="0,00")
        valor = _parse_num_str(valor_raw)
        data = st.date_input("Data", value=datetime.date.today())
    with col2:
        st.markdown("**Método / Origem**")
        metodo = st.selectbox("Método", ["Nenhum", "Conta Bancária", "Cartão de Crédito"])
        metodo_key = None; metodo_id = None
        if metodo == "Conta Bancária":
            if contas.empty:
                st.info("Nenhuma conta cadastrada.")
            else:
                opt = {f'{r["id"]} — {r["banco"]}': int(r["id"]) for _, r in contas.iterrows()}
                sel = st.selectbox("Selecione conta", list(opt.keys()))
                metodo_key = "conta"; metodo_id = opt[sel]
                row = contas[contas["id"]==metodo_id].iloc[0]
                st.write("Saldo:", format_brl(row["saldo"]), " — Limite:", format_brl(row["limite"]))
        elif metodo == "Cartão de Crédito":
            if cartoes.empty:
                st.info("Nenhum cartão cadastrado.")
            else:
                opt = {f'{r["id"]} — {r["nome"]}': int(r["id"]) for _, r in cartoes.iterrows()}
                sel = st.selectbox("Selecione cartão", list(opt.keys()))
                metodo_key = "cartao"; metodo_id = opt[sel]
                row = cartoes[cartoes["id"]==metodo_id].iloc[0]
                st.write("Limite:", format_brl(row["limite"]), " — Utilizado:", format_brl(row["saldo_utilizado"]))
        nota = st.text_area("Nota / observação adicional")

    if st.button("Salvar lançamento"):
        try:
            insert_registro(tipo_de_entrada=tipo_de_entrada, tipo_id=tipo_id, observacao=observ or None,
                            valor=valor, data_str=pd.to_datetime(data).strftime("%Y-%m-%d"),
                            metodo=metodo_key, metodo_id=metodo_id, nota=nota or None)
            st.success("Lançamento salvo.")
            st.experimental_rerun()
        except Exception as e:
            st.error("Erro ao salvar: " + str(e))

def page_backup_export():
    st.header("Backup / Export")
    if st.button("Exportar registros"):
        df = fetch_df("SELECT * FROM registros ORDER BY data DESC")
        df.to_csv("registros_export.csv", index=False, sep=";")
        st.success("registros_export.csv gerado.")
    if st.button("Exportar contas"):
        df = fetch_df("SELECT * FROM contas")
        df.to_csv("contas_export.csv", index=False, sep=";")
        st.success("contas_export.csv gerado.")
    if st.button("Exportar cartoes"):
        df = fetch_df("SELECT * FROM cartoes")
        df.to_csv("cartoes_export.csv", index=False, sep=";")
        st.success("cartoes_export.csv gerado.")
    if st.button("Exportar tipos"):
        df = fetch_df("SELECT * FROM tipos")
        df.to_csv("tipos_export.csv", index=False, sep=";")
        st.success("tipos_export.csv gerado.")

def page_dashboard():
    st.header("Dashboard")
    df = fetch_df("""
        SELECT r.*, t.tipo as categoria_tipo, t.observacao as categoria_obs, c.nome as cartao_nome, acc.banco as conta_banco
        FROM registros r
        LEFT JOIN tipos t ON r.tipo_id = t.id
        LEFT JOIN cartoes c ON r.metodo = 'cartao' AND r.metodo_id = c.id
        LEFT JOIN contas acc ON r.metodo = 'conta' AND r.metodo_id = acc.id
        ORDER BY data DESC
    """)
    if df.empty:
        st.info("Nenhum registro encontrado.")
        return

    df["valor"] = df["valor"].astype(float)
    df["data"] = pd.to_datetime(df["data"])
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.to_period("M").dt.to_timestamp()
    df["valor_ajustado"] = df.apply(lambda r: -abs(r["valor"]) if r["tipo_de_entrada"]=='Despesa' else abs(r["valor"]), axis=1)
    total_receitas = df[df["valor_ajustado"]>0]["valor_ajustado"].sum()
    total_despesas = df[df["valor_ajustado"]<0]["valor_ajustado"].sum()
    saldo = total_receitas + total_despesas

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Receitas", format_brl(total_receitas))
    c2.metric("Despesas", format_brl(total_despesas))
    c3.metric("Saldo", format_brl(saldo))
    perc = (100*(saldo/total_receitas)) if total_receitas!=0 else 0
    c4.metric("Saldo/Receita (%)", f"{perc:.2f}%")

    st.subheader("Séries Mensais")
    series = df.groupby(["mes", "tipo_de_entrada"])["valor"].sum().unstack(fill_value=0)
    series.index = pd.to_datetime(series.index)
    st.line_chart(series)

    st.subheader("Saldo Mensal")
    mensal = df.groupby("mes")["valor_ajustado"].sum().sort_index()
    mensal.index = pd.to_datetime(mensal.index)
    st.bar_chart(mensal)

    st.subheader("Agregação Anual")
    anual = df.groupby("ano")["valor_ajustado"].sum().reset_index().sort_values("ano", ascending=False)
    anual["valor_fmt"] = anual["valor_ajustado"].map(format_brl)
    st.dataframe(anual)

    st.subheader("Por Categoria")
    df["categoria"] = df.apply(lambda r: r["categoria_tipo"] if pd.notna(r["categoria_tipo"]) else (r["observacao"] or "Sem categoria"), axis=1)
    por_tipo = df.groupby("categoria")["valor_ajustado"].sum().reset_index().sort_values("valor_ajustado")
    por_tipo["valor_fmt"] = por_tipo["valor_ajustado"].map(format_brl)
    st.dataframe(por_tipo[["categoria","valor_fmt"]].rename(columns={"valor_fmt":"Valor"}), use_container_width=True)

    st.subheader("Tabela de Registros (filtro)")
    ano_opts = sorted(df["ano"].unique(), reverse=True)
    ano_sel = st.selectbox("Ano", ano_opts)
    cat_opts = ["(Todos)"] + sorted(df["categoria"].unique())
    cat_sel = st.selectbox("Categoria", cat_opts)
    tipo_sel = st.selectbox("Tipo Entrada", ["(Todos)", "Receita","Despesa"])
    filt = df[df["ano"]==int(ano_sel)]
    if cat_sel != "(Todos)":
        filt = filt[filt["categoria"]==cat_sel]
    if tipo_sel != "(Todos)":
        filt = filt[filt["tipo_de_entrada"]==tipo_sel]
    disp = filt.copy()
    disp["valor"] = disp["valor"].map(format_brl)
    disp["data"] = disp["data"].dt.strftime("%d/%m/%Y")
    st.dataframe(disp[["data","tipo_de_entrada","categoria","observacao","valor","metodo","nota"]].rename(
        columns={"data":"Data","tipo_de_entrada":"Tipo","categoria":"Categoria","observacao":"Observação","valor":"Valor","metodo":"Método","nota":"Nota"}
    ), use_container_width=True)

# rota
if menu == "Tipos":
    page_tipos()
elif menu == "Cartões":
    page_cartoes()
elif menu == "Contas":
    page_contas()
elif menu == "Novo Registro":
    page_novo_registro()
elif menu == "Backup/Export":
    page_backup_export()
else:
    page_dashboard()

# Rodapé
st.markdown("---")
st.markdown(
    """
    **Notas rápidas**
    - Ao lançar despesas por conta, o saldo da conta é atualizado.
    - Ao lançar despesas por cartão, o `saldo_utilizado` do cartão é atualizado.
    - Ambiente do Streamlit Cloud pode perder arquivos locais em reinícios; recomendo banco externo (Supabase/Postgres) para dados persistentes.
    - Para produção: usar autenticação (recomendo OIDC) e banco gerenciado.
    """
)
