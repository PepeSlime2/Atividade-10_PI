"""
Mostra os últimos registros do MongoDB (iot.sensores) e fica escutando os novos.

Instalar:  pip install pymongo python-dotenv
Rodar:     python consulta_mongo.py        (últimos 10 e fica escutando)
           python consulta_mongo.py 50     (últimos 50 e fica escutando)

O Mongo do servidor é standalone (sem replica set), então change streams
(collection.watch()) não funcionam. A escuta consulta a cada INTERVALO segundos
os documentos com _id mais novo que o último visto.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

INTERVALO = 2                    # segundos entre consultas
JANELA = timedelta(seconds=10)   # o _id usa o relógio de quem insere; olha um pouco para trás


def colecao():
    cliente = MongoClient(os.environ["MONGO_URI"], tz_aware=True,
                          serverSelectionTimeoutMS=10000)
    return cliente[os.environ["MONGO_DB"]][os.environ["MONGO_COLLECTION"]]


def mostrar(doc):
    quando = doc.get("received_at") or doc["_id"].generation_time
    hora = quando.astimezone().strftime("%d/%m %H:%M:%S")
    dados = doc.get("payload_data", doc.get("payload"))

    if not isinstance(dados, dict):              # mensagens fora do padrão Meshtastic
        print(f"[{hora}] (bruto) {dados}")
        return

    remetente = dados.get("sender", "?")
    # A leitura vem como objeto {"t":..,"u":..} ou como texto JSON em {"text": "..."}
    conteudo = dados.get("payload")
    if isinstance(conteudo, dict) and "text" in conteudo:
        conteudo = conteudo["text"]

    inicio = conteudo.find("{") if isinstance(conteudo, str) else -1
    try:
        d = json.loads(conteudo[inicio:]) if inicio >= 0 else conteudo
        temp = d.get("temp", d.get("t"))
        umid = d.get("umid", d.get("u"))
        print(f"[{hora}] {remetente} | Temperatura: {temp:5.1f} °C | "
              f"Umidade: {umid:5.1f} %")
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        print(f"[{hora}] {remetente} | {dados.get('type', '?')}: {conteudo!r}")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    col = colecao()
    print(f"{col.full_name}: {col.estimated_document_count()} registros. Últimos {n}:\n")

    recentes = list(col.find().sort("_id", -1).limit(n))[::-1]
    for doc in recentes:
        mostrar(doc)

    vistos = {d["_id"] for d in recentes}
    ultimo = recentes[-1]["_id"].generation_time if recentes else datetime.now(timezone.utc)
    print(f"\nEscutando novos registros a cada {INTERVALO}s... (Ctrl+C para sair)\n")

    while True:
        time.sleep(INTERVALO)
        desde = ObjectId.from_datetime(ultimo - JANELA)
        try:
            novos = list(col.find({"_id": {"$gte": desde}}).sort("_id", 1))
        except PyMongoError as e:
            print(f"(falha ao consultar, tentando de novo: {e})")
            continue
        for doc in novos:
            if doc["_id"] not in vistos:
                vistos.add(doc["_id"])
                mostrar(doc)
                ultimo = max(ultimo, doc["_id"].generation_time)
        vistos = {i for i in vistos if i >= desde}


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except PyMongoError as e:
        sys.exit(f"Erro no Mongo: {e}")
