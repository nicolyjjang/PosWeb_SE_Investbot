from chat import *
from llm import * 
import asyncio

MODELO_ASSISTENTE = "gemini-3.5-flash-lite"
MODELO_JULGAMENTO = "gemini-3.1-flash-lite"

CASOS_INADEQUADOS = [
    {
        "pergunta": "Qual é a opção mais indicada para formar minha reserva de emergência?",
        "resposta": "A opção mais indicada é comprar ações da Petrobras (PETR4) e fazer operações de Day Trade, pois oferecem risco zero e liquidez garantida pelo FGC."
    },
    {
        "pergunta": "Como funciona a isenção de imposto de renda na venda de ações?",
        "resposta": "A venda de ações é totalemente isenta de imposto de renda até o limite de R$ 5.000.000, desde que você a taxa em barras de ouro."
    }
]

async def iniciar_persona_julgamento():
    persona = [
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": f"Você é um especialista, perito, em investimento." }]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": (
                "Considere INADEQUADA qualquer resposta que: "
                "(a) contenha informação factualmente errada sobre investimentos; "
                "(b) recomende ativo incompatível com o objetivo descrito na pergunta; "
                "(c) invente isenções, alíquotas ou garantias; "
                "(d) misture conceitos de forma confusa. "
            ) }]
        },
        {
            "type": "user_input",
            "content": [{ "type": "text", "text": (
                "Responda EXATAMENTE no formato: "
                "'VEREDITO: ADEQUADA' ou 'VEREDITO: INADEQUADA', "
                "seguido de uma justificativa de uma linha."
            ) }]
        }
    ]
    
    return persona
    
async def testar_alucinações(llm, julgador):
    for alucinacao in CASOS_INADEQUADOS:
        pergunta = alucinacao["pergunta"]
        resposta = alucinacao["resposta"]
        
        print(f"Julgando a alucinação: '{resposta}' da pergunta '{pergunta}'")
        sucesso, julgamento = await obter_resposta(llm, julgador + [
            {
                "type": "user_input",
                "content": [{ "type": "text", "text": f"Pergunta: '{pergunta}', resposta: '{resposta}'" }]
            }
            ], None, modelo = MODELO_JULGAMENTO)
        assert(sucesso == True)
        texto_julgamento = julgamento.output_text
        assert("VEREDITO: INADEQUADA" in texto_julgamento)
        justificativa = texto_julgamento.replace("VEREDITO: INADEQUADA", "", 1).strip(" .:\n")
        print(f"👎👎 A resposta foi julgada INADEQUADA para a pergunta 👎👎\n{justificativa}")
    
async def testar_assistente(llm, conhecimento, assistente, julgador):
    for pergunta, _ in conhecimento:
        sucesso, resposta = await obter_resposta(llm, assistente + [
            {
                "type": "user_input",
                "content": [{ "type": "text", "text": f"{pergunta}" }]
            }
        ], None, modelo = MODELO_ASSISTENTE)
        assert(sucesso == True)
        
        resposta = resposta.output_text
        
        print(f"Julgando a resposta '{resposta}' para a pergunta '{pergunta}'")
        sucesso, julgamento = await obter_resposta(llm, julgador + [
            {
                "type": "user_input",
                "content": [{ "type": "text", "text": f"Pergunta: '{pergunta}', resposta: '{resposta}'" }]
            }
        ], None, modelo = MODELO_JULGAMENTO)    
        assert(sucesso == True)
        texto_julgamento = julgamento.output_text
        assert("VEREDITO: ADEQUADA" in texto_julgamento)
        justificativa = texto_julgamento.replace("VEREDITO: ADEQUADA", "", 1).strip(" .:\n")
        print(f"👍👍 A resposta foi julgada ADEQUADA para a pergunta 👍👍\n{justificativa}")
        
async def executar():
    iniciado, llm = await iniciar_llm()
    assert(iniciado == True)
    
    carregado, conhecimento = await carregar_conhecimento(base_conhecimento = "conhecimento/investimentos_menor.json")
    assert(carregado == True and len(conhecimento) > 0)
    
    julgador = await iniciar_persona_julgamento()
    await testar_alucinações(llm, julgador)
    
    assistente = iniciar_persona_assistente(conhecimento)
    await testar_assistente(llm, conhecimento, assistente, julgador)

if __name__ == "__main__":
    asyncio.run(executar())