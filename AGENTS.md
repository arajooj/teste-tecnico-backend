# AGENTS.md

## Objetivo do projeto

Este repositório implementa uma API backend em Python para gerenciamento de propostas de crédito em um cenário SaaS multi-tenant. O domínio principal envolve:

- autenticação JWT
- isolamento de dados por tenant
- cadastro e consulta de clientes
- integração com banco mock
- processamento assíncrono
- recebimento de webhooks

Ao trabalhar neste projeto, preserve aderência aos requisitos funcionais descritos no `README.md`, com atenção especial para segurança, multi-tenancy e separação de responsabilidades.

## Stack e execução

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- SQS via LocalStack

Fluxo local esperado:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Arquitetura do projeto

O `README.md` descreve uma separação clássica entre endpoint, service, repository e DTO. Neste repositório, essa mesma intenção está representada com uma arquitetura em camadas:

- `app/modules/*/api`: rotas FastAPI e schemas de entrada/saída
- `app/modules/*/application`: comandos, queries e orquestração de casos de uso
- `app/modules/*/domain`: exceções e regras de domínio
- `app/modules/*/infrastructure`: modelos SQLAlchemy e repositórios
- `app/core`: configuração, segurança, exceções, logging e banco
- `app/shared`: utilitários transversais, como paginação e tipos compartilhados

Ao adicionar novas features, siga essa organização em vez de concentrar lógica na camada HTTP.

## Regras de design

Siga estas diretrizes ao modificar ou criar código:

- Mantenha as rotas enxutas. A camada `api` deve validar entrada, resolver dependências e delegar comportamento.
- Coloque regras de negócio na camada `application` ou `domain`, não em `router`.
- Use `repository` apenas para acesso a dados e consultas persistentes.
- Prefira composição e injeção explícita de dependências a heranças desnecessárias.
- Aplique KISS: escolha a solução mais simples que atenda ao requisito.
- Respeite SRP: cada função, classe ou módulo deve ter um motivo claro para mudar.
- Evite abstrações prematuras. Só generalize quando houver padrão recorrente real.
- Dê nomes explícitos a comandos, queries, schemas e exceções.

## Regras obrigatórias de negócio

- Toda query de dados de negócio deve ser filtrada por `tenant_id`.
- Nenhum endpoint autenticado pode acessar recursos de outro tenant.
- O contexto autenticado deve vir de JWT e expor ao menos `user_id`, `tenant_id` e `role`.
- Senhas nunca devem ser armazenadas em texto puro; use hash consistente com `app/core/security.py`.
- Endpoints protegidos devem depender do contexto autenticado em vez de receber identificadores sensíveis do cliente.
- Webhooks devem localizar propostas por `external_protocol`, atualizar estado e persistir a resposta completa.
- Chamadas ao banco mock não devem bloquear o endpoint síncrono quando o requisito exigir fila/processamento assíncrono.

## Banco e modelagem

- Preserve compatibilidade com Alembic ao alterar modelos SQLAlchemy.
- Novas colunas e constraints relevantes devem ser refletidas em migration.
- Prefira constraints de banco para garantir unicidade por tenant, por exemplo CPF e email quando aplicável.
- Evite `SELECT *` implícito em consultas complexas; carregue apenas o necessário quando fizer sentido.
- Em listagens, mantenha paginação consistente e limites explícitos.

## Padrões de API

- Use schemas Pydantic para entrada e saída na camada `api`.
- Retorne códigos HTTP coerentes com a ação, como `201` para criação e `202` para processamento assíncrono.
- Centralize tratamento de erro via exceções de domínio e handlers em `app/core/exceptions.py`.
- Preserve compatibilidade com os contratos descritos no `README.md` para clientes, propostas, autenticação e webhooks.

## Testes

O projeto deve manter pelo menos a cobertura mínima pedida no desafio, mas prefira ir além quando tocar comportamento crítico.

- Escreva testes unitários para regras de negócio em `application`, `domain` e `repository`.
- Estruture os testes com Arrange, Act, Assert.
- Cada teste deve validar um comportamento específico.
- Cubra caminhos felizes e de erro.
- Use fixtures pequenas e reutilizáveis em `tests/conftest.py`.
- Ao testar autenticação, verifique token válido, token inválido e isolamento entre tenants.
- Ao testar repositórios, valide filtros por `tenant_id`, paginação e restrições de unicidade.
- Ao testar webhooks e fluxos assíncronos, cubra idempotência ou reprocessamento quando o comportamento existir.
- Evite mocks excessivos em regras puras; prefira fakes simples quando possível.

## Performance e escalabilidade

Antes de otimizar, meça. Ainda assim, considere estes cuidados desde o início:

- Evite consultas sem filtro por tenant.
- Evite N+1 queries em listagens e relações.
- Prefira paginação a carregar coleções inteiras.
- Mantenha payloads e respostas enxutos em rotas de listagem.
- Em fluxos assíncronos, mantenha endpoints rápidos e delegue trabalho pesado para fila/worker.
- Em código de repositório, priorize índices e consultas previsíveis sobre micro-otimizações Python.
- Não introduza cache, paralelismo ou abstrações de performance sem necessidade demonstrada.

## Convenções de mudança

- Ao adicionar um novo módulo, espelhe a estrutura por camadas já usada em `clients`, `identity` e `proposals`.
- Ao criar novo endpoint, adicione schemas, caso de uso e repositório correspondentes quando necessário.
- Ao alterar comportamento persistente, revise seed, migrations e testes afetados.
- Ao tocar autenticação, revise impacto em todos os endpoints protegidos.
- Ao tocar regras multi-tenant, trate isso como área crítica e teste explicitamente.

## Checklist para agentes

Antes de concluir uma alteração, confirme:

- o requisito continua aderente ao `README.md`
- a separação entre `api`, `application`, `domain` e `infrastructure` foi mantida
- não houve vazamento entre tenants
- autenticação/autorização continua coerente
- migrations e modelos continuam alinhados
- testes relevantes foram criados ou atualizados
- mudanças de performance em queries ou fluxos assíncronos foram consideradas
