import datetime

import re

import logging

from google.oauth2.service_account import Credentials

from googleapiclient.discovery import build

import pytz

from config import CREDENTIALS_PATH, SCOPES, CALENDAR_ID, DURACAO_EVENTO_MIN, ENDERECO_STUDIO, HORARIOS_FIXOS

from message_manager import get_message



def parse_natural_date(date_str: str):

    today = datetime.date.today()

    date_str = date_str.lower().strip()

    if "hoje" in date_str:

        return today

    if "amanhã" in date_str:

        return today + datetime.timedelta(days=1)

    if date_str == "hoje":

        return today



    weekdays = {

        "segunda": 0, "terça": 1, "terca": 1, "quarta": 2,

        "quinta": 3, "sexta": 4, "sábado": 5, "sabado": 5

    }

    for day_name, day_index in weekdays.items():

        if day_name in date_str:

            days_ahead = day_index - today.weekday()

            if "próxima" in date_str or "proxima" in date_str or days_ahead <= 0:

                days_ahead += 7

            return today + datetime.timedelta(days=days_ahead)

    try:

        dia, mes = map(int, re.findall(r'\d+', date_str))

        ano = today.year

        if mes < today.month or (mes == today.month and dia < today.day):

            ano += 1

        return datetime.date(ano, mes, dia)

    except (ValueError, IndexError):

        return None



def get_calendar_service():

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)

    return build('calendar', 'v3', credentials=creds)



def get_available_slots(date_str: str):

    requested_date = parse_natural_date(date_str)

    if not requested_date:

        return get_message('SCHEDULING_INVALID_DATE')

    if requested_date.weekday() == 6:

        next_day = requested_date + datetime.timedelta(days=1)

        return get_message('SCHEDULING_SUNDAY_CLOSED', next_day=next_day.strftime('%d/%m'))

    if requested_date < datetime.date.today():

        return get_message('SCHEDULING_PAST_DATE')



    service = get_calendar_service()

    tz = pytz.timezone('America/Sao_Paulo')

    timeMin = datetime.datetime.combine(requested_date, datetime.time.min).astimezone(tz).isoformat()

    timeMax = datetime.datetime.combine(requested_date, datetime.time.max).astimezone(tz).isoformat()



    events_result = service.events().list(

        calendarId=CALENDAR_ID, timeMin=timeMin, timeMax=timeMax,

        singleEvents=True, orderBy='startTime'

    ).execute()



    events = events_result.get('items', [])

    busy_intervals = [(datetime.datetime.fromisoformat(e['start'].get('dateTime')), 

                       datetime.datetime.fromisoformat(e['end'].get('dateTime'))) 

                      for e in events if 'dateTime' in e['start']]



    horarios_disponiveis = []

    now_in_tz = datetime.datetime.now(tz)



    for slot_str in HORARIOS_FIXOS:

        slot_time_naive = datetime.datetime.strptime(slot_str, "%H:%M").time()

        slot_datetime = tz.localize(datetime.datetime.combine(requested_date, slot_time_naive))

        

        is_seven_am_slot = (slot_str == "07:00")

        is_after_nine_pm = (now_in_tz.hour >= 21)

        is_for_tomorrow = (requested_date == now_in_tz.date() + datetime.timedelta(days=1))

        

        if is_seven_am_slot and is_after_nine_pm and is_for_tomorrow:

            continue

        

        if slot_datetime < (now_in_tz + datetime.timedelta(hours=3)):

            continue



        slot_end_time = slot_datetime + datetime.timedelta(minutes=DURACAO_EVENTO_MIN)

        if not any(max(start, slot_datetime) < min(end, slot_end_time) for start, end in busy_intervals):

            horarios_disponiveis.append(slot_str)

    

    return horarios_disponiveis



