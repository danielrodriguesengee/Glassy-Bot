import logging

import os

from flask import Flask, request, jsonify

from waitress import serve

import threading

import traceback

from collections import defaultdict



import database_manager

import ai_agent

from handlers import menu_handler, scheduling_handler, cancellation_handler

from services.reminder_service import start_reminder_scheduler

from message_queue import queue_message, start_queue_worker

from message_manager import load_messages, get_message



# --- CONFIGURAÇÃO DO LOGGING ---

log_format = '%(asctime)s - %(levelname)s - %(message)s'

logging.basicConfig(filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot.log'), 

                    level=logging.INFO, 

                    format=log_format,

                    encoding='utf-8')

# --- FIM DA CONFIGURAÇÃO ---



app = Flask(__name__)



user_locks = defaultdict(threading.Lock)

users_being_processed = set()



ESCAPE_INTENTS = ['get_info', 'course_info', 'human_transfer']

MENU_COMMANDS = {'menu', 'início', 'inicio', 'oi', 'olá', 'ola'}



def process_message(user_id, raw_message):

    state, data, history = database_manager.get_user_state_and_history(user_id)

    raw_message_clean = raw_message.strip()



    if raw_message_clean.lower() in MENU_COMMANDS:

        database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

        return menu_handler.handle_initial_message(user_id)



    updated_history = history + [{"role": "user", "content": raw_message_clean}]

    extracted_intent, _ = ai_agent.extract_intent(raw_message_clean, history)

    intent = extracted_intent.get("intent")

    

    logging.info(f"Usuário: {user_id}, Estado: {state}, Mensagem: '{raw_message_clean}', Intenção da IA: {intent}")



    # Lógica para resposta a lembretes

    if state == "AWAITING_REMINDER_CONFIRMATION":

        if intent in ["thanking", "greeting", "confirmation"]:

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('REMINDER_RESPONSE')

        else:

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return process_message(user_id, raw_message)



    if raw_message_clean.lower() in ['#pausarbot', '#reativarbot']:

        if raw_message_clean.lower() == '#pausarbot':

            database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, history)

            return get_message('AUTOMATION_PAUSED')

        else:

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('AUTOMATION_REACTIVATED')



    if state == "HUMAN_ATTENDANCE":

        return None



    confirmation = extracted_intent.get("confirmation")

    

    if state == "INITIAL" and raw_message_clean.isdigit():

        options = {'1': 'schedule', '2': 'cancel', '3': 'get_info', '4': 'course_info', '5': 'human_transfer'}

        if raw_message_clean in options:

            intent = options[raw_message_clean]

            extracted_intent['intent'] = intent



    if state.startswith("AWAITING_"):

        if intent in ESCAPE_INTENTS and state not in ["AWAITING_TRANSFER_CONFIRM", "AWAITING_NAME"]:

            last_question = data.get('last_bot_question', get_message('GENERAL_OK_IF_YOU_NEED_ANYTHING'))

            if intent == 'get_info':

                menu_handler.get_portfolio(user_id)

                return get_message('ESCAPE_INTENT_PORTFOLIO', last_question=last_question)

            elif intent == 'course_info':

                course_info_msg = menu_handler.get_course_info()

                return get_message('ESCAPE_INTENT_COURSE_INFO', course_info=course_info_msg, last_question=last_question)

            elif intent == 'human_transfer':

                database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, updated_history)

                return menu_handler.transfer_to_human(user_id=user_id)



        if intent == 'cancel' and not state.startswith("AWAITING_CANCEL_"):

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('GENERAL_OK_NO_PROBLEM')



        if state == "AWAITING_TRANSFER_CONFIRM":

            if confirmation == 'yes':

                database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, updated_history)

                return menu_handler.transfer_to_human(user_id=user_id)

            else:

                horarios_str = ", ".join(data.get('available_slots', []))

                database_manager.set_user_state_and_history(user_id, "AWAITING_TIME", data, updated_history)

                return get_message('TRANSFER_CONFIRM_REJECTED', horarios_str=horarios_str)



        elif state.startswith("AWAITING_CANCEL_"):

            return cancellation_handler.handle_cancellation(user_id, state, data, extracted_intent, raw_message_clean, updated_history)

        else:

            return scheduling_handler.handle_scheduling(user_id, state, data, extracted_intent, raw_message_clean, updated_history)



    if intent == "schedule":

        return scheduling_handler.handle_scheduling(user_id, 'INITIAL', data, extracted_intent, raw_message_clean, updated_history)



    if intent == "cancel":

        return cancellation_handler.handle_cancellation(user_id, 'INITIAL', data, extracted_intent, raw_message_clean, updated_history)



    if intent == "get_info":

        menu_handler.get_portfolio(user_id)

        database_manager.set_user_state_and_history(user_id, "INITIAL", data, updated_history)

        return get_message('PORTFOLIO_SENT')



    if intent == "course_info":

        response_text = menu_handler.get_course_info()

        data['last_bot_question'] = get_message('COURSE_INFO_PROMPT')

        database_manager.set_user_state_and_history(user_id, "AWAITING_TRANSFER_CONFIRM", data, updated_history)

        return response_text



    if intent == "human_transfer":

        database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, updated_history)

        return menu_handler.transfer_to_human(user_id=user_id)



    if intent == "greeting" or raw_message_clean.lower() in MENU_COMMANDS:

        database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

        return menu_handler.handle_initial_message(user_id)



    # --- CORREÇÃO APLICADA AQUI, CONFORME RECOMENDAÇÃO ---

    if intent == "thanking":

        database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

        return get_message('GENERAL_THANKS')



    if confirmation == 'no':

        database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

        return get_message('GENERAL_OK_IF_YOU_NEED_ANYTHING')



    logging.warning(f"Intent desconhecida registrada: {intent} para a mensagem '{raw_message_clean}'")

    database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

    return get_message('GENERAL_UNKNOWN_INTENT')



