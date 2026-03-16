# Teste Técnico Backend

API de propostas de crédito em `FastAPI` com autenticação JWT, multi-tenancy, persistência em PostgreSQL, fila `SQS` no `LocalStack`, integração com banco mock e processamento de webhook.

O enunciado original do teste foi preservado em `DESAFIO.md`.

## Contexto da entrega

Minha stack principal no dia a dia é mais orientada a `Node.js`, mas para este desafio implementei a solução em `Python` seguindo os requisitos do enunciado.

Também usei IA como apoio para acelerar documentação, revisão de texto e organização de partes da entrega. As decisões de implementação, a aplicação das regras de negócio e os ajustes na solução foram conduzidos e validados durante o desenvolvimento, inclusive na forma de organizar módulos, responsabilidades, fluxo assíncrono e apoio por abordagens agentic, roles e skills.

## Stack

- `Python 3.11+`
- `FastAPI`
- `SQLAlchemy 2.x`
- `Alembic`
- `PostgreSQL`
- `LocalStack` com `SQS` e `Lambda`
- `pytest`, `pytest-cov` e `ruff`

## Estrutura

- `app/core`: config, banco, segurança, logging e exceções
- `app/modules/identity`: login e autenticação
- `app/modules/clients`: CRUD de clientes isolado por tenant
- `app/modules/proposals`: simulação, submissão e leitura de propostas
- `app/modules/webhooks`: processamento do callback do banco
- `app/workers`: processamento do job da fila
- `app/lambdas`: handler da Lambda conectada ao `SQS`
- `scripts`: seed e empacotamento da Lambda

## Pré-requisitos

- `Python 3.11+`
- `Docker`
- `Docker Compose`
- Docker com suporte a `host.docker.internal` / `host-gateway` para o callback do `mock-bank`

## Variáveis de ambiente

O projeto lê `.env`. Se quiser customizar a execução local, copie `.env.example` para `.env`.

Valores padrão:

- `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/teste_tecnico`
- `AWS_ENDPOINT_URL=http://localhost:4566`
- `SQS_QUEUE_NAME=proposal-processing-queue`
- `MOCK_BANK_BASE_URL=http://localhost:8001`
- `WEBHOOK_CALLBACK_BASE_URL=http://host.docker.internal:8000`
- `JWT_SECRET_KEY=change-me`

## Subindo o ambiente local

### 1. Ambiente virtual

Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Infraestrutura

```powershell
docker compose up -d
```

Isso sobe:

- `postgres` na porta `5432`
- `localstack` na porta `4566`
- `mock-bank` na porta `8001`
- `lambda-builder`, que gera o pacote da Lambda usado pelo `LocalStack`

### 3. Migrations e seed

Windows, Linux e macOS:

```powershell
alembic upgrade head
python -m scripts.seed
```

Credenciais seeded:

- Tenant Alpha: `11111111-1111-1111-1111-111111111111` + `alpha@example.com` / `123456`
- Tenant Beta: `22222222-2222-2222-2222-222222222222` + `beta@example.com` / `123456`

### 4. API

Windows, Linux e macOS:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Observação: o framework da API é `FastAPI`. O `uvicorn` é o servidor ASGI usado para executar a aplicação `FastAPI` localmente.

