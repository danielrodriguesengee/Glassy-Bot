import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'database', 'conversations.db')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
SCOPES = ['https://www.googleapis.com/auth/calendar']

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_AI_MODEL = '@cf/meta/llama-3-8b-instruct'

CALENDAR_ID = 'contatoglassstudio@gmail.com'
AGENT_WHATSAPP_NUMBER = '553799582660'

# --- MUDANÇA AQUI ---
# Agora, ele pega a URL do Gateway do ambiente. Se não encontrar, usa localhost como padrão.
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:3000/send-message')

HORARIOS_FIXOS = ["07:00", "10:00", "13:00", "16:00"]
DURACAO_EVENTO_MIN = 150
ENDERECO_STUDIO = "R. Juca Dias, 196, São Judas, Arcos/MG - CEP: 35600-144"