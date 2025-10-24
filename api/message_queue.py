# --- Conteúdo do arquivo: api/message_queue.py ---
import sqlite3
import json
import time
import threading
import requests
from datetime import datetime
from config import GATEWAY_URL, DB_PATH

def queue_message(user_id, text, media_data=None, file_name=None):
    """Adiciona uma mensagem à fila de envio no banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO outbound_queue (user_id, message_text, media_data, file_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, media_data, file_name, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        print(f"Mensagem para {user_id} enfileirada.")
    except Exception as e:
        print(f"!!! ERRO AO ENFILEIRAR MENSAGEM: {e}")

def _process_outbound_queue():
    """Worker que processa a fila de mensagens e as envia para o Gateway."""
    while True:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        job = None
        try:
            cursor.execute("SELECT * FROM outbound_queue WHERE attempts < 5 ORDER BY created_at ASC LIMIT 1")
            job = cursor.fetchone()
            
            if job:
                print(f"Processando job {job['id']} para {job['user_id']}...")
                payload = {"to": job['user_id'], "text": job['message_text']}
                if job['media_data']:
                    payload['mediaData'] = job['media_data']
                    payload['fileName'] = job['file_name']

                try:
                    response = requests.post(GATEWAY_URL, json=payload, timeout=20)
                    response.raise_for_status()
                    cursor.execute("DELETE FROM outbound_queue WHERE id = ?", (job['id'],))
                    conn.commit()
                    print(f"Job {job['id']} enviado com sucesso.")
                except requests.exceptions.RequestException as e:
                    print(f"!!! ERRO AO ENVIAR JOB {job['id']}: {e}. Nova tentativa em breve.")
                    cursor.execute("UPDATE outbound_queue SET attempts = attempts + 1 WHERE id = ?", (job['id'],))
                    conn.commit()
        except Exception as e:
            print(f"!!! ERRO INESPERADO NO WORKER DA FILA: {e}")
            if job:
                cursor.execute("UPDATE outbound_queue SET attempts = attempts + 1 WHERE id = ?", (job['id'],))
                conn.commit()

        conn.close()
        time.sleep(2) 

def start_queue_worker():
    """Inicia o worker da fila em uma thread separada."""
    worker_thread = threading.Thread(target=_process_outbound_queue, daemon=True)
    worker_thread.start()
    print("--> Worker da fila de mensagens iniciado.")