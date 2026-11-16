from mcp.client.streamable_http import streamable_http_client
from contextlib import AsyncExitStack
from mcp import ClientSession
from cache import *
from llm import *
import asyncio
import json

NOME_ESPECIALISTA = "InvestBot"
BASE_CONHECIMENTO = "conhecimento/investimentos.json"
MODELO_GEMINI = "gemini-3.5-flash-lite"

CACHE = "cache"
MODELO_CACHE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
NOME_CACHE = "investbot_cache"

URL_FERRAMENTAS = "http://localhost:8000/mcp"

def iniciar_persona_assistente(conhecimento):
    persona = [
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": f"Você é um especialista, perito, em investimentos, chamado {NOME_ESPECIALISTA}"}]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "Se o usuário fizer uma saudação, você deve falar na sua resposta que você é um software, não é um humano, mas que pode ajudar o usuário a entender sobre investimentos"}]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "Se o usuário te perguntar algo que não esteja relacionado com investimentos financeiros, você deve dizer 'não posso responder esta pergunta'"}]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": "Sempre que for necessário realizar alguma análise sobre investimentos, você deve executar as ferramentas disponíveis para obter informações atualizadas e confiáveis"}]
        },
    ]
    
    for mensagem, resposta in conhecimento:
        persona.append({
            "type": "user_input",
            "content": [{ "type": "text", "text": f"Caso o usuário fale ou pergunte '{mensagem}' ou algo parecido, sua resposta deve ser '{resposta}'" }]
        })
    
    return persona

async def carregar_conhecimento(base_conhecimento = BASE_CONHECIMENTO):
    carregado, conhecimento = False, []
    
    try: 
        with open(base_conhecimento, "r", encoding="utf-8") as arquivo:
            conteudo = json.load(arquivo)
            arquivo.close()
            
        for pergunta_resposta in conteudo:
            pergunta = pergunta_resposta["pergunta"]
            resposta = pergunta_resposta["resposta"]
            
            conhecimento.append((pergunta, resposta))
            
        carregado = True
    except Exception as e:
        print(f"Erro ao carregar o conhecimento: {str(e)}")
    
    return carregado, conhecimento
    
async def conectar_ferramentas(contexto, url_ferramentas = URL_FERRAMENTAS): 
    conexao_mcp, ferramentas = None, []
    
    try:
        stream_leitura, stream_escrita = await contexto.enter_async_context(streamable_http_client(url_ferramentas))
        
        conexao_mcp = await contexto.enter_async_context(ClientSession(stream_leitura, stream_escrita))
        
        await conexao_mcp.initialize()
        
        listagem_ferramentas = await conexao_mcp.list_tools()
        for f in listagem_ferramentas.tools:
            ferramentas.append({
                "type": "function",
                "name": f.name,
                "description": f.description,
                "parameters": f.input_schema
            })
    except Exception as e:
        print(f"Erro ao conectar às ferramentas: {str(e)}")
        
    return conexao_mcp, ferramentas
    
def extrair_texto_execucao(resultado):
    if resultado.structured_content:
        return json.dumps(resultado.structured_content, ensure_ascii=False)
    
    conteudo = []
    for c in resultado.content:
        if hasattr(c, "text"):
            conteudo.append(c.text)
        else:
            conteudo.append(str(c))
            
    return "\n".join(conteudo)

async def executar_ferramentas(conexao_mcp, resposta, mensagens):
    ferramentas_para_executar = [passo for passo in resposta.steps if passo.type == "function_call"]
    if ferramentas_para_executar:
        for ferramenta in ferramentas_para_executar:
            print(f"🔧 Executando ferramenta: {ferramenta.name}")
            execucao = await conexao_mcp.call_tool(ferramenta.name, arguments = ferramenta.arguments)
            
            mensagens.append({
                "type": "function_result",
                "name": ferramenta.name,
                "call_id": ferramenta.id,
                "result": [
                    {
                        "type": "text",
                        "text": extrair_texto_execucao(execucao)
                    }
                ]
            })
    
    return ferramentas_para_executar != None and len(ferramentas_para_executar) > 0
    
async def executar_com_contexto(contexto):
    conexao_mcp, ferramentas = await conectar_ferramentas(contexto)
    if not ferramentas:
        print("Não foram encotradas ferramentas")
    else: 
        for ferramenta in ferramentas:
            print(f"Ferramenta encotrada: {ferramenta['name']}, Descrição: {ferramenta['description']}")
            
    iniciado, llm = await iniciar_llm()
    if not iniciado:
        print("Erro ao iniciar o llm")
        return
    
    carregado, conhecimento = await carregar_conhecimento()
    if not carregado:
        print("Erro ao carregar o conhecimento")
        return
    
    iniciado, modelo_cache, colecao_cache = iniciar_cache(MODELO_CACHE, CACHE, NOME_CACHE)
    if not iniciado:
        print("Erro ao iniciar o cache")
        return
    
    persona = iniciar_persona_assistente(conhecimento)
    
    while True:
        mensagem = input("👤: ")
        if mensagem in ["sair", "/s", "exit"]:
            break
        
        persona.append({
            "type": "user_input",
            "content": [{ "type": "text", "text": mensagem }]
        })
        
        encontrada, resposta = buscar_cache(mensagem, modelo_cache, colecao_cache)
        if encontrada: 
            persona.append({ "type": "model_output", "text": resposta })
            
            print(f"🤖: {resposta} [Resposta do cache]")
        else:
            ferramentas_executadas = False
            
            while True:
                sucesso, resposta = await obter_resposta(llm, persona, ferramentas, modelo = MODELO)
                if not sucesso:
                    print("Não foi possível obter uma resposta da IA.")
                    break
                
                persona.extend(resposta.steps)
                
                print(f"🤖 Tokens Consumidos => {get_consumo_tokens(resposta)}")
                
                if not await executar_ferramentas(conexao_mcp, resposta, persona):
                    break
                else:
                    ferramentas_executadas = True
            
            if sucesso:
                texto_resposta = resposta.output_text
                print(f"🤖: {texto_resposta} [Resposta do llm]")
                if not ferramentas_executadas:
                    gravar_cache(mensagem, texto_resposta, modelo_cache, colecao_cache)
                
async def executar():
    contexto = AsyncExitStack()
    try:
        await executar_com_contexto(contexto)
    finally:
        await contexto.aclose()

if __name__ == "__main__":
    asyncio.run(executar())