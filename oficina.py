import streamlit as st
import pandas as pd
import psycopg2
import os
import base64
from werkzeug.security import generate_password_hash, check_password_hash
st.image('fundo.png')

st.set_page_config(
    page_title="Localizador de Ferramentas",
    layout="centered"
)
def fundo(imagem):
    with open(imagem, 'rb') as img:
        img_e = base64.b64encode(img.read()).decode()
    st.markdown("""
    <style>
    .stApp {{
        background-image: url('data:image/png;base64,{img_e}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: unset;
        }}

    /* Camada escura */
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.45);
        z-index: 0;
    }

    /* Conteúdo acima */
    .block-container {
        position: relative;
        z-index: 1;
    }

    /* Título */
    h1 {
        font-size: 42px !important;
        font-weight: 800;
        color: white;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.7);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111, #222);
    }

    </style>
    """, unsafe_allow_html=True)

    fundo("fundo.png")
# conexao df1
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
        prateleira TEXT
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

def salvar_item(item, armario, prateleira):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ferramentas (item, armario, prateleira)
    VALUES (%s, %s, %s)
    ON CONFLICT (item) DO UPDATE SET
        item = EXCLUDED.item,
        armario = EXCLUDED.armario,
        prateleira = EXCLUDED.prateleira
    """, (item, armario, prateleira))

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
        return True

    except Exception:
        return False

    finally:
        conn.close()

def excluir_usuario(usuario):
    if usuario != "superadmin":
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM usuarios WHERE usuario = %s", (usuario,))
        conn.commit()
        conn.close()

# sessão
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
tab1, tab2, tab3= st.tabs(['Localizador','Gerenciamento', 'Painel de Controle'])

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
        item = resultado['item'].values[0]
        armario = resultado['armario'].values[0]
        prateleira = resultado['prateleira'].values[0]
        st.markdown(f'Item: {item}')
        st.markdown(f'Armario: {armario}')
        st.markdown(f'Prateleira: {prateleira}')
    user_agent = st.context.headers.get("User-Agent", "")
    st.divider()

# area administração
if st.session_state.logado and st.session_state.role in ["admin", "superadmin"]:
    with tab2:
        st.header("Gerenciamento do Sistema")

        st.subheader("Cadastrar/Atualizar Item")
        with st.form("cadastro"):
            nome = st.text_input("Nome do Item").upper()
            armario = st.number_input("Armário", min_value = 0, step = 1)
            prateleira = st.number_input("Prateleira", min_value=0, step=1)
            submit = st.form_submit_button("Salvar")

            if submit and nome:
                salvar_item(nome, armario, prateleira)
                st.success("Item salvo!")
                st.rerun()

        st.divider()

        st.subheader("Excluir Item")
        if not df.empty:
            item_del = st.selectbox("Selecionar para excluir", df["item"], key="excluir_box")

            if st.button("Confirmar Exclusão", type="primary"):
                excluir_item(item_del)
                st.success("Item excluído com sucesso!")
                st.rerun()
        else:
            st.info("Nenhuma ferramenta cadastrada no momento.")
if st.session_state.logado and st.session_state.role in ["admin", "superadmin"]:
    with tab3:
        if st.session_state.role == "superadmin":
            st.header('Painel de Controle')

            st.subheader('Cadastrar novo usuário')
            with st.form("novo_user"):
                n_usuario = st.text_input("Login")
                n_senha= st.text_input("Senha", type="password")
                n_nivel = st.selectbox("Nível", ["admin", "superadmin"])

                if st.form_submit_button("Criar"):
                    if n_usuario and n_senha:
                        if criar_usuario(n_usuario, n_senha, n_nivel):
                            st.success("Usuário criado!")
                            st.rerun()
                        else:
                            st.error("Usuário já existe.")
            st.subheader('Gerenciamento de Usuários')

            conn = get_conn()
            usuarios_df = pd.read_sql("SELECT usuario, role FROM usuarios", conn)
            conn.close()

            st.dataframe(usuarios_df, use_container_width=True)

            target = st.selectbox("Usuário alvo", usuarios_df["usuario"])
            novasenha = st.text_input("Trocar senha (opcional)", type="password")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Atualizar Senha") and novasenha:
                    atualizar_senha(target, novasenha)
                    st.success("Senha alterada!")

                with col2:
                    if st.button("Excluir Conta", type="primary"):
                        excluir_usuario(target)
                        st.rerun()
                
            st.divider()

        

else:
    with tab2:
        st.warning('Login nao efetuado')
    with tab3:
        st.warning('Login nao efetuado')
