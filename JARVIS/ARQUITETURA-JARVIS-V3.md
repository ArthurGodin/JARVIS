# JARVIS v3 - Arquitetura de Produto e Implementacao

## Visao

O JARVIS nao deve evoluir para "um chatbot que abre app".
O produto certo e:

**JARVIS = orquestrador pessoal de workstation**

Valor entregue:
- entra em modo trabalho
- entra em modo reuniao
- entra em modo projeto
- restaura ambiente
- reduz atrito operacional

O gatilho por voz, hotkey e bandeja continua importante, mas como meio.
O produto vendavel e a capacidade de organizar contextos de trabalho com um comando.

---

## O Que Ja Existe Hoje

O estado atual do projeto ja valida a tese:

- gatilho por voz configuravel
- gatilho por hotkey global
- hotkey de encerramento
- bandeja do Windows para controle rapido
- comandos `--status` e `--stop`
- protecao contra varias instancias
- uma rotina fixa de automacao que executa:
  - abre musica
  - abre app
  - abre terminal/comando

Conclusao:

Hoje o JARVIS ja e um **launcher automatizado com multiplos gatilhos**.
O proximo salto e deixar de ser "uma automacao fixa" e virar "um engine de modos e receitas".

---

## Tese de Produto

### Nome da categoria

`Workstation Orchestration`

### Usuario inicial

Comecar por um publico que sente dor diaria e paga por produtividade:

- desenvolvedor
- designer
- creator
- profissional remoto
- founder/operacao

### Promessa do produto

"Com um comando, seu ambiente entra no contexto certo."

Exemplos:

- "Jarvis, trabalho"
- "Jarvis, reuniao"
- "Jarvis, projeto Atlas"
- `CTRL+ALT+J`
- clique na bandeja -> `Ativar modo`

---

## Principios do JARVIS v3

1. **Modos antes de IA**
O centro do produto e modo/receita/contexto. IA entra depois para sugerir, nao para substituir a engine.

2. **Acoes explicitas**
Cada automacao precisa ser composta por acoes claras, auditaveis e testaveis.

3. **Configuracao externa**
Usuario nao deve depender de editar Python para criar valor.

4. **Seguranca operacional**
Toda acao sensivel precisa ser reversivel, confirmavel ou pelo menos logada.

5. **Produto local-first**
O core precisa funcionar localmente. Integracoes online entram como camadas.

6. **Escalonamento por conectores**
Novas automacoes entram como plugins/acoes, nao como remendos no arquivo principal.

---

## O Que o v3 Precisa Entregar

### Nivel 1 - Produto util

- multiplos modos
- multiplos gatilhos
- editor simples de configuracao
- logs
- bandeja confiavel
- start/stop/status

### Nivel 2 - Produto bom

- contexto por horario/app/calendario
- layouts de janela
- perfis por projeto
- historico de uso
- acoes reutilizaveis

### Nivel 3 - Produto forte

- sugestoes proativas
- recomendacao de modo
- onboarding
- empacotamento como `.exe`
- autostart com Windows
- templates prontos

---

## Modelo Conceitual do v3

O v3 deve girar em torno de 4 entidades:

### 1. Trigger
Algo que inicia a automacao.

Exemplos:
- voz
- hotkey
- bandeja
- CLI
- horario
- app ativo

### 2. Mode
Nome comercial da automacao.

Exemplos:
- `trabalho`
- `foco`
- `reuniao`
- `projeto-x`

### 3. Recipe
Descricao tecnica do que o modo executa.

Exemplo:
- abrir VS Code
- abrir navegador no perfil certo
- tocar playlist
- abrir terminal na pasta X
- aguardar 2 segundos
- organizar janelas

### 4. Action
Bloco atomico e reutilizavel.

Exemplos:
- `open_app`
- `open_url`
- `run_command`
- `open_folder`
- `play_music`
- `focus_window`
- `set_volume`

---

## Arquitetura Recomendada

Hoje quase tudo esta concentrado em `jarvis-windows.py`.
No v3, isso deve ser quebrado em modulos.

### Estrutura recomendada

```text
JARVIS/
  jarvis/
    app.py
    bootstrap.py
    constants.py
    state.py
    config/
      loader.py
      schema.py
      defaults.py
    triggers/
      voice.py
      hotkey.py
      tray.py
      cli.py
      scheduler.py
    recipes/
      loader.py
      validator.py
      resolver.py
      executor.py
    actions/
      base.py
      open_app.py
      open_url.py
      run_command.py
      open_folder.py
      play_music.py
      window_layout.py
      audio.py
    integrations/
      browser.py
      spotify.py
      vscode.py
      claude.py
      windows_shell.py
    runtime/
      cooldown.py
      process_control.py
      logs.py
      telemetry.py
    ui/
      tray.py
      status.py
    profiles/
      profile_store.py
  config/
    jarvis.config.json
    modes.json
  docs/
    ARQUITETURA-JARVIS-V3.md
```

---

## Mapeamento do Codigo Atual para o v3

### O que sai de `jarvis-windows.py`

**Vai para `triggers/voice.py`**
- deteccao por voz
- normalizacao de frase
- matching por similaridade

**Vai para `triggers/hotkey.py`**
- registro de hotkeys
- hotkey de ativacao
- hotkey de encerramento

**Vai para `ui/tray.py`**
- icone da bandeja
- menu
- status visual
- acao de sair

**Vai para `runtime/process_control.py`**
- `--status`
- `--stop`
- single instance