@app.route('/webhook', methods=['POST'])

def handle_webhook():

    webhook_data = request.json

    user_id = webhook_data.get('userId')

    raw_message = webhook_data.get('message', '').strip()



    if not user_id or not raw_message:

        return jsonify({"status": "error", "message": "Payload inválido"}), 400



    with user_locks[user_id]:

        if user_id in users_being_processed:

            logging.info(f"Lock: Mensagem de {user_id} ignorada, processamento anterior em andamento.")

            return jsonify({"status": "ok", "action": "ignored_due_to_lock"})

        users_being_processed.add(user_id)



        try:

            response_text = process_message(user_id, raw_message)

            if response_text:

                queue_message(user_id, response_text)

        except Exception as e:

            logging.critical(f"ERRO CRÍTICO NO PROCESSAMENTO DA MENSAGEM: {e}", exc_info=True)

            traceback.print_exc()

            queue_message(user_id, get_message('CRITICAL_ERROR_WEBHOOK'))

        finally:

            users_being_processed.remove(user_id)



    return jsonify({"status": "ok", "action": "queued"})



@app.route('/check-state', methods=['POST'])

def check_user_state():

    user_id = request.json.get('userId')

    if not user_id:

        return jsonify({"error": "userId não fornecido"}), 400



    state, _, _ = database_manager.get_user_state_and_history(user_id)

    return jsonify({"state": state})



if __name__ == '__main__':

    print("Iniciando a API da Glassy...")

    logging.info("--- INICIANDO A APLICAÇÃO ---")

    load_messages()

    database_manager.setup_database()

    logging.info("Banco de dados verificado e pronto.")



    start_reminder_scheduler()

    start_queue_worker()



    port = int(os.environ.get('PORT', 5000))

    print(f"--> Iniciando servidor de PRODUÇÃO (Waitress) na porta {port}")

    serve(app, host='0.0.0.0', port=port)
