# --- Conteúdo do arquivo: api/database_manager.py ---



import sqlite3

import json

import os

from datetime import datetime

from config import DB_PATH



def setup_database():

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    cursor = conn.cursor()

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS conversations (

            user_id TEXT PRIMARY KEY,

            state TEXT,

            data TEXT,

            history TEXT

        )

    ''')

    

    cursor.execute('''

        CREATE TABLE IF NOT EXISTS outbound_queue (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id TEXT NOT NULL,

            message_text TEXT,

            media_data TEXT,

            file_name TEXT,

            created_at TEXT NOT NULL,

            attempts INTEGER DEFAULT 0

        )

    ''')

    

    conn.commit()

    conn.close()



def get_user_state_and_history(user_id):

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("SELECT state, data, history FROM conversations WHERE user_id = ?", (user_id,))

    result = cursor.fetchone()

    conn.close()

    if result:

        data_dict = json.loads(result['data'] or '{}')

        history_list = json.loads(result['history'] or '[]')

        return result['state'], data_dict, history_list

    return "INITIAL", {}, []



def set_user_state_and_history(user_id, state, data, history):

    if not isinstance(data, dict):

        data = {}



    # --- AJUSTE CRÍTICO APLICADO AQUI ---

    # Só adiciona o timestamp se a conversa estiver ATIVA.

    # Se o estado for 'INITIAL' ou 'HUMAN_ATTENDANCE', o campo de dados será salvo limpo.

    if state not in ["INITIAL", "HUMAN_ATTENDANCE"]:

        data['state_timestamp'] = datetime.now().isoformat()

    else:

        # Garante que, ao resetar, o timestamp antigo seja removido.

        data = {}



    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    cursor = conn.cursor()

    cursor.execute("INSERT OR REPLACE INTO conversations (user_id, state, data, history) VALUES (?, ?, ?, ?)",

                    (user_id, state, json.dumps(data), json.dumps(history)))

    conn.commit()

    conn.close()