**Vai para `actions/*`**
- abrir musica
- abrir app
- abrir terminal
- abrir pasta

**Vai para `recipes/executor.py`**
- ordem das acoes
- cooldown
- tratamento de erro

**Vai para `config/*`**
- frase de ativacao
- hotkeys
- modos
- rotas/pastas/apps

### O que sobra em `app.py`

- carregar config
- iniciar runtime
- subir triggers
- subir bandeja
- manter loop principal

---

## Configuracao Recomendada

O usuario precisa conseguir definir modos sem editar Python.

### `jarvis.config.json`

```json
{
  "voice": {
    "enabled": true,
    "phrases": ["Jarvis"],
    "language": "pt-BR",
    "similarity": 0.78
  },
  "hotkeys": {
    "enabled": true,
    "activate": "ctrl+alt+j",
    "stop": "ctrl+alt+shift+j"
  },
  "tray": {
    "enabled": true
  },
  "cooldown_seconds": 15
}
```

### `modes.json`

```json
{
  "modes": [
    {
      "id": "trabalho",
      "name": "Modo Trabalho",
      "triggers": ["voice:jarvis trabalho", "hotkey:ctrl+alt+j"],
      "actions": [
        { "type": "open_app", "app": "claude" },
        { "type": "open_url", "url": "https://music.youtube.com/..." },
        { "type": "run_command", "cwd": "C:/dev/projeto", "command": "claude --dangerously-skip-permissions" }
      ]
    }
  ]
}
```

---

## Modos Iniciais Recomendados

Para MVP vendavel, eu faria estes 5 modos:

1. `modo trabalho`
- abre app principal
- abre projeto
- abre navegador
- toca playlist

2. `modo reuniao`
- abre Teams/Meet/Zoom
- silencia ruido
- abre pauta
- abre notas

3. `modo foco`
- fecha distracoes
- abre so o necessario
- toca audio de foco
- sobe cronometro

4. `modo projeto`
- abre stack daquele projeto
- layout de janelas
- docs e links certos

5. `encerrar expediente`
- fecha apps
- salva estado
- pausa musica
- abre rotina de fechamento

---

## Ordem de Implementacao Recomendada

### Fase 1 - Base do v3

Objetivo:
tirar a logica fixa do `jarvis-windows.py` e criar fundacao modular.

Entrega:
- `app.py`
- `process_control.py`
- `triggers/voice.py`
- `triggers/hotkey.py`
- `ui/tray.py`

### Fase 2 - Engine de receitas

Objetivo:
substituir rotina fixa por lista de acoes configuraveis.

Entrega:
- `actions/base.py`
- `actions/open_app.py`
- `actions/open_url.py`
- `actions/run_command.py`
- `actions/open_folder.py`
- `recipes/executor.py`
- `recipes/validator.py`

### Fase 3 - Config externa

Objetivo:
tirar configuracao do codigo.

Entrega:
- `config/loader.py`
- `config/schema.py`
- `config/defaults.py`
- `config/jarvis.config.json`
- `config/modes.json`

### Fase 4 - Experiencia de produto

Objetivo:
deixar usavel por nao tecnico.

Entrega:
- melhor bandeja
- status visual
- logs amigaveis
- mensagens de erro boas
- onboarding

### Fase 5 - Diferenciacao

Objetivo:
ficar forte de mercado.

Entrega:
- contexto por horario
- contexto por app
- modos sugeridos
- templates
- `.exe`
- autostart

---

## Arquivos Prioritarios do Primeiro Sprint

Se a implementacao comecar agora, eu atacaria estes arquivos primeiro:

1. `jarvis/app.py`
2. `jarvis/runtime/process_control.py`
3. `jarvis/triggers/voice.py`
4. `jarvis/triggers/hotkey.py`
5. `jarvis/ui/tray.py`
6. `jarvis/actions/base.py`
7. `jarvis/actions/open_app.py`
8. `jarvis/actions/open_url.py`
9. `jarvis/actions/run_command.py`
10. `jarvis/recipes/executor.py`

---

## Diferenciais que Realmente Ajudam a Vender

O que vende:

- ganhar tempo todo dia
- entrar em contexto com um comando
- padronizar rotina
- reduzir erro operacional
- diminuir friccao antes de trabalhar

O que nao vende no inicio:

- promessas vagas de IA
- automacao muito "show off"
- features sem rotina real
- integracao com tudo ao mesmo tempo

---

## Antimetas

Coisas que eu evitaria no comeco:

- chatbot geral embutido
- home automation
- multiplataforma ao mesmo tempo
- dezenas de integracoes antes do core
- interface pesada cedo demais

---

## Definicao de MVP Vendavel

O MVP vendavel nao precisa ser "Jarvis faz tudo".
Precisa ser:

- confiavel
- rapido
- facil de configurar
- util 3 a 10 vezes por dia

Definicao pratica:

"Com voz, hotkey ou bandeja, o usuario ativa modos que montam o ambiente de trabalho certo em poucos segundos."

---

## Proximo Passo Recomendado

O melhor proximo passo tecnico nao e inventar mais gatilhos.
E construir:

**Modo + Recipe Engine + Action Layer**

Traduzindo:

- sair de rotina fixa
- entrar em automacoes configuraveis
- deixar cada modo vendavel

---

## Decisao de Produto

Se este documento for aprovado, o proximo passo de implementacao deve ser:

**Sprint 1 do JARVIS v3**

Meta do sprint:
- modularizar o arquivo atual
- criar engine de acoes
- criar config externa
- fazer o primeiro modo real (`modo trabalho`)

