import streamlit as st
import sqlite3
import pandas as pd
import json
from streamlit_autorefresh import st_autorefresh # type: ignore

DB_PATH = r"C:\Users\Daniel\OneDrive\Documentos\Projetos\glassy-bot-cwai-termux\database\conversations.db"

# -------------------
# Funções de DB
# -------------------
def load_conversations():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, state, data FROM conversations")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_bot_paused():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_control (id INTEGER PRIMARY KEY, paused INTEGER)")
    cursor.execute("SELECT paused FROM bot_control WHERE id=1")
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO bot_control (id, paused) VALUES (1, 0)")
        conn.commit()
        conn.close()
        return False
    conn.close()
    return bool(row[0])

def set_bot_paused(value: bool):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE bot_control SET paused=? WHERE id=1", (1 if value else 0,))
    conn.commit()
    conn.close()

# -------------------
# Auto-refresh
# -------------------
st_autorefresh(interval=10 * 1000, key="datarefresh")

# -------------------
# Página
# -------------------
st.title("Glassy-Bot Monitoramento Local")
st.write("Monitor e controle das sessões e status do bot.")

# -------------------
# Botão global de pausar/reactivar
# -------------------
paused = get_bot_paused()
if paused:
    if st.button("Reativar Bot Global"):
        set_bot_paused(False)
        st.success("Bot global reativado")
else:
    if st.button("Pausar Bot Global"):
        set_bot_paused(True)
        st.warning("Bot global pausado")

st.markdown("---")

# -------------------
# Conversas
# -------------------
st.subheader("Conversas Ativas")
convs = load_conversations()

if not convs:
    st.info("Nenhuma conversa cadastrada.")
else:
    # Monta dataframe
    data = []
    for row in convs:
        user_id, state, data_json = row["user_id"], row["state"], row["data"]
        try:
            data_dict = json.loads(data_json) if data_json else {}
            timestamp = data_dict.get("state_timestamp", "")
            error = data_dict.get("error", "")
        except Exception:
            timestamp = ""
            error = ""
        data.append((user_id, state, timestamp, error))

    df = pd.DataFrame(data, columns=["User ID", "Estado", "Última Atualização", "Erro"])
    
    # Exibe a tabela completa
    st.dataframe(df, use_container_width=True)

    # -------------------
    # Selecionar conversa específica
    # -------------------
    st.markdown("---")
    st.subheader("Gerenciar Conversa Específica")
    selected_user = st.selectbox("Escolha uma conversa pelo User ID", df["User ID"].tolist())

    if selected_user:
        selected_row = df[df["User ID"] == selected_user].iloc[0]
        st.write(f"**Estado:** {selected_row['Estado']}")
        st.write(f"**Última Atualização:** {selected_row['Última Atualização']}")
        st.write(f"**Erro:** {selected_row['Erro']}")

        # Aqui você pode colocar botões específicos por conversa
        st.write("Controle do bot para esta conversa (não implementado no DB ainda)")
        st.button("Pausar Bot desta conversa")
        st.button("Reativar Bot desta conversa")
