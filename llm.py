from dotenv import load_dotenv
from google import genai
import asyncio
import json
import os

MODELO = "gemini-3.5-flash-lite"

async def iniciar_llm(): 
    iniciado, llm = False, None
    
    try:
        load_dotenv()
        llm = genai.Client(api_key = os.environ["GOOGLE_API_KEY"])
        
        iniciado = True
    except Exception as e:
        print(f"Erro iniciando conexão com a IA: {str(e)}")
    
    return iniciado, llm
    
async def obter_resposta(llm, mensagens, ferramentas, modelo = MODELO):
    sucesso, resposta = False, None
    
    try:
        if not ferramentas:
            resposta = await llm.aio.interactions.create(
                input = mensagens,
                model = modelo
            )
        else:
            resposta = await llm.aio.interactions.create(
                input = mensagens,
                model = modelo,
                tools = ferramentas
            )
            
        sucesso = True
    except Exception as e:
        print(f"Erro obtendo resposta da IA: {str(e)}")

    return sucesso, resposta
    
def get_consumo_tokens(resposta):
    uso = resposta.usage
    
    return {
        "entrada": uso.total_input_tokens,
        "saida": uso.total_output_tokens,
        "raciocinio": uso.total_thought_tokens,
        "ferramentas": uso.total_tool_use_tokens,
        "total": uso.total_tokens
    }
    
async def executar():
    iniciado, llm = await iniciar_llm()
    if not iniciado:
        return
    print("Conexão com a IA iniciada com sucesso")
    
    mensagens = [
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "Elabore uma resposta curta para uma saudação. Na sua resposta, você deve se identificar como um sistema especialista dedicado a ensinar sobre investimentos." }]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "O seu nome é InvestBot. Sempre se identifique com esse nome durante saudações." }]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "Olá, tudo bem?" }]
        },
    ]
    
    sucesso, resposta = await obter_resposta(llm, mensagens, None)
    if sucesso:
        print(f"Resposta da IA: {resposta.output_text}")
    else: 
        print("Falha ao obter resposta da IA")

if __name__ == "__main__":
    asyncio.run()