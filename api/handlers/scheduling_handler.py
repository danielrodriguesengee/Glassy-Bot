import database_manager

import re

import logging

from services.calendar_service import get_available_slots, create_event, parse_natural_date

from utils import normalize_time_input, notify_booking_to_agent

from config import ENDERECO_STUDIO

from message_manager import get_message

from handlers import menu_handler



def handle_scheduling(user_id, state, data, extracted_intent, raw_message, history):

    if state in ["INITIAL", "AWAITING_DATE"]:

        data.update(extracted_intent)

        if state == "AWAITING_DATE" and extracted_intent.get("confirmation") == "no":

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('SCHEDULING_NO_PROBLEM_ON_CANCEL')



        date_to_check = extracted_intent.get('date_str') if extracted_intent.get('date_str') else raw_message

        parsed_date = parse_natural_date(date_to_check)

        if not parsed_date:

            database_manager.set_user_state_and_history(user_id, "AWAITING_DATE", data, history)

            return get_message('SCHEDULING_REQUEST_DATE')



        available_slots = get_available_slots(date_to_check)

        if isinstance(available_slots, str):

            database_manager.set_user_state_and_history(user_id, "AWAITING_DATE", data, history)

            return available_slots

        if not available_slots:

            database_manager.set_user_state_and_history(user_id, "AWAITING_DATE", data, history)

            return get_message('SCHEDULING_NO_SLOTS')



        data['date_str'] = date_to_check

        data['available_slots'] = available_slots

        horarios_str = ", ".join(available_slots)

        formatted_date = parsed_date.strftime('%d/%m')

        database_manager.set_user_state_and_history(user_id, "AWAITING_TIME", data, history)

        return get_message('SCHEDULING_AVAILABLE_SLOTS', formatted_date=formatted_date, horarios_str=horarios_str)



    elif state == "AWAITING_TIME":

        is_asking = extracted_intent.get("intent") == "ask_availability"

        if is_asking:

            database_manager.set_user_state_and_history(user_id, "AWAITING_TRANSFER_CONFIRM", data, history)

            return get_message('SCHEDULING_ASK_SWITCH_SLOT')

        if extracted_intent.get("confirmation") == "no":

            database_manager.set_user_state_and_history(user_id, "AWAITING_DATE", {}, history)

            return get_message('SCHEDULING_TRY_ANOTHER_DATE')



        normalized_time = normalize_time_input(raw_message)

        if normalized_time and normalized_time in data.get('available_slots', []):

            data['time'] = normalized_time

            data['last_bot_question'] = get_message('SCHEDULING_TIME_CONFIRMED')

            database_manager.set_user_state_and_history(user_id, "AWAITING_SERVICE", data, history)

            return get_message('SCHEDULING_TIME_CONFIRMED')

        else:

            horarios_str = ", ".join(data.get('available_slots', []))

            return get_message('SCHEDULING_INVALID_TIME', horarios_str=horarios_str)



    elif state == "AWAITING_SERVICE":

        if "intent" in extracted_intent and extracted_intent["intent"] == "schedule" and "service" in extracted_intent:

            service = extracted_intent["service"]

        else:

            service = raw_message.strip()



        if not service:

            return get_message('SCHEDULING_REQUEST_SERVICE')

        

        data['service'] = service

        database_manager.set_user_state_and_history(user_id, "AWAITING_NAME", data, history)

        return get_message('SCHEDULING_SERVICE_CONFIRMED')



    elif state == "AWAITING_NAME":

        clean_name = raw_message.strip()

        if len(clean_name.split()) < 2:

            return get_message('SCHEDULING_REQUEST_FULL_NAME')

        

        data['name'] = clean_name

        

        # --- MELHORIA APLICADA AQUI ---

        # 1. Pega o número de telefone diretamente do ID do usuário.

        phone_number = user_id.split('@')[0]

        if not phone_number.startswith('55'):

            phone_number = '55' + phone_number

        data['phone'] = phone_number

        

        # 2. Pula a confirmação de telefone e vai direto para as observações.

        database_manager.set_user_state_and_history(user_id, "AWAITING_OBS", data, history)

        return get_message('SCHEDULING_PHONE_CONFIRMED_ASK_OBS') # Pergunta direto por observações



    # --- OS ESTADOS AWAITING_PHONE E AWAITING_CORRECT_PHONE FORAM REMOVIDOS ---



    elif state == "AWAITING_OBS":

        data['obs'] = raw_message if extracted_intent.get("confirmation") != "no" else 'Nenhuma'

        database_manager.set_user_state_and_history(user_id, "AWAITING_POLICY_CONFIRM", data, history)

        return get_message('SCHEDULING_POLICY_PROMPT')



    elif state == "AWAITING_POLICY_CONFIRM":

        if extracted_intent.get("confirmation") == "yes":

            try:

                # Centraliza a formatação do nome e serviço para garantir consistência

                data['name'] = ' '.join(word.capitalize() for word in data.get('name', '').split())

                data['service'] = data.get('service', '').capitalize()



                parsed_date = parse_natural_date(data.get('date_str'))

                formatted_date = parsed_date.strftime('%d/%m') if parsed_date else data.get('date_str')

                

                create_event(

                    name=data.get('name'), 

                    service=data.get('service'), 

                    date_str=data.get('date_str'), 

                    time_str=data.get('time'),

                    phone=data.get('phone'), 

                    obs=data.get('obs')

                )

                

                notify_booking_to_agent(data)

                database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

                

                return get_message('SCHEDULING_FINAL_CONFIRMATION', 

                                   name=data['name'], 

                                   service=data['service'], 

                                   formatted_date=formatted_date, 

                                   time=data['time'], 

                                   address=ENDERECO_STUDIO)

            

            except Exception as e:

                logging.critical(f"ERRO NA ETAPA FINAL DE AGENDAMENTO: {e}", exc_info=True)

                database_manager.set_user_state_and_history(user_id, "HUMAN_ATTENDANCE", data, history)

                return menu_handler.transfer_to_human(user_id)

        else:

            database_manager.set_user_state_and_history(user_id, "INITIAL", {}, [])

            return get_message('SCHEDULING_CANCELLED')



    return get_message('GENERAL_LOST_FALLBACK')
