# Consultas no MongoDB

As leituras do DHT11 saem do rádio Meshtastic `!8fa724e8`, passam pelo MQTT e são gravadas no MongoDB do servidor. Este guia mostra como consultar esses dados direto com queries.

```
DHT11 → Mega → Heltec !8fa724e8 → MQTT → serviço no servidor → MongoDB (iot.sensores)
```

## Onde estão os dados

| Item      | Valor                                        |
| --------- | -------------------------------------------- |
| Banco     | `iot`                                        |
| Coleção   | `sensores`                                   |
| Conexão   | variável `MONGO_URI` do arquivo `.env`       |


```
mongodb://root:<SENHA>@<HOST>:27017/?authSource=admin
```

## Como conectar

### MongoDB Compass (interface gráfica)

1. Instale o [MongoDB Compass](https://www.mongodb.com/try/download/compass).
2. Clique em **Add new connection**, cole a string de conexão e clique em **Connect**.
3. Abra `iot` → `sensores`.
   - Os filtros (o primeiro argumento do `find`) vão no campo **Filter**.
   - Projeção, ordenação e limite ficam em **Options**.
   - As agregações vão na aba **Aggregations**.

### mongosh (terminal)

1. Instale o [MongoDB Shell](https://www.mongodb.com/try/download/shell).
2. Conecte e selecione o banco:

```bash
mongosh "mongodb://root:<SENHA>@<HOST>:27017/?authSource=admin"
```
```js
use iot
```

Todos os exemplos abaixo estão na sintaxe do mongosh.

## Formato de um documento

Exemplo real de uma leitura (alguns campos omitidos):

```js
{
  _id: ObjectId("6ada2db7e61373062a68bf1a"),
  topic: "sensores/tempUmid/2/json/mqtt_teste/!8fa724e8",
  payload: "{\"channel\":0, ...}",      // mensagem MQTT original, como texto
  payload_data: {                         // a mesma mensagem já convertida em objeto
    sender: "!8fa724e8",                  // rádio que enviou
    type: "text",
    payload: { t: 21, u: 15 },            // t = temperatura (°C), u = umidade (%)
    timestamp: 1792683446                 // relógio do rádio: às vezes vem 0, não use
  },
  received_at: ISODate("2026-10-23T10:51:10.043Z"),   // quando chegou no servidor
  data: ISODate("2026-10-23T10:51:10.043Z")           // igual ao received_at
}
```

**Atenção:**

- **As datas estão em UTC.** Horário de Brasília = UTC − 3. Por exemplo, 07:00 em Brasília é `10:00Z` no banco.
- **Nem todo documento é uma leitura.** Alguns não têm `payload_data`, outros chegam com `payload: { text: "" }`. Para pegar só leituras, filtre por `"payload_data.payload.t": { $exists: true }`.
- **Para saber quando a leitura chegou**, use `received_at`, não `payload_data.timestamp`.

## Consultas com `find`

Formato geral:

```js
db.sensores.find(<filtro>, <projeção>).sort(<ordem>).limit(<quantidade>)
```

### Contar documentos

```js
db.sensores.countDocuments()                                       // todos
db.sensores.countDocuments({ "payload_data.sender": "!8fa724e8" }) // só do rádio
```

### Últimas 10 leituras do rádio

```js
db.sensores.find(
  { "payload_data.sender": "!8fa724e8", "payload_data.payload.t": { $exists: true } },
  { _id: 0, received_at: 1, temp: "$payload_data.payload.t", umid: "$payload_data.payload.u" }
).sort({ _id: -1 }).limit(10)
```

- A projeção (segundo argumento) escolhe os campos que aparecem e renomeia os campos de dentro do documento para `temp` e `umid`.
- `sort({ _id: -1 })` coloca os mais novos primeiro. O `_id` tem índice, então essa ordenação é rápida.
- Para ver só a última leitura, troque para `.limit(1)`.

### Leituras de um dia

Para o dia 23/10 no horário de Brasília (de 00:00 a 23:59, ou seja, de 03:00Z do dia 23 até 03:00Z do dia 24):

```js
db.sensores.find({
  "payload_data.sender": "!8fa724e8",
  received_at: { $gte: ISODate("2026-10-23T03:00:00Z"), $lt: ISODate("2026-10-24T03:00:00Z") }
})
```

### Leituras da última hora

Só funciona no mongosh, porque usa JavaScript:

```js
db.sensores.find({
  "payload_data.sender": "!8fa724e8",
  received_at: { $gte: new Date(Date.now() - 60 * 60 * 1000) }
})
```

### Filtrar por valor

```js
// temperatura maior ou igual a 25 °C
db.sensores.find({ "payload_data.payload.t": { $gte: 25 } })

// temperatura entre 20 e 25 °C
db.sensores.find({ "payload_data.payload.t": { $gte: 20, $lte: 25 } })

// umidade abaixo de 20 %
db.sensores.find({ "payload_data.payload.u": { $lt: 20 } })
```

### Operadores mais usados

| Operador  | Significado        | Exemplo                                  |
| --------- | ------------------ | ---------------------------------------- |
| `$eq`     | igual              | `{ t: { $eq: 22 } }` ou só `{ t: 22 }`   |
| `$ne`     | diferente          | `{ t: { $ne: 0 } }`                      |
| `$gt`     | maior que          | `{ t: { $gt: 25 } }`                     |
| `$gte`    | maior ou igual     | `{ t: { $gte: 25 } }`                    |
| `$lt`     | menor que          | `{ u: { $lt: 20 } }`                     |
| `$lte`    | menor ou igual     | `{ u: { $lte: 20 } }`                    |
| `$in`     | está na lista      | `{ t: { $in: [21, 22] } }`               |
| `$exists` | campo existe       | `{ t: { $exists: true } }`               |

Na tabela, `t` e `u` estão abreviados. Na consulta de verdade, use o caminho completo: `"payload_data.payload.t"` e `"payload_data.payload.u"`.

## Agregações: médias, mínimos e máximos

O `aggregate` recebe uma lista de etapas (*pipeline*). Cada etapa recebe o resultado da anterior.

### Média, mínimo e máximo por hora

```js
db.sensores.aggregate([
  // 1. só leituras do rádio
  { $match: { "payload_data.sender": "!8fa724e8", "payload_data.payload.t": { $exists: true } } },

  // 2. agrupa por hora, no horário de Brasília
  { $group: {
      _id: { $dateToString: { date: "$received_at", format: "%Y-%m-%d %H:00", timezone: "America/Sao_Paulo" } },
      media_temp: { $avg: "$payload_data.payload.t" },
      min_temp:   { $min: "$payload_data.payload.t" },
      max_temp:   { $max: "$payload_data.payload.t" },
      media_umid: { $avg: "$payload_data.payload.u" },
      leituras:   { $sum: 1 }
  } },

  // 3. horas mais recentes primeiro
  { $sort: { _id: -1 } }
])
```

Resultado (médias arredondadas aqui; o banco devolve mais casas decimais):

```js
{ _id: "2026-10-23 07:00", media_temp: 20.18, min_temp: 19, max_temp: 22, media_umid: 15.9, leituras: 323 }
```

Para agrupar **por dia**, troque o `format` para `"%Y-%m-%d"`.

### Mostrar as datas no horário de Brasília

```js
db.sensores.aggregate([
  { $match: { "payload_data.sender": "!8fa724e8", "payload_data.payload.t": { $exists: true } } },
  { $sort: { _id: -1 } },
  { $limit: 10 },
  { $project: {
      _id: 0,
      hora: { $dateToString: { date: "$received_at", format: "%d/%m/%Y %H:%M:%S", timezone: "America/Sao_Paulo" } },
      temp: "$payload_data.payload.t",
      umid: "$payload_data.payload.u"
  } }
])
```

### Quantos registros cada origem enviou

```js
db.sensores.aggregate([
  { $group: { _id: "$payload_data.sender", total: { $sum: 1 } } },
  { $sort: { total: -1 } }
])
```

Um `_id: null` no resultado são os documentos sem `payload_data`.

## Usando as mesmas queries no Python

Com o `pymongo`, os filtros e pipelines são os mesmos, escritos como dicionários Python:

```python
import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
col = MongoClient(os.environ["MONGO_URI"])["iot"]["sensores"]

filtro = {"payload_data.sender": "!8fa724e8", "payload_data.payload.t": {"$exists": True}}
for doc in col.find(filtro).sort("_id", -1).limit(10):
    print(doc["received_at"], doc["payload_data"]["payload"])
```

Diferenças em relação ao mongosh:

- Operadores e nomes de campo vão entre aspas: `"$gte"`.
- `true` vira `True`.
- `ISODate("...")` vira `datetime(2026, 10, 23, 3, tzinfo=timezone.utc)`.
- Agregações rodam com `col.aggregate([...])`, usando o mesmo pipeline.

## Cuidados

- **O banco é compartilhado pelo grupo.** Use só comandos de leitura: `find`, `countDocuments` e `aggregate`. Não rode `insertOne`, `updateMany`, `deleteMany` ou `drop` sem combinar antes, porque não tem como desfazer.
- **Ao explorar, use sempre `limit()`** para não trazer a coleção inteira.
- **Não dá para receber os dados em tempo real com `watch()`.** O servidor é standalone, sem replica set, e por isso change streams não funcionam. Para acompanhar ao vivo, repita a consulta de tempos em tempos, filtrando por `_id` maior que o último já visto.