Documentação interativa:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Healthcheck: [http://localhost:8000/health](http://localhost:8000/health)

## Fluxo assíncrono

O processamento do banco não acontece diretamente no endpoint HTTP.

Para ficar mais próximo de produção, a solução não ficou restrita a um worker simples rodando isoladamente. A escolha foi usar `LocalStack + SQS + Lambda`, simulando com mais fidelidade o fluxo assíncrono que seria esperado em um ambiente real.

Fluxo implementado:

1. `POST /api/proposals/simulate` cria a proposta com status `pending`, gera token de callback exclusivo e persiste um job assíncrono.
2. O publish para o `SQS` usa esse job persistido. Se falhar, o erro fica rastreado no banco e o redespacho é tentado no startup seguinte da API.
3. A Lambda registrada no `LocalStack` consome a fila e processa o job.
4. A lógica de processamento executada pela Lambda chama o banco mock, grava `simulation_protocol` ou `inclusion_protocol` e mantém `external_protocol` como protocolo ativo atual.
5. O banco mock envia `POST /api/webhooks/bank-callback?callback_token=...`.
6. O webhook valida token, fase esperada, protocolo e idempotência antes de atualizar status e `bank_response`.
7. `POST /api/proposals/{id}/submit` reaproveita o mesmo fluxo assíncrono para inclusão da proposta, com um novo token de callback.

Observação: neste projeto não há um comando separado para subir um worker manual em polling. O caminho principal de consumo assíncrono é `SQS -> Lambda no LocalStack`.

## Endpoints principais

### Auth

- `POST /api/auth/login`

### Clients

- `POST /api/clients`
- `GET /api/clients`
- `GET /api/clients/{id}`
- `PUT /api/clients/{id}`

### Proposals

- `POST /api/proposals/simulate`
- `POST /api/proposals/{id}/submit`
- `GET /api/proposals`
- `GET /api/proposals/{id}`

### Webhooks

- `POST /api/webhooks/bank-callback`

## Exemplo rápido de uso

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"11111111-1111-1111-1111-111111111111\",\"email\":\"alpha@example.com\",\"password\":\"123456\"}"
```

### Criar cliente

Substitua `TOKEN` pelo JWT retornado no login.

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Maria Silva\",\"cpf\":\"12345678901\",\"birth_date\":\"1990-01-01\",\"phone\":\"11999999999\"}"
```

## Testes e qualidade

### Rodar lint

Windows, Linux e macOS:

```powershell
python -m ruff check .
```

### Rodar testes com cobertura

Windows, Linux e macOS:

```powershell
python -m pytest --cov --cov-report=term-missing --cov-report=xml
```

### Rodar smoke E2E local

Esse smoke usa a infraestrutura real do desafio (`docker compose`, `LocalStack`, `mock-bank` e a API local) e valida o fluxo `login -> cliente -> simulação -> webhook -> submissão -> webhook`.

Pré-requisitos:

- infraestrutura levantada com `docker compose up -d`
- migrations aplicadas e seed executado
- API rodando localmente na porta `8000`

Windows:

```powershell
$env:RUN_DOCKER_E2E=1
python -m pytest tests/integration/test_smoke_e2e.py -m integration
```

Linux / macOS:

```bash
RUN_DOCKER_E2E=1 python -m pytest tests/integration/test_smoke_e2e.py -m integration
```

Essa meta de cobertura foi validada localmente durante a entrega.

Meta adotada nesta entrega:

- `100%` de cobertura dos testes unitários no escopo medido pela configuração do projeto
- cobertura concentrada em autenticação, regras de aplicação, repositórios, webhook e fluxo assíncrono

## Dockerfile da API

Existe um `Dockerfile` na raiz como diferencial opcional.

Build:

```bash
docker build -t teste-tecnico-api .
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file .env teste-tecnico-api
```

## Lambda local

O pacote da Lambda é gerado automaticamente no `docker compose up` pelo serviço `lambda-builder`.

Essa escolha foi intencional para manter o processamento assíncrono mais próximo de produção, usando `Lambda` conectada ao `SQS` no `LocalStack`, em vez de depender somente de um worker simplificado fora desse fluxo.

Se quiser regenerar manualmente:

Windows:

```powershell
.\scripts\build_lambda_package.ps1
```

Linux / macOS:

```bash
chmod +x ./scripts/build_lambda_package.sh
./scripts/build_lambda_package.sh
```

## Troubleshooting

- Se a API não conectar no banco, confirme se `postgres` está saudável e rode `alembic upgrade head`.
- Se o webhook não atualizar a proposta, verifique se a API está disponível em `WEBHOOK_CALLBACK_BASE_URL` e se a Lambda foi criada com a mesma URL.
- Se a fila não processar, confira se o `docker compose up -d` gerou a Lambda e as filas no `LocalStack`.
- Se mudar dependências usadas pela Lambda, regenere o pacote com `.\scripts\build_lambda_package.ps1`.
- Em Linux, confirme que a sua versão do Docker suporta `host-gateway`, já que o `mock-bank` precisa alcançar a API no host.
