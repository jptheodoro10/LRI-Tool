# Modulos de IA e Camadas do Backend

## Visao Geral

O backend atual separa bem tres preocupacoes:

- exposicao HTTP
- regras de negocio
- persistencia

Em cima disso, os modulos de IA entram como uma capacidade transversal: eles usam dados do canvas, montam contexto, chamam o provedor LLM e devolvem uma saida util para a interface.

## Modulos de IA

Hoje existem tres blocos principais ligados a IA.

### 1. Cliente LLM

Arquivo principal:

- `backend/app/services/llm_client.py`

Responsabilidade:

- esconder o provedor real atras de uma interface unica: `generate(prompt) -> str`

Implementacoes atuais:

- `MockLLMClient`
- `OpenAILLMClient`

Vantagens:

- desacopla o resto do backend do SDK do provedor
- facilita testes locais e execucao offline com respostas deterministicamente geradas
- reduz o custo de trocar de provedor depois
- centraliza timeout, modelo e leitura da resposta textual

### 2. Modulo de recomendacoes da Fase 1

Arquivo principal:

- `backend/app/services/ai_service.py`

Responsabilidade:

- gerar recomendacoes para campos vazios do canvas com base nos campos ja preenchidos

Regras atuais:

- funciona apenas na fase 1
- exige pelo menos um campo preenchido
- gera recomendacao apenas para campos vazios
- persiste sugestoes em `ai_suggestions`
- usa `context_hash` para evitar recomputacao desnecessaria

Fluxo atual:

1. O frontend identifica os campos vazios.
2. Ao clicar no botao, ele dispara uma chamada por campo vazio.
3. O backend monta o contexto do canvas.
4. O servico gera a recomendacao e salva status, contexto e saida.
5. Cada resposta volta separadamente e aparece progressivamente abaixo do canvas correspondente.

Vantagens:

- feedback rapido para o usuario
- melhor sensacao de performance, porque o primeiro resultado nao espera o lote inteiro
- persistencia das sugestoes para recarregamento posterior
- cache por contexto, evitando chamadas repetidas quando nada mudou
- isolamento do prompt e das regras de negocio num unico servico

### 3. Modulo de overview da Fase 3

Arquivo principal:

- `backend/app/services/ai_service.py`

Responsabilidade:

- analisar criticamente cada canvas da fase 3, em vez de sugerir texto para preencher

Regras atuais:

- funciona apenas na fase 3
- exige todos os campos preenchidos
- gera uma analise por canvas
- nao persiste o resultado no banco
- a resposta vive apenas no estado da interface

Fluxo atual:

1. O frontend garante que o board esta completo.
2. Ele faz uma chamada por campo para o endpoint de overview.
3. Cada retorno e mostrado conforme chega.

Vantagens:

- separa bem dois usos diferentes da IA: completar texto e revisar texto
- evita poluir o banco com saidas temporarias
- melhora a UX com respostas progressivas
- mantem a fase 3 focada em reflexao critica, nao em auto-preenchimento

## Diferenca entre os dois modulos de IA de produto

### Fase 1

- objetivo: preencher lacunas
- saida: sugestao pronta para ajudar a escrever
- persistencia: sim
- estado: recommendation

### Fase 3

- objetivo: revisar e refinar
- saida: overview + suggestions sobre o texto atual
- persistencia: nao
- estado: overview temporario em tela

## Camadas do Backend

O backend segue uma cadeia simples e clara:

- Router
- Service
- Repository
- Model/Database

### 1. Router

Arquivos principais:

- `backend/app/routers/runs.py`
- `backend/app/routers/canvas.py`
- `backend/app/routers/invites.py`
- `backend/app/routers/scores.py`
- `backend/app/routers/auth.py`

Responsabilidade:

- receber a requisicao HTTP
- validar acesso
- converter erros de negocio em status HTTP
- devolver o contrato de resposta

Vantagens:

- reduz logica de negocio nas rotas
- facilita entender a API publica
- deixa autorizacao e contrato HTTP em um lugar previsivel

### 2. Service

Arquivos principais:

- `backend/app/services/run_service.py`
- `backend/app/services/canvas_service.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/invite_service.py`
- `backend/app/services/score_service.py`
- `backend/app/services/pdf_service.py`

Responsabilidade:

- concentrar regras de negocio
- orquestrar repositorios
- montar contexto para IA
- aplicar regras de fase, ciclo, decisao e avaliacao

Vantagens:

- camada ideal para testes de regra
- evita duplicacao entre rotas
- torna o comportamento do sistema mais previsivel

### 3. Repository

Arquivos principais:

- `backend/app/repositories/run_repository.py`
- `backend/app/repositories/canvas_repository.py`
- `backend/app/repositories/ai_suggestion_repository.py`
- `backend/app/repositories/invite_repository.py`
- `backend/app/repositories/participant_repository.py`
- `backend/app/repositories/score_repository.py`

Responsabilidade:

- encapsular acesso ao banco
- executar consultas, updates, inserts e deletes

Vantagens:

- separa SQLAlchemy da regra de negocio
- simplifica refatoracoes futuras
- melhora legibilidade e reuso de consultas

### 4. Model e banco

Arquivos principais:

- `backend/app/models/run.py`
- `backend/app/models/canvas.py`
- `backend/app/models/score.py`
- outros modelos de apoio

Responsabilidade:

- definir a estrutura persistida
- impor constraints importantes, como unicidade por ciclo

Vantagens:

- reforca consistencia no nivel do banco
- reduz chances de duplicidade indevida
- deixa claro o contrato de dados do sistema

## Como a IA atravessa essas camadas

Um fluxo tipico de IA passa assim:

1. `ProjectPhasePage.jsx` chama um endpoint.
2. O router de `canvas.py` valida acesso.
3. `AISuggestionService` monta o contexto e escolhe o prompt.
4. `LLMClient` chama mock ou OpenAI.
5. O resultado volta para o service.
6. Se for fase 1, o resultado e persistido via `AISuggestionRepository`.
7. A resposta HTTP volta para o frontend.
8. O frontend renderiza o resultado abaixo do canvas correspondente.

## Vantagens arquiteturais do estado atual

- Boa separacao de responsabilidades.
- IA plugavel por provedor.
- Mock deterministico para teste e demo local.
- Fluxo progressivo na UI para fase 1 e fase 3.
- Persistencia apenas onde faz sentido de produto.
- Reuso do mesmo `ai_service.py` para dois comportamentos de IA diferentes.
- Regras de ciclo e fase ficam no backend, nao espalhadas pelo frontend.

## Limitacoes atuais

- O worker ainda nao executa jobs reais de IA; ele esta reservado para extensao futura.
- As chamadas de IA sao sincronas do ponto de vista do endpoint.
- Participantes nao editam diretamente os canvases; a colaboracao ocorre com board compartilhado e avaliacao na fase 4.
- O dominio ainda carrega alguns elementos legados, como o metrico `novelty`, que nao aparece no fluxo principal atual.

## Onde evoluir depois

- mover geracoes de IA para fila real se houver necessidade de escala
- adicionar observabilidade para latencia e falhas de prompts
- versionar prompts de forma mais explicita por caso de uso
- persistir telemetria de uso da IA sem misturar com o dado funcional
