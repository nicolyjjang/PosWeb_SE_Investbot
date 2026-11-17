from mcp.server.mcpserver import MCPServer
from collections import defaultdict
import unicodedata
import json
import os

CAMPOS_OBRIGATORIOS = [
    "nome", "ticker", "categoria",
    "sinonimos", "perfil_indicado",
    "tributacao", "rentabilidade",
    "risco", "liquidez", "observacao"
]
PALAVRAS_IGNORADAS_BUSCA = {
    "a", "as", "ao", "aos", "como", "da", "das", "de", "do", "dos",
    "e", "é", "em", "o", "os", "para", "por", "qual", "que", "um", "uma",
}

BASE_INVESTIMENTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conhecimento", "dados_investimentos.json")
NOME = "base_investimentos"
mcp = MCPServer(NOME, "uma base de consulta de ativos financeiros e investimentos da B3.")

def normalizar_texto(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.lower().replace("-", " ").split()) 

def carregar_investimentos(caminho=BASE_INVESTIMENTOS):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
        
        for ativo in dados:
            for campo in CAMPOS_OBRIGATORIOS:
                if campo not in ativo:
                    raise ValueError(f"Ativo {ativo.get('ticker', '?')} sem o campo obrigatório: '{campo}'")
        return dados
    
INVESTIMENTOS = carregar_investimentos()

# pré-processa os dados criando um indice de busca para facilitar a pesquisa de ativos
INDICE_BUSCA = []
for ativo in INVESTIMENTOS:
    termos = [ativo["nome"], ativo["ticker"], ativo["categoria"], *ativo["sinonimos"]]
    INDICE_BUSCA.append((ativo, [normalizar_texto(termo) for termo in termos if termo]))

def buscar_ativo(termo):
    """
    Busca um ativo por nome, ticker, categoria ou sinônimo e retorna o dict do ativo ou None se não encontrar.
    
    Estratégia:
        1. Match exato: busca pelo termo normalizado
        2. Match parcial: busca por pelo menos uma palavra do termo normalizado (por exemplo: "petrobras" em "ações da petrobras") 
        3. Match por substring: busca pelo termo normalizado como substring (mínimo de 4 caracteres, por exemplo: "petro" em "ações da petrobras")
    """
    
    termo_normalizado = normalizar_texto(termo)
    if not termo_normalizado:
        return None
    
    # Match exato
    for ativo, termos in INDICE_BUSCA:
        if termo_normalizado in termos:
            return ativo
    
    # Match parcial
    palavras_buscadas = {
        palavra for palavra in termo_normalizado.split()
        if palavra not in PALAVRAS_IGNORADAS_BUSCA
    }
    for ativo, termos in INDICE_BUSCA:
        for termo_cadastrado in termos:
            if palavras_buscadas and palavras_buscadas <= set(termo_cadastrado.split()):
                return ativo
    
    # Match por Substring
    if len(termo_normalizado) >= 4:
        for ativo, termos in INDICE_BUSCA:
            if any(termo_normalizado in termon for termon in termos):
                return ativo
    
    return None
    
def ativo_nao_encontrado(termo):
    return (
        f"O ativo '{termo}' não foi encontrado na base de investimentos. \nUse a ferramenta `listar_ativos` para ver os ativos disponíveis"
    )

@mcp.tool(
    name="listar_ativos",
    title="Lista os ativos e investimentos disponiveis",
    description="Lista os ativos de renda fixa, renda variáveis (ações), fundos de investimento (FIIs), previdência privada disponiveis na base, agrupados por categoria"
)
def listar_ativos():
    por_categoria = defaultdict(list) # agrupa os ativos em uma lista por categoria
    for ativo in INVESTIMENTOS:
        por_categoria[ativo["categoria"]].append(
            f"{ativo['nome']} ({ativo['ticker']})"
        )
    
    blocos = [
        f"{categoria}:\n - " + "\n - ".join(sorted(items))
        for categoria, items in sorted(por_categoria.items())
    ]
    return "\n\n".join(blocos)

