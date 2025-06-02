import os
from pymilvus import MilvusClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MILVUS_URI")
token = os.getenv("MILVUS_TOKEN")

print("=== Informações de Conexão ===")
print(f"URI: {uri}")
print(f"Token (primeiros 10 caracteres): {token[:10]}..." if token else "Token não encontrado")
print("=============================")

try:
    # Usando MilvusClient para conexão com Zilliz Cloud
    client = MilvusClient(
        uri=uri,
        token=token,
        db_name="default"
    )
    print("Conectado ao Milvus Cloud com sucesso!")
except Exception as e:
    print(f"Erro ao conectar ao Milvus Cloud: {str(e)}")
    print("\nSugestões de verificação:")
    print("1. Verifique se a URI está no formato correto: https://<cluster-id>.api.gcp-us-west1.zillizcloud.com")
    print("2. Confirme se o token é o token de API gerado no painel do Zilliz Cloud")
    print("3. Verifique se o cluster está ativo no painel do Zilliz Cloud")
    print("4. Confirme se não há restrições de IP no cluster") 