def create_event(name: str, service: str, date_str: str, time_str: str, phone: str, obs: str = 'Nenhuma'):

    requested_date = parse_natural_date(date_str)

    if not requested_date:

        raise ValueError("Data inválida para criar evento.")

    

    service_calendar = get_calendar_service()

    hora, minuto = map(int, time_str.split(':'))

    start_time = datetime.datetime(requested_date.year, requested_date.month, requested_date.day, hora, minuto)

    end_time = start_time + datetime.timedelta(minutes=DURACAO_EVENTO_MIN)



    # --- LÓGICA DE FORMATAÇÃO ADICIONADA/GARANTIDA AQUI ---

    # Garante que o nome do cliente tenha as iniciais maiúsculas (Ex: "Teste Teste")

    nome_formatado = ' '.join(word.capitalize() for word in name.split())

    # Garante que o nome do serviço tenha a inicial maiúscula (Ex: "Alongamento")

    servico_formatado = service.capitalize()



    event = {

        'summary': f"{nome_formatado} - {servico_formatado}", # Usa as variáveis formatadas

        'location': ENDERECO_STUDIO,

        'description': f"Contato: {phone} | Observações: {obs}",

        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/Sao_Paulo'},

        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/Sao_Paulo'},

    }

    return service_calendar.events().insert(calendarId=CALENDAR_ID, body=event).execute()



def find_event_to_cancel(phone_number: str):

    service = get_calendar_service()

    clean_input_phone = re.sub(r'\D', '', phone_number)

    if not clean_input_phone:

        return None, None, None, None



    now = datetime.datetime.now(pytz.utc)

    timeMin = now.isoformat()

    timeMax = (now + datetime.timedelta(days=90)).isoformat()



    events_result = service.events().list(

        calendarId=CALENDAR_ID, timeMin=timeMin, timeMax=timeMax,

        singleEvents=True, orderBy='startTime'

    ).execute()

    events = events_result.get('items', [])



    for event in events:

        description = event.get('description', '')

        match = re.search(r'Contato:\s*(\S+)', description)

        if match:

            stored_phone = re.sub(r'\D', '', match.group(1))

            

            match_found = (stored_phone == clean_input_phone or

                           stored_phone.endswith(clean_input_phone) or

                           clean_input_phone.endswith(stored_phone) or

                           (len(stored_phone) >= 8 and len(clean_input_phone) >= 8 and stored_phone[-8:] == clean_input_phone[-8:]))



            if match_found:

                event_id = event['id']

                summary = event.get('summary', 'Compromisso')

                start_time_str = event['start'].get('dateTime')

                start_dt_obj = datetime.datetime.fromisoformat(start_time_str).astimezone(pytz.timezone('America/Sao_Paulo'))

                formatted_datetime = f"dia {start_dt_obj.strftime('%d/%m')} às {start_dt_obj.strftime('%H:%M')}"

                return summary, formatted_datetime, event_id, start_dt_obj



    return None, None, None, None



def confirm_cancel_event(event_id: str):

    service = get_calendar_service()

    try:

        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()

        return True

    except:

        return False



def get_events_for_next_hours(hours: int):

    service = get_calendar_service()

    now_utc = datetime.datetime.now(pytz.utc)

    timeMin = now_utc.isoformat()

    timeMax = (now_utc + datetime.timedelta(hours=hours)).isoformat()

    try:

        events_result = service.events().list(

            calendarId=CALENDAR_ID,

            timeMin=timeMin,

            timeMax=timeMax,

            singleEvents=True,

            orderBy='startTime'

        ).execute()

        return events_result.get('items', [])

    except Exception as e:

        logging.error(f"ERRO AO BUSCAR EVENTOS DA AGENDA: {e}")

        return []



def update_event_description(event_id: str, new_description: str):

    service = get_calendar_service()

    try:

        event_patch = {'description': new_description}

        service.events().patch(calendarId=CALENDAR_ID, eventId=event_id, body=event_patch).execute()

        return True

    except Exception as e:

        logging.error(f"ERRO AO ATUALIZAR DESCRIÇÃO DO EVENTO: {e}")

        return False
