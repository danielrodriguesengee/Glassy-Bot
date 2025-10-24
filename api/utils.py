import re

import os

import requests

import logging

from datetime import datetime, timedelta

from config import AGENT_WHATSAPP_NUMBER

from message_queue import queue_message

from message_manager import get_message

import sqlite3

import json

from config import DB_PATH





def normalize_time_input(time_str: str) -> str:

    """

    Normaliza a entrada de tempo do usuário para o formato HH:MM.

    Exemplos: "7h" -> "07:00", "10" -> "10:00", "1330" -> "13:30"

    """

    if "manhã" in time_str.lower() or "manha" in time_str.lower():

        return "09:00"



    digits = re.sub(r'\D', '', time_str)



    if len(digits) == 1:

        return f"0{digits}:00"

    if len(digits) == 2:

        if int(digits) < 24:

            return f"{digits}:00"

    if len(digits) == 3:

        return f"0{digits[0]}:{digits[1:]}"

    if len(digits) == 4:

        return f"{digits[:2]}:{digits[2:]}"



    return ""





def format_agent_id(agent_number):

    """Garante que o ID do agente esteja no formato correto para o WhatsApp."""

    if not agent_number:

        return None



    clean_number = re.sub(r'\D', '', agent_number)

    if '@s.whatsapp.net' not in clean_number:

        return f"{clean_number}@s.whatsapp.net"

    return clean_number





def notify_human_agent(user_id: str):

    """Notifica a atendente que um usuário solicitou atendimento humano."""

    agent_id = format_agent_id(AGENT_WHATSAPP_NUMBER)

    if not agent_id:

        logging.error("Número do agente não configurado para notificação.")

        return

    client_number = user_id.split('@')[0]

    message = get_message('AGENT_NOTIFY_HUMAN', client_number=client_number)

    queue_message(agent_id, message)





def notify_booking_to_agent(booking_data: dict):

    """Notifica a atendente sobre um novo agendamento."""

    agent_id = format_agent_id(AGENT_WHATSAPP_NUMBER)

    if not agent_id:

        logging.error("Número do agente não configurado para notificação.")

        return



    from services.calendar_service import parse_natural_date

    parsed_date = parse_natural_date(booking_data.get('date_str', ''))

    formatted_date = parsed_date.strftime('%d/%m') if parsed_date else booking_data.get('date_str')



    if booking_data.get('obs') and booking_data['obs'] != 'Nenhuma':

        message = get_message(

            'AGENT_NOTIFY_BOOKING_WITH_OBS',

            name=booking_data['name'],

            service=booking_data['service'],

            formatted_date=formatted_date,

            time=booking_data['time'],

            obs=booking_data['obs']

        )

    else:

        message = get_message(

            'AGENT_NOTIFY_BOOKING',

            name=booking_data['name'],

            service=booking_data['service'],

            formatted_date=formatted_date,

            time=booking_data['time']

        )



    queue_message(agent_id, message)





def notify_cancellation_to_agent(cancellation_data: dict):

    """Notifica a atendente sobre um cancelamento."""

    agent_id = format_agent_id(AGENT_WHATSAPP_NUMBER)

    if not agent_id:

        logging.error("Número do agente não configurado para notificação.")

        return



    client_name = cancellation_data.get('summary', 'N/A').split(' - ')[0]

    datetime_str = cancellation_data.get('datetime', 'N/A')



    message = get_message(

        'AGENT_NOTIFY_CANCELLATION',

        client_name=client_name,

        datetime=datetime_str

    )



    queue_message(agent_id, message)





# ============================================================

# ✅ FUNÇÃO DE TIMEOUT CORRIGIDA E MAIS ROBUSTA

# ============================================================

def check_state_timeouts(timeout_minutes: int = 10):

    """

    Verifica sessões inativas e as encerra se o tempo desde a última

    atualização de estado ultrapassar 'timeout_minutes'.

    """

    logging.info("Verificando sessões inativas para timeout...")

    try:

        conn = sqlite3.connect(DB_PATH, check_same_thread=False)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()

        

        # --- AJUSTE APLICADO AQUI ---

        # A query agora ignora também o estado de lembrete.

        cursor.execute("SELECT user_id, data FROM conversations WHERE state NOT IN ('INITIAL', 'HUMAN_ATTENDANCE', 'AWAITING_REMINDER_CONFIRMATION')")

        rows = cursor.fetchall()



        now = datetime.now()

        timeout_delta = timedelta(minutes=timeout_minutes)



        for row in rows:

            user_id = row['user_id']

            

            # Pula se o campo 'data' for nulo ou vazio

            if not row['data']:

                continue



            data = json.loads(row['data'])

            timestamp_str = data.get('state_timestamp')



            # Pula este usuário se, por algum motivo, ele não tiver um timestamp

            if not timestamp_str:

                continue



            try:

                last_update = datetime.fromisoformat(timestamp_str)

                inactive_time = now - last_update



                if inactive_time > timeout_delta:

                    logging.info(

                        f"Encerrando sessão de {user_id}. "

                        f"Tempo inativo: {inactive_time} (maior que {timeout_delta})"

                    )

                    from database_manager import set_user_state_and_history

                    set_user_state_and_history(user_id, "INITIAL", {}, [])

                    queue_message(user_id, get_message('SESSION_TIMEOUT'))

            

            except (ValueError, TypeError):

                # Ignora o registro se o timestamp estiver mal formatado

                logging.warning(f"Timestamp inválido para o usuário {user_id}. Pulando verificação de timeout.")

                continue



        conn.close()



    except Exception as e:

        logging.error(f"Erro CRÍTICO ao verificar timeouts de sessão: {e}", exc_info=True)
