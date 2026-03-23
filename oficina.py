import streamlit as st
import pandas as pd
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash


st.set_page_config(
    page_title="Localizador de Ferramentas",
    layout="centered"
)

# conexao df
def get_conn():
    return psycopg2.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        database=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        sslmode="require"
    )

def criar_tabelas():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ferramentas (
        item TEXT PRIMARY KEY,
        armario TEXT,
        prateleira TEXT,
        status TEXT,
        responsavel TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        usuario TEXT PRIMARY KEY,
        senha TEXT,
        role TEXT
    )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

def criar_admin_padrao():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        hash_admin = generate_password_hash('1234')
        hash_super = generate_password_hash('admin')

        cursor.execute(
            "INSERT INTO usuarios (usuario, senha, role) VALUES (%s, %s, %s)",
            ("admin", hash_admin, "admin")
        )
        cursor.execute(
            "INSERT INTO usuarios (usuario, senha, role) VALUES (%s, %s, %s)",
            ("superadmin", hash_super, "superadmin")
        )
        conn.commit()
        conn.close()

criar_admin_padrao()

def carregar_ferramentas():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM ferramentas", conn)
    conn.close()
    return df

# ✅ SEM IMAGEM
def salvar_item(item, armario, prateleira, status, responsavel):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ferramentas (item, armario, prateleira, status, responsavel)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (item) DO UPDATE SET
        armario = EXCLUDED.armario,
        prateleira = EXCLUDED.prateleira,
        status = EXCLUDED.status,
        responsavel = EXCLUDED.responsavel
    """, (item, armario, prateleira, status, responsavel))

    conn.commit()
    conn.close()

def excluir_item(item):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ferramentas WHERE item = %s", (item,))

    conn.commit()
    conn.close()

def autenticar(usuario, senha):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT senha, role FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        senha_banco, role = resultado
        if check_password_hash(senha_banco, senha):
            return role
    return None

def atualizar_senha(usuario, nova_senha):
    conn = get_conn()
    cursor = conn.cursor()

    hash_nova_senha = generate_password_hash(nova_senha)

    cursor.execute(
        "UPDATE usuarios SET senha = %s WHERE usuario = %s",
        (hash_nova_senha, usuario)
    )

    conn.commit()
    conn.close()

def criar_usuario(usuario, senha, role):
    conn = get_conn()
    cursor = conn.cursor()

    try:
        hash_senha = generate_password_hash(senha)

        cursor.execute(
            "INSERT INTO usuarios VALUES (%s, %s, %s)",
            (usuario, hash_senha, role)
        )

        conn.commit()
        conn.close()
        return True

    except Exception:
        conn.close()
        return False

def excluir_usuario(usuario):
    if usuario != "superadmin":
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE usuario = %s", (usuario,))
        conn.commit()
        conn.close()

if "logado" not in st.session_state:
    st.session_state.logado = False
if "role" not in st.session_state:
    st.session_state.role = None

# login
st.sidebar.header("Acesso Administrativo")

if not st.session_state.logado:
    usuario = st.sidebar.text_input("Usuário")
    senha = st.sidebar.text_input("Senha", type="password")
    if st.sidebar.button("Entrar"):
        role = autenticar(usuario, senha)
        if role:
            st.session_state.logado = True
            st.session_state.role = role
            st.rerun()
        else:
            st.sidebar.error("Acesso negado")
else:
    st.sidebar.success(f"Logado como: {st.session_state.role}")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.session_state.role = None
        st.rerun()

# interface
tab1, tab2 = st.tabs(['Localizador','Ferramentas'])

df = carregar_ferramentas()

# Area geral
with tab1:
    st.title("Localizador de Ferramentas da Oficina")
    st.header("Buscar Ferramenta 🔎")

    listaferramentas = df["item"].tolist() if not df.empty else ["Nenhuma ferramenta cadastrada"]
    busca = st.selectbox("Selecione a ferramenta que você deseja", listaferramentas)

    if busca and not df.empty and busca != "Nenhuma ferramenta cadastrada":
        filtro = df['item'] == busca
        resultado = df[filtro]

        armario = resultado['armario'].values[0]
        prateleira = resultado['prateleira'].values[0]
        status = resultado['status'].values[0]

        # ✅ IMAGEM AUTOMÁTICA PELO ARMÁRIO
        caminho_img = os.path.join("images", f"{armario}.png")
        if os.path.exists(caminho_img):
            st.image(caminho_img, caption=f"Local aproximado: {armario}")

        if status == 'pegando':
            responsavel = resultado['responsavel'].values[0]

            if responsavel and str(responsavel).strip() != "":
                st.warning(f"A ferramenta ({busca}) está em uso por: {responsavel}")
            else:
                st.warning(f"A ferramenta ({busca}) está em uso")
        else:
            st.success(f"A ferramenta ({busca}) está no armário ({armario}) e na prateleira ({prateleira})")

    st.divider()

# area administração
if st.session_state.logado and st.session_state.role in ["admin", "superadmin"]:
    with tab2:
        st.header("Gerenciamento do Sistema")      
        st.subheader("Cadastrar/Atualizar Item")

        with st.form("cadastro"):
            nome = st.text_input("Nome do Item")
            armario = st.text_input("Armário")
            prateleira = st.text_input("Prateleira")
            status = st.radio("Status da ferramenta", ["devolvendo", "pegando"])

            responsavel = ""
            if status == "pegando":
                responsavel = st.text_input('Nome de quem está pegando a ferramenta')

            submit = st.form_submit_button("Salvar")

            if submit and nome:
                salvar_item(nome, armario, prateleira, status, responsavel)
                st.success("Item salvo!")
                st.rerun()

else:
    with tab2:
        st.warning('Login nao efetuado')
