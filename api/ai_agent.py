# --- Conteúdo do arquivo: api/ai_agent.py ---

import requests

import json

import re

import unicodedata

import logging

from config import CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, CLOUDFLARE_AI_MODEL



# --- REGRAS DE PRIORIDADE REFINADAS PARA EVITAR FALSOS POSITIVOS ---

SYSTEM_INSTRUCTION = """Sua única tarefa é analisar o texto do usuário e extrair informações para um sistema de agendamento de unhas.



Responda APENAS com um objeto JSON válido e nada mais. NÃO adicione texto, explicações ou formatação além do JSON puro.



O JSON deve ter as seguintes chaves possíveis: 'intent', 'service', 'date_str', 'time_str', 'confirmation'.



'intent' pode ser: 'schedule', 'cancel', 'get_info', 'human_transfer', 'greeting', 'confirmation', 'course_info', 'ask_availability', 'thanking', 'unknown'.



'confirmation' pode ser: 'yes', 'no'.



REGRAS DE PRIORIDADE:

1.  A intenção 'greeting' DEVE ser usada APENAS para saudações curtas e explícitas (ex: "oi", "olá", "bom dia"). Nomes de pessoas ou outras frases NÃO devem ser classificados como 'greeting'.

2.  A intenção 'human_transfer' DEVE ser usada APENAS quando o usuário pedir explicitamente para falar com uma pessoa (ex: "falar com atendente", "ajuda", "atendente humano"). NUNCA infira esta intenção a partir de um nome próprio como 'Larissa Felix' ou 'Rodrigues'.

3.  Se a palavra "curso", "aula" ou "aprender" estiver na frase, a intenção DEVE ser 'course_info'.

4.  Se "cancelar" ou "desmarcar" estiverem na frase, a intenção DEVE ser 'cancel'.

5.  Se mencionar data/hora (ex: "amanhã", "dia 15"), priorize 'schedule'.

6.  Se o usuário apenas nomear um serviço (ex: "manutenção"), a intenção DEVE ser 'schedule' e o nome do serviço deve ser extraído.



REGRAS GERAIS:

- 'confirmation' com 'yes': "sim", "pode ser", "claro", "confirmo", "ok", "perfeito".

- 'confirmation' com 'no': "não", "nao", "nenhum", "deixa pra lá".

- 'thanking': Qualquer forma de agradecimento (ex: "obrigado", "valeu").



EXEMPLOS DE EXTRAÇÃO COMPLEXA:

"Oi, tem horário pra amanhã de manhã?" -> {"intent": "schedule", "date_str": "amanhã", "time_str": "manhã"}

"Queria marcar manutenção para a próxima sexta" -> {"intent": "schedule", "service": "manutenção", "date_str": "próxima sexta"}

"Qual o valor do curso?" -> {"intent": "course_info"}

"sim" -> {"intent": "confirmation", "confirmation": "yes"}

"não, nenhuma" -> {"intent": "confirmation", "confirmation": "no"}

"Larissa Felix" -> {"intent": "unknown"}

"Daniel Rodrigues" -> {"intent": "unknown"}

"""



# --- Palavras-chave para confirmações ---

YES_KEYWORDS = {

    "sim", "pode ser", "aham", "claro", "confirmo", "ok", "okk", "okay",

    "anhan", "uhum", "certo", "beleza", "blz", "positivo", "ta", "tá",

    "combinado", "perfeito", "isso mesmo", "isso ai", "isso aí", "show",

    "top", "fé", "bora", "demoro", "demorô", "👍", "👌", "✅", "esse mesmo"

}



NO_KEYWORDS = {

    "não", "nao", "nenhum", "deixa pra la", "deixa pra lá", "sair",

    "cancela", "depois", "negativo", "nunca", "prefiro nao", "prefiro não",

    "acho que nao", "acho que não", "to fora", "tô fora", "nem",

    "❌", "🚫", "🙅"

}



EMOJI_MAP = {

    "👍": "sim", "👌": "sim", "✅": "sim",

    "❌": "nao", "🚫": "nao", "🙅": "nao"

}



# --- Normalização de texto ---

def normalize_text(text: str) -> str:

    text = text.lower().strip()

    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')

    for emoji, replacement in EMOJI_MAP.items():

        text = text.replace(emoji, f" {replacement} ")

    text = re.sub(r'\s+', ' ', text)

    return text.strip()



# --- Checagem local de confirmações ---

def local_confirmation_check(message: str):

    msg_norm = normalize_text(message)

    if msg_norm in YES_KEYWORDS:

        return {"intent": "confirmation", "confirmation": "yes"}

    if msg_norm in NO_KEYWORDS:

        return {"intent": "confirmation", "confirmation": "no"}

    return None



# --- Checagem local de intenções simples ---

def local_intent_check(message: str):

    msg_norm = normalize_text(message)

    # Greeting simples

    if msg_norm in {"oi", "ola", "bom dia", "boa tarde", "boa noite"}:

        return {"intent": "greeting"}

    # Agradecimento

    if any(word in msg_norm for word in ["obrigado", "obg", "valeu", "agradecido", "show de bola"]):

        return {"intent": "thanking"}

    # Curso / aula

    if any(word in msg_norm for word in ["curso", "aula", "aprender"]):

        return {"intent": "course_info"}

    # Cancelamento

    if any(word in msg_norm for word in ["cancelar", "desmarcar", "imprevisto"]):

        return {"intent": "cancel"}

    # Pedido de preço

    if any(word in msg_norm for word in ["valor", "preco", "quanto"]) and "curso" not in msg_norm:

        return {"intent": "get_info"}

    # Disponibilidade

    if any(word in msg_norm for word in ["horario", "agenda", "só tem esses horários"]):

        return {"intent": "ask_availability"}

    return None



# --- Combinação de checagens locais ---

def detect_local_intent(message: str):

    local_conf = local_confirmation_check(message)

    if local_conf:

        return local_conf

    return local_intent_check(message)



# --- Chamada para Cloudflare AI ---

def call_cloudflare_ai(messages):

    try:

        api_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_AI_MODEL}"

        headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}

        response = requests.post(api_url, headers=headers, json={"messages": messages}, timeout=10)

        response.raise_for_status()

        result = response.json()

        response_text = result.get("result", {}).get("response", "")

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if json_match:

            return json.loads(json_match.group(0))

        else:

            logging.warning(f"!!! AVISO: Nenhum JSON encontrado. Resposta: {response_text}")

    except Exception as e:

        logging.warning(f"!!! ERRO AO CHAMAR API CLOUDFLARE: {e}")

    return {"intent": "unknown"}



# --- Função principal de extração de intenção ---

def extract_intent(user_message: str, history: list = None):

    # 1. Tenta detectar localmente

    local_intent = detect_local_intent(user_message)

    if local_intent:

        return local_intent, []



    # 2. Se não detectado localmente, chama API Cloudflare

    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

    if history:

        messages.extend(history[-3:])

    messages.append({"role": "user", "content": user_message})



    return call_cloudflare_ai(messages), []
