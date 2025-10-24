import schedule

import time

import threading

import pytz

import re

from datetime import datetime, timedelta

import database_manager

from services.calendar_service import get_calendar_service, update_event_description

from message_queue import queue_message

from message_manager import get_message

from config import CALENDAR_ID, ENDERECO_STUDIO

import utils # Importa o módulo utils para acessar a função de timeout



def send_reminder_if_needed(event, hours_before, reminder_tag):

    description = event.get('description', '')

    summary = event.get('summary', 'Seu compromisso')

    start_time_str = event['start'].get('dateTime')

    

    if not start_time_str or reminder_tag in description:

        return



    tz = pytz.timezone('America/Sao_Paulo')

    start_time = datetime.fromisoformat(start_time_str).astimezone(tz)

    now = datetime.now(tz)

    

    time_to_event = start_time - now

    

    lower_bound = timedelta(hours=hours_before) - timedelta(minutes=5)

    upper_bound = timedelta(hours=hours_before) + timedelta(minutes=5)



    if lower_bound < time_to_event < upper_bound:

        try:

            phone_number_jid = get_phone_from_event(event)



            if phone_number_jid:

                user_id = phone_number_jid

                

                parts = summary.split(' - ')

                service_name = parts[1].strip() if len(parts) > 1 else "seu serviço"

                

                message_key = f'REMINDER_{hours_before}H'

                

                reminder_message = get_message(

                    message_key, 

                    service=service_name,

                    start_time=start_time.strftime('%H:%M'),

                    address=ENDERECO_STUDIO

                )

                

                if not reminder_message or "não foi encontrada" in reminder_message:

                    print(f"⚠️ AVISO: A chave de mensagem '{message_key}' não foi encontrada. Lembrete não enviado.")

                    return



                queue_message(user_id, reminder_message)

                

                _, data, history = database_manager.get_user_state_and_history(user_id)

                database_manager.set_user_state_and_history(user_id, "AWAITING_REMINDER_CONFIRMATION", data, history)

                

                new_description = f"{description} | {reminder_tag}"

                update_event_description(event['id'], new_description)

                

                client_name = parts[0].strip() if len(parts) > 0 else "Cliente"

                print(f"✅ Lembrete de {hours_before}h enfileirado para {client_name} ({user_id}) e estado alterado.")

            else:

                print(f"⚠️ Lembrete de {hours_before}h para '{summary}' não enviado: Telefone não encontrado na descrição.")



        except Exception as e:

            print(f"!!! ERRO AO PROCESSAR LEMBRETE DE {hours_before}h para o evento '{summary}': {e}")



def get_phone_from_event(event):

    description = event.get('description', '')

    match = re.search(r'Contato:\s*(\S+)', description)

    

    if not match:

        print(f"AVISO: Não foi possível encontrar o telefone na descrição do evento ID: {event.get('id')}")

        return None

        

    phone_number_raw = match.group(1)

    phone_digits = re.sub(r'[^0-9]', '', phone_number_raw)



    if not phone_digits:

        print(f"AVISO: Telefone encontrado na descrição do evento ID {event.get('id')} não contém dígitos válidos.")

        return None



    if len(phone_digits) >= 10 and not phone_digits.startswith('55'):

        phone_digits = '55' + phone_digits



    return f"{phone_digits}@s.whatsapp.net"



def check_reminders():

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Verificando agendamentos para lembretes...")

    service = get_calendar_service()

    now = datetime.now(pytz.utc)

    timeMin = now.isoformat()

    timeMax = (now + timedelta(hours=25)).isoformat()

    

    try:

        events_result = service.events().list(

            calendarId=CALENDAR_ID, timeMin=timeMin, timeMax=timeMax,

            singleEvents=True, orderBy='startTime'

        ).execute()

        events = events_result.get('items', [])

        

        for event in events:

            send_reminder_if_needed(event, 24, "Lembrete_24h_OK")

            send_reminder_if_needed(event, 1, "Lembrete_1h_OK")

    except Exception as e:

        print(f"!!! ERRO CRÍTICO AO BUSCAR EVENTOS DA AGENDA: {e}")



def run_scheduler():

    # --- AJUSTE APLICADO AQUI ---

    # Agora ambas as funções são agendadas para rodar.

    schedule.every(1).minutes.do(check_reminders)

    schedule.every(1).minutes.do(utils.check_state_timeouts) # <-- ADICIONADO



    while True:

        schedule.run_pending()

        time.sleep(60)



def start_reminder_scheduler():

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)

    scheduler_thread.start()

    print("--> Agendador de Lembretes e Timeouts (1min) iniciado.") # <-- MENSAGEM ATUALIZADA
