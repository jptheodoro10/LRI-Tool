# Versao para Artigo

## Arquitetura da Aplicacao

A aplicacao proposta foi implementada como um sistema web composto por frontend em React/Vite, backend em FastAPI, persistencia em PostgreSQL e uma camada de abstracao para servicos baseados em modelos de linguagem. A arquitetura adota uma separacao em camadas no backend, organizada como `Router -> Service -> Repository -> Database`. Essa organizacao foi escolhida para desacoplar a exposicao HTTP da logica de negocio e da persistencia, reduzindo o acoplamento entre componentes e facilitando manutencao, testes e evolucao incremental.

O elemento central do dominio e a entidade `Run`, que representa a execucao de uma sessao de Lean Research Inception. Cada `Run` guarda o titulo do projeto, a fase atual, o ciclo atual, o estado de execucao e a sintese final do problema. O processo foi estruturado em cinco fases: preenchimento inicial do canvas, alinhamento com participantes e geracao de convites, revisao do problema, avaliacao semantica e decisao final com exportacao. Alem disso, a arquitetura suporta a nocao de ciclos. Quando a decisao final e `PIVOT`, o sistema retorna para a fase 2, incrementa o ciclo e reaproveita o conteudo do canvas anterior como base para uma nova iteracao. Essa decisao preserva continuidade entre iteracoes e reduz retrabalho durante a reformulacao do problema.

No frontend, a interface principal concentra a interacao do facilitador com o canvas, o controle de fases, a geracao de convites, a avaliacao dos resultados e o acionamento dos modulos de IA. O backend expoe endpoints REST para autenticacao, gerenciamento de projetos, canvas, convites e pontuacoes. O controle de acesso separa dois perfis de uso: o facilitador autenticado via JWT e os participantes externos autenticados por meio de links tokenizados de convite. Essa separacao reduz friccao para participantes convidados, ao mesmo tempo em que preserva verificacoes explicitas de autorizacao por projeto e participante.

## Modulos de IA

A arquitetura de IA foi projetada como uma capacidade transversal ao sistema. Em vez de acoplar diretamente o backend a um fornecedor especifico, foi definida uma interface unica, `LLMClient.generate(prompt)`, com duas implementacoes: uma versao deterministica de mock, utilizada em execucoes offline e testes locais, e uma implementacao baseada na OpenAI Responses API. Essa decisao aumenta a portabilidade da solucao, facilita experimentacao com diferentes provedores e melhora a reprodutibilidade do artefato.

Do ponto de vista funcional, a aplicacao possui dois modulos principais de IA. O primeiro atua na fase 1, gerando recomendacoes textuais para campos vazios do canvas com base no contexto ja preenchido. O segundo atua na fase 3, produzindo uma analise critica de cada campo do canvas quando o quadro ja esta completo. Embora ambos usem a mesma infraestrutura de prompts e provedor, eles possuem objetivos distintos: o primeiro auxilia no preenchimento, enquanto o segundo apoia a reflexao e refinamento do problema formulado.

Uma decisao arquitetural relevante foi executar as requisicoes de IA por campo em paralelo no frontend. Quando o facilitador solicita recomendacoes na fase 1 ou overviews na fase 3, a interface identifica os campos-alvo e dispara uma chamada independente para cada um deles. Como consequencia, os resultados podem ser exibidos progressivamente, assim que cada resposta e concluida, sem que o usuario precise aguardar o termino do lote completo. Essa estrategia reduz a latencia percebida e melhora a experiencia de uso, especialmente em cenarios em que o tempo de resposta do modelo varia entre chamadas.

No caso das recomendacoes da fase 1, as sugestoes sao persistidas em banco de dados. Alem do texto gerado, o sistema armazena status de execucao, timestamps e um `context_hash`, calculado a partir do contexto do canvas e da versao do prompt. Esse mecanismo evita recomputacoes desnecessarias quando o estado relevante do canvas nao foi alterado, reduzindo custo e tempo de resposta. Em contraste, os overviews da fase 3 nao sao persistidos, pois foram modelados como artefatos efemeros de apoio a reflexao do facilitador. Essa diferenciacao entre persistencia funcional e estado temporario evita poluicao da base de dados com saidas transitivas da interface.

## Persistencia e Fluxos de Colaboracao

O canvas e reutilizado nas fases 1, 2 e 3, com respostas organizadas por projeto, pergunta e ciclo. Apesar de haver colaboracao entre participantes ao longo do processo, a edicao direta do canvas fica restrita ao facilitador. Os participantes externos contribuem principalmente por meio da avaliacao semantica na fase 4. Essa decisao simplifica o controle de concorrencia, reduz conflitos de escrita e preserva consistencia no artefato principal em construcao.

Na fase 2, o sistema gera links publicos de convite para participantes. Na primeira iteracao do processo, o avancar para a fase 3 exige pelo menos um convite gerado. Em ciclos subsequentes, apos um `PIVOT`, novos convites sao bloqueados e o grupo existente e mantido. Essa regra estabiliza o conjunto de participantes nas iteracoes seguintes e favorece comparabilidade entre ciclos de refinamento.

Na fase 4, os participantes submetem avaliacoes em escala de 1 a 7 para tres metricas: valor, aplicabilidade e viabilidade. O backend agrega as respostas e calcula distribuicoes, medias e medianas para apoiar a decisao final. Na fase 5, esses resultados, juntamente com o problema formulado e a sintese escrita pelo facilitador, sao consolidados em um PDF exportavel. Assim, o sistema nao apenas apoia a conducao do processo, mas tambem produz um artefato final compartilhavel e passivel de documentacao.

## Implicacoes Arquiteturais

Em sintese, a arquitetura adotada privilegia reprodutibilidade local, separacao clara de responsabilidades e boa experiencia interativa. A opcao por fluxos de IA acionados sob demanda, em vez de uma fila assicrona completa, reduz a complexidade operacional do artefato sem comprometer o comportamento principal esperado. Ao mesmo tempo, o uso de chamadas paralelas ao modelo de linguagem permite compensar parcialmente essa simplicidade com uma interface progressiva e responsiva. Como limitacoes, observa-se que o worker existente ainda nao executa jobs reais e que a aplicacao ainda nao possui uma camada mais robusta de observabilidade para latencia, custo ou falhas de prompts. Ainda assim, a estrutura atual oferece uma base adequada para extensao futura sem exigir refatoracao arquitetural radical.

## Sugestao de Legenda de Figura

Figura X. Visao geral da arquitetura da aplicacao, destacando a separacao entre frontend, backend em camadas, persistencia, fluxo de convites e integracao com modelos de linguagem.

## Sugestao de Chamada no Texto

A Figura X apresenta a arquitetura geral da aplicacao. Observa-se a separacao entre a interface web, a API em FastAPI organizada em camadas e a infraestrutura de persistencia e suporte a IA. Uma decisao relevante foi a execucao paralela de chamadas ao modelo de linguagem por campo do canvas, reduzindo a latencia percebida e permitindo renderizacao progressiva dos resultados na interface.
