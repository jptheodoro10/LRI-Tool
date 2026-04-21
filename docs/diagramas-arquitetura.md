# Diagramas de Arquitetura

## Visao Geral

```mermaid
flowchart LR
    subgraph U["Atores"]
        R["Pesquisador / Facilitador"]
        P["Participante Convidado"]
    end

    subgraph FE["Frontend React + Vite"]
        APP["App / React Router"]
        PHASE["ProjectPhasePage"]
        APIJS["services/api.js"]
        INV["InvitePage"]
    end

    subgraph BE["Backend FastAPI"]
        ROUTERS["Routers
auth / runs / canvas / invites / scores"]
        SERVICES["Services
RunService
CanvasService
AISuggestionService
InviteService
ScoreService
PDFService"]
        LLM["LLMClient
MockLLMClient | OpenAILLMClient"]
        REPOS["Repositories"]
    end

    subgraph DB["Persistencia"]
        PG["PostgreSQL"]
        EX["exports/*.pdf"]
    end

    subgraph AUX["Auxiliar"]
        WK["Worker placeholder
reservado para jobs futuros"]
    end

    R --> APP
    P --> INV

    APP --> PHASE
    INV --> APIJS
    PHASE --> APIJS
    APIJS --> ROUTERS

    ROUTERS --> SERVICES
    SERVICES --> REPOS
    REPOS --> PG
    SERVICES --> LLM
    SERVICES --> EX

    LLM -->|"mock offline ou OpenAI Responses API"| SERVICES

    WK -. atualmente nao executa fluxos centrais .- BE

    PHASE -->|"Fase 1: 1 request por campo vazio em paralelo"| ROUTERS
    PHASE -->|"Fase 3: 1 request por campo em paralelo"| ROUTERS
    PHASE -->|"autosave periodico do canvas"| ROUTERS
    PHASE -->|"advance-phase / decision / export"| ROUTERS

    ROUTERS -->|"JWT bearer"| R
    ROUTERS -->|"invite token + participant_id"| P

    PG -->|"runs, participants, invites,\ncanvas_responses, ai_suggestions,\nscores, decisions, exports"| REPOS
```

## Fluxo de IA em Paralelo

```mermaid
sequenceDiagram
    autonumber
    actor U as Facilitador
    participant FE as ProjectPhasePage
    participant API as FastAPI / canvas router
    participant AIS as AISuggestionService
    participant LLM as LLMClient
    participant DB as PostgreSQL

    U->>FE: Clica em "Generate recommendations" ou "Get overview"
    FE->>API: Persiste estado atual do canvas
    API->>DB: Upsert das respostas
    DB-->>API: OK
    API-->>FE: Estado persistido

    par Campo 1
        FE->>API: POST /canvas/{field1}/recommendation
        API->>AIS: gerar sugestao do campo 1
        AIS->>DB: ler contexto do canvas / sugestoes
        DB-->>AIS: contexto
        AIS->>LLM: generate(prompt campo 1)
        LLM-->>AIS: texto campo 1
        AIS->>DB: salvar sugestao campo 1
        DB-->>AIS: OK
        AIS-->>API: payload campo 1
        API-->>FE: resposta campo 1
        FE-->>U: renderiza campo 1 assim que chega
    and Campo 2
        FE->>API: POST /canvas/{field2}/recommendation
        API->>AIS: gerar sugestao do campo 2
        AIS->>DB: ler contexto do canvas / sugestoes
        DB-->>AIS: contexto
        AIS->>LLM: generate(prompt campo 2)
        LLM-->>AIS: texto campo 2
        AIS->>DB: salvar sugestao campo 2
        DB-->>AIS: OK
        AIS-->>API: payload campo 2
        API-->>FE: resposta campo 2
        FE-->>U: renderiza campo 2 assim que chega
    and Campo N
        FE->>API: POST /canvas/{fieldN}/recommendation
        API->>AIS: gerar sugestao do campo N
        AIS->>DB: ler contexto do canvas / sugestoes
        DB-->>AIS: contexto
        AIS->>LLM: generate(prompt campo N)
        LLM-->>AIS: texto campo N
        AIS->>DB: salvar sugestao campo N
        DB-->>AIS: OK
        AIS-->>API: payload campo N
        API-->>FE: resposta campo N
        FE-->>U: renderiza campo N assim que chega
    end

    Note over FE,U: Beneficio: o usuario nao espera o campo mais lento para ver os primeiros resultados
```

## Como Visualizar

- No VS Code, abra este arquivo e use `Open Preview` ou `Open Preview to the Side`.
- No GitHub, Mermaid em blocos Markdown costuma renderizar automaticamente.
- No Mermaid Live Editor, cole o conteudo deste arquivo ou apenas o bloco desejado: `https://mermaid.live`
