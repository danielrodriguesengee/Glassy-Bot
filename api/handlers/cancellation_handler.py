# --- Conteúdo do arquivo: api/handlers/cancellation_handler.py ---

import database_manager

from services.calendar_service import find_event_to_cancel, confirm_cancel_event

from utils import notify_cancellation_to_agent

from message_manager import get_message

from datetime import datetime, timedelta

import pytz

# Precisamos do menu_handler para a transferência

from handlers import menu_handler



def handle_cancellation(user_id, state, data, extracted_intent, raw_message, history):

    

    if state in ["INITIAL", "AWAITING_CANCEL_PHONE"]:

        # Se o bot está esperando o telefone e recebe um número

        if state == "AWAITING_CANCEL_PHONE" and any(char.isdigit() for char in raw_message):

            phone = raw_message

            summary, formatted_datetime, event_id, start_time_obj = find_event_to_cancel(phone)

            

            if event_id:

                # --- NOVA LÓGICA DE VERIFICAÇÃO DE 24H ---

                tz = pytz.timezone('America/Sao_Paulo')

                now = datetime.now(tz)

                time_remaining = start_time_obj - now



                # Se faltar 24h ou mais, segue o fluxo normal

                if time_remaining >= timedelta(hours=24):

                    data.update({'cancel_event_id': event_id, 'summary': summary, 'datetime': formatted_datetime})

                    client_name = summary.split(' - ', 1)[0].strip()

                    service_name = summary.split(' - ', 1)[1].strip() if ' - ' in summary else "seu serviço"

                    database_manager.set_user_state_and_history(user_id, "AWAITING_CANCEL_CONFIRM", data, history)

                    return get_message('CANCELLATION_FOUND_PROMPT', client_name=client_name, service_name=service_name, formatted_datetime=formatted_datetime)

                # Se faltar menos de 24h, entra no novo fluxo

                else:

                    database_manager.set_user_state_and_history(user_id, "AWAITING_CANCEL_TOO_CLOSE_CONFIRM", data, history)

                    return get_message('CANCELLATION_TOO_CLOSE')

            

            else: # Se não encontrou evento

                database_manager.set_user_state_and_history(user_id, "AWAITING_CANCEL_PHONE", data, history)

                return get_message('CANCELLATION_NOT_FOUND')

        

        else: # Se não for um número ou for o estado inicial, pede o telefone

            database_manager.set_user_state_and_history(user_id, "AWAITING_CANCEL_PHONE", data, history)

            return get_message('CANCELLATION_REQUEST_PHONE')



    # Estado normal de confirmação de cancelamento (para mais de 24h)

    if state == "AWAITING_CANCEL_CONFIRM":

        response = get_message('CANCELLATION_ABORTED')

        if extracted_intent.get("confirmation") == "yes":

            if confirm_cancel_event(data.get('cancel_event_id')):

                notify_cancellation_to_agent(data)

                response = get_message('CANCELLATION_CONFIRMED')

            else:

                response = get_message('CANCELLATION_API_ERROR')

        

        database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

        return response



    # --- NOVO ESTADO: Aguardando resposta para transferência (cancelamento < 24h) ---

    if state == "AWAITING_CANCEL_TOO_CLOSE_CONFIRM":

        if extracted_intent.get("confirmation") == "yes":

            # Reutiliza a função de transferência para o humano

            database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, history)

            return menu_handler.transfer_to_human(user_id)

        else: # Se o usuário responder "Não"

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('CANCELLATION_TOO_CLOSE_NO_AGENT')



    # Fallback para qualquer outro estado inesperado

    database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

    return get_message('GENERAL_LOST_FALLBACK')
