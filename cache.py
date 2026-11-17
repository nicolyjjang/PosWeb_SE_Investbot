from sentence_transformers import SentenceTransformer
import chromadb

import hashlib
import os

LIMIAR_DISTANCIA_CACHE = 0.20
PALAVRAS_IGNORADAS = {
    "a", "as", "ao", "aos", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "é", "essa", "esse", "esta", "este", "mais", "meu", "minha",
    "não", "na", "nas", "no", "nos", "o", "os", "para", "por", "qual",
    "que", "se", "sua", "seu", "um", "uma", "onde", "sobre",
}

def iniciar_cache(modelo, caminho, nome):
    iniciado, modelo_cache, colecao_cache = False, None, None
    
    try:
        os.environ.setdefault("USE_TF", "0")
        os.environ.setdefault("MLPCONFIGDIR", ".matplotlib") 
        
        modelo_cache = SentenceTransformer(modelo)
        cliente_cache = chromadb.PersistentClient(path=str(caminho))
        colecao_cache = cliente_cache.get_or_create_collection(
            name = nome,
            metadata = { "hnsw:space": "cosine" } 
        )
        
        iniciado = True
    except Exception as e:
        print(f"Cache semântico indisponível: {str(e)}")
        
    return iniciado, modelo_cache, colecao_cache
    
def normalizar_pergunta(pergunta):
    return " ".join(pergunta.lower().strip().split())
    
def gerar_id_cache(pergunta):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    return hashlib.sha256(pergunta_normalizada.encode("utf-8")).hexdigest()
    
def gerar_embedding(modelo_cache, texto):
    return modelo_cache.encode(texto, normalize_embeddings = True).tolist()

def possui_termo_relevante_em_comum(pergunta, pergunta_cache):
    termos_pergunta = {
        termo for termo in normalizar_pergunta(pergunta).split()
        if len(termo) >= 4 and termo not in PALAVRAS_IGNORADAS
    }
    termos_cache = {
        termo for termo in normalizar_pergunta(pergunta_cache).split()
        if len(termo) >= 4 and termo not in PALAVRAS_IGNORADAS
    }
    
    return bool(termos_pergunta & termos_cache)

def buscar_cache(pergunta, modelo_cache, colecao_cache):
    encontrada, resposta = False, None
    
    try:
        embedding = gerar_embedding(modelo_cache, pergunta)
        resultados = colecao_cache.query(
            query_embeddings = [embedding],
            n_results = 1,
            include = ["metadatas", "distances"]
        )
        # novo
        if (
            not resultados["distances"]
            or not resultados["distances"][0]
            or not resultados["metadatas"]
            or not resultados["metadatas"][0]
        ):
            return False, None
        
        distancias = resultados["distances"][0] # distância da pergunta mais próxima no cache
        metadados = resultados["metadatas"][0] # metadados da pergunta mais próxima no cache
        
        distancia = distancias[0]
        metadado = metadados[0]
        pergunta_cache = metadado.get("pergunta", "")
        resposta = metadado.get("resposta")
        
        encontrada = (
            resposta is not None
            and distancia <= LIMIAR_DISTANCIA_CACHE
            and possui_termo_relevante_em_comum(pergunta, pergunta_cache)
        )
    except Exception as e:
        print(f"Ocorreu um erro ao consultar o cache semântico: {str(e)}.")
    
    return encontrada, resposta
    
def gravar_cache(pergunta, resposta, modelo_cache, colecao_cache):
    if modelo_cache is None or colecao_cache is None or not pergunta.strip() or not resposta:
        return
    
    try:
        embedding = gerar_embedding(modelo_cache, pergunta)
        colecao_cache.upsert(
            ids = [gerar_id_cache(pergunta)],
            embeddings = [embedding],
            documents = [pergunta],
            metadatas = [{"pergunta": pergunta, "resposta": resposta}]
        )
    except Exception as e:
        print(f"Ocorreu um erro ao gravar no cache semântico: {str(e)}")