# --- Conteúdo do arquivo: api/handlers/menu_handler.py ---
import os
import base64
from message_queue import queue_message
from utils import notify_human_agent
from message_manager import get_message

def handle_initial_message(user_id):
    return get_message('WELCOME') # 

def get_portfolio(user_id: str):
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'media', 'portfolio.pdf')
        if not os.path.exists(file_path):
            error_message = get_message('PORTFOLIO_ERROR') # 
            queue_message(user_id, error_message)
            return

        with open(file_path, "rb") as pdf_file:
            encoded_string = base64.b64encode(pdf_file.read()).decode('utf-8')
        
        caption_text = get_message('PORTFOLIO_CAPTION') # 
        
        queue_message(
            user_id=user_id, 
            text=caption_text, 
            media_data=encoded_string, # 
            file_name="Portfolio - Glass Studio.pdf"
        )
    except Exception as e:
        print(f"!!! ERRO AO ENVIAR PORTFÓLIO: {e}")

def get_course_info():
    return get_message('COURSE_INFO') # 

def transfer_to_human(user_id: str, reason: str = "user_request"):
    notify_human_agent(user_id)
    return get_message('TRANSFER_TO_HUMAN') #