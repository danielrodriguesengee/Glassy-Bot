import csv

import os

import logging



messages = {}



def load_messages():

    """

    Carrega as mensagens de um arquivo CSV para um dicionário em memória.

    O arquivo CSV deve ter duas colunas: 'key' e 'text'.

    """

    global messages

    try:

        file_path = os.path.join(os.path.dirname(__file__), 'messages.csv')

        

        with open(file_path, mode='r', encoding='utf-8') as infile:

            reader = csv.reader(infile)

            next(reader)  # Pula o cabeçalho (key,text)

            for row in reader:

                if row and len(row) >= 2:

                    key = row[0]

                    text = row[1]

                    messages[key] = text

        

        logging.info("Dicionário de mensagens carregado com sucesso.")



    except Exception as e:

        logging.critical(f"ERRO CRÍTICO AO CARREGAR MENSAGENS: {e}", exc_info=True)





def get_message(key, **kwargs):

    """

    Retorna uma mensagem formatada do dicionário.

    Substitui placeholders como {nome} pelos valores em kwargs.

    Converte o texto '\n' para quebras de linha reais.

    """

    message_template = messages.get(key)

    if message_template:

        try:

            # --- ALTERAÇÃO AQUI ---

            # Adicionamos .replace('\\n', '\n') para garantir a quebra de linha

            formatted_message = message_template.format(**kwargs).replace('\\n', '\n')

            return formatted_message

        except KeyError as e:

            logging.warning(f"Placeholder {e} não encontrado para a chave '{key}'.")

            return message_template.replace('\\n', '\n')

    else:

        logging.warning(f"A chave de mensagem '{key}' não foi encontrada.")

        return f"AVISO: Chave '{key}' não encontrada."
