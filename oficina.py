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
        status TEXT
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
            "INSERT INTO usuarios VALUES (%s, %s, %s)",
            ("admin", hash_admin, "admin")
        )
        cursor.execute(
            "INSERT INTO usuarios VALUES (%s, %s, %s)",
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

def salvar_item(item, armario, prateleira, status):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO ferramentas (item, armario, prateleira, status)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (item) DO UPDATE SET
        armario = EXCLUDED.armario,
        prateleira = EXCLUDED.prateleira,
        status = EXCLUDED.status
    """, (item, armario, prateleira, status))

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

# inter face
tab1, tab2, tab3 = st.tabs(['Localizador','Itens','Mapa'])

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
        if status == 'pegando':
            st.text(' Massa')
            st.text(f'A ferramenta {busca} está sendo usada')
        else:
            st.text(f'A ferramenta ({busca}) está no armário ({armario}) e na prateleira ({prateleira})')  

    caminho_mapa = os.path.join("images", "mapa_oficina.png")
    if os.path.exists(caminho_mapa):
        botaomapa = st.toggle('Mostrar mapa')
        if botaomapa:
            st.subheader("Mapa do Local")
            st.image(caminho_mapa)        
   
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
            status = st.selectbox('Voce esta pegando ou devolvendo',['devolvendo','pegando'])
            if status == 'devolvendo':
                st.divider()
            else:
                usuario = st.text_input('Nome de quem esta pegando a ferramenta')
            if st.form_submit_button("Salvar") and nome:
                salvar_item(nome, armario, prateleira,status)
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

    with tab3:        
        st.subheader("Atualizar Mapa")
        arquivo_mapa = st.file_uploader("Upload imagem (PNG/JPG)", type=['png', 'jpg', 'jpeg'])
        if arquivo_mapa and st.button("Salvar Mapa"):
            os.makedirs("images", exist_ok=True)
            with open(os.path.join("images", "mapa_oficina.png"), "wb") as f:
                f.write(arquivo_mapa.getbuffer())
            st.success("Mapa atualizado!")

    with tab2:
        if st.session_state.logado and st.session_state.role == "superadmin":
            st.divider()
            st.header('Painel de Controle')
            st.subheader('Cadastrar novo usuário')

            with st.form("novo_user"):
                n_usuario = st.text_input("Login")
                n_senha= st.text_input("Senha", type="password")
                n_nivel = st.selectbox("Nível", ["admin", "superadmin"])
                if st.form_submit_button("Criar") and n_usuario and n_senha:
                    if criar_usuario(n_usuario, n_senha, n_nivel):
                        st.success("Usuário criado!")
                        st.rerun()
                    else:
                        st.error("Usuário já existe.")
       
            st.divider()
       
            st.subheader('Gerenciamento de Usuários')

            conn = get_conn()
            usuarios_df = pd.read_sql("SELECT usuario, role FROM usuarios", conn)
            conn.close()

            st.dataframe(usuarios_df, use_container_width=True)
               
            target = st.selectbox("Usuário alvo", usuarios_df["usuario"])
            novasenha = st.text_input("Trocar senha (opcional)", type="password")
               
            att, exclui = st.columns(2)
            with att:
                if st.button("Atualizar Senha") and novasenha:
                    atualizar_senha(target, novasenha)
                    st.success("Senha alterada!")
            with exclui:
                if st.button("Excluir Conta", type="primary"):
                    excluir_usuario(target)
                    st.rerun()
else:
    with tab2:
        st.warning('Login nao efetuado')
    with tab3:
        st.warning('Login nao efetuado')