@mcp.tool(
    name="consultar_tributacao",
    title="Consulta a tributacao de um ativo ou investimento",
    description="Informa as regras do Imposto de Renda (IR), alíquotas e isenções tributárias de um ativo."
)
def consultar_tributacao(ativo_ou_ticker: str):
    ativo = buscar_ativo(ativo_ou_ticker)
    if ativo is None:
        return ativo_nao_encontrado(ativo_ou_ticker)
    
    tributacao = ativo["tributacao"]
    return (
        f"{ativo['nome']} ({ativo['ticker']})\n"
        f"Tabela: {tributacao['tabela']}\n"
        f"Alíquota: {tributacao['aliquota']}\n"
        f"Isenção: {tributacao['isencao']}"
    )
    
@mcp.tool(
    name="consultar_rentabilidade_risco",
    title="Consulta de rentabilidade, risco e liquidez de um ativo ou investimento",
    description="Informa a rentabilidade esperada, nível de risco, liquidez e perfil recomendado de um ativo."
)
def consultar_rentabilidade_risco(ativo_ou_ticker: str):
    ativo = buscar_ativo(ativo_ou_ticker)
    if ativo is None:
        return ativo_nao_encontrado(ativo_ou_ticker)
    
    rentabilidade = ativo["rentabilidade"]
    risco = ativo["risco"]
    liquidez = ativo["liquidez"]
    perfil = ativo["perfil_indicado"]
    observacao = ativo["observacao"]
    
    return (
        f"{ativo['nome']} ({ativo['ticker']})\n"
        f"Perfil recomendado: {perfil}"
        f"Rentabilidade esperada: {rentabilidade}\n"
        f"Nível de risco: {risco}\n"
        f"Liquidez: {liquidez}\n"
        f"Observação: {observacao}"
    )

@mcp.tool(
    name="consultar_ativo",
    title="Retorna todas as informacoes de um ativo ou investimento",
    description="Retorna uma visão completa de um ativo, incluindo categoria, perfil, rentabilidade, risco, liquidez, tributação e observação"
)
def consultar_ativo(ativo_ou_ticker: str):
    ativo = buscar_ativo(ativo_ou_ticker)
    if ativo is None:
        return ativo_nao_encontrado(ativo_ou_ticker)
    
    tributacao = ativo["tributacao"]
    rentabilidade = ativo["rentabilidade"]
    risco = ativo["risco"]
    liquidez = ativo["liquidez"]
    perfil = ativo["perfil_indicado"]
    observacao = ativo["observacao"]
    
    return (
        f"{ativo['nome']} ({ativo['ticker']})\n"
        f"Categoria: {ativo['categoria']}\n"
        f"Perfil recomendado: {perfil}\n"
        f"Rentabilidade esperada: {rentabilidade}\n"
        f"Nível de risco: {risco}\n"
        f"Liquidez: {liquidez}\n"
        f"Tabela de tributação: {tributacao['tabela']}\n"
        f"Alíquota de tributação: {tributacao['aliquota']}\n"
        f"Isenção de tributação: {tributacao['isencao']}\n"
        f"Observação: {observacao}"
    )

@mcp.tool(
    name="filtrar_por_perfil",
    title="Filtra ativos e investimentos por perfil de investidor",
    description="Lista os ativos adequados para um determinado perfil de investidor (Conservador, Moderado ou Arrojado)"
)
def filtrar_por_perfil(perfil: str):
    perfil_normalizado = normalizar_texto(perfil)
    if not perfil_normalizado:
        return "Informe um perfil de investidor válido (Conservador, Moderado ou Arrojado)"
    
    encontrados = []
    for ativo in INVESTIMENTOS:
        if normalizar_texto(ativo["perfil_indicado"]) == perfil_normalizado:
            encontrados.append(f"{ativo['nome']} ({ativo['ticker']})")
    
    if not encontrados:
        return "Nenhum ativo encontrado para o perfil '{perfil}'. \n Perfis disponíveis na base: Conservador, Moderado, Arrojado"
    
    return "Ativos adequados ao perfil '{perfil}':\n - " + "\n - ".join(encontrados)

if __name__ == "__main__":
    mcp.run(
        transport = "streamable-http",
        host = "0.0.0.0",
        streamable_http_path = "/mcp"
    )