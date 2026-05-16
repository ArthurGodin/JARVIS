<div align="center">

# 🤖 JARVIS

### Seu próprio assistente pessoal pra Windows — orquestra a sua estação de trabalho com um clique, atalho ou comando de voz.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![PyInstaller](https://img.shields.io/badge/Build-PyInstaller-yellow?logo=python&logoColor=white)](https://pyinstaller.org/)
[![License](https://img.shields.io/badge/License-Personal-lightgrey)](#-licença)
[![Status](https://img.shields.io/badge/Status-Active-success)](#)

*Uma sequência de comandos que abre tudo que você precisa, fecha o que distrai, posiciona janelas e bota a playlist certa. Tudo isso enquanto você só fala "**hey jarvis, modo trabalho**".*

</div>

---

## ✨ O que o JARVIS faz

Você define **modos** — combinações de aplicativos, sites, janelas e configurações que rodam juntos. Depois dispara o modo de 4 formas diferentes:

| 🖱️ Clique | ⌨️ Atalho | 🎙️ Voz | ⏰ Agenda |
|---|---|---|---|
| Botão grande no painel | `Ctrl+Alt+1`, `Ctrl+Alt+2`... | *"hey jarvis, modo foco"* | `mon-fri 09:00` |

E ele:
- 🚀 Abre **VSCode + GitHub + Spotify** com 1 comando (Modo Trabalho)
- 🎯 Fecha **Discord + Slack** e bota lo-fi (Modo Foco)
- 🪟 Posiciona janelas automaticamente (esquerda, direita, fullscreen)
- 🔊 Ajusta volume mestre do Windows
- 🎙️ Conversa com você (Voz IA via Groq) — pergunta, comenta, comanda
- 💬 Responde com **voz neural Microsoft** (Antonio/Francisca/Thalita)
- 🔁 Tem janela de follow-up de **12s** — você fala várias coisas em sequência sem repetir "hey jarvis"

---

## 🚀 Instalação rápida

### Pra usar (não precisa Python)

1. Baixa a release mais recente (em breve nas [Releases](../../releases))
2. Extrai o `JARVIS.zip` num lugar permanente
3. Duplo clique em `JARVIS.exe`
4. (Opcional) Configura a **Groq Key** grátis em [console.groq.com](https://console.groq.com/keys) pra ativar a Voz IA

### Pra desenvolver

```bash
git clone https://github.com/ArthurGodin/JARVIS.git
cd JARVIS/JARVIS
pip install -r requirements.txt
python -m jarvis.app
```

### Pra gerar o `.exe`

```bash
python -m PyInstaller --noconfirm jarvis.spec
# Resultado em dist/JARVIS/ (~230 MB)
```

---

## 🧠 JARVIS Master Briefing — vire mestre absoluto do projeto

> *"Um único arquivo que, colado numa IA, transforma ela na maior especialista em JARVIS que existe."*

Junto com o executável vai um arquivo chamado **[`JARVIS_MASTER_BRIEFING.md`](JARVIS/JARVIS_MASTER_BRIEFING.md)** — um briefing completo, exaustivo e atualizado do produto inteiro: features, arquitetura, troubleshooting, roadmap, schema de config, comandos de voz, decisões de design... tudo.

### Como usar

1. Abre o arquivo `JARVIS_MASTER_BRIEFING.md`
2. Cola o conteúdo inteiro numa conversa nova com **ChatGPT, Claude, Gemini** — qualquer LLM
3. Pergunta o que quiser

A IA absorve tudo, segue um system prompt rígido no topo (responder só com o que está no briefing, sem inventar) e vira o **Mestre JARVIS**. Pergunte:

```
"Como faço o JARVIS abrir o Spotify às 9h da manhã segunda a sexta?"
"A voz está robótica, por quê?"
"Tem versão pra Mac?"
"Como adiciono uma action customizada?"
"Por que precisa de Groq Key?"
```

E ela responde como uma pessoa que estudou o produto inteiro.

### O que tem dentro

18 seções, ~26 KB, cobrindo:

- Visão geral + filosofia do produto
- Instalação detalhada + primeira utilização (onboarding)
- **Todas as 9 actions** explicadas (open_url, open_app, close_app, set_volume, arrange_window...)
- Sistemas de voz (TTS Edge + SAPI fallback, Wake Word, Voz IA)
- Hotkeys, scheduler, histórico SQLite, tray, plugins, autostart, feedback
- Tela por tela da UI (5 abas)
- Schema completo do `config.json`
- Exemplos de comandos de voz
- **Arquitetura técnica** com diagrama de módulos
- Stack tecnológica + estrutura de arquivos
- **Roadmap** (C2 backend proxy, hotword PT-BR custom, macros gravadas)
- Limitações conhecidas + 8 cenários de troubleshooting
- Localização de dados do usuário
- 6 perguntas-exemplo com respostas pra calibrar o tom

> 💡 **Dica**: ao atualizar uma feature do JARVIS, atualize o briefing. Ele é a fonte canônica de "o que existe / o que não existe" — útil pra você, pra IAs e pra futuros contribuidores.

---

## 🎙️ Voz — o coração responsivo

### Wake Word
- Modelo **OpenWakeWord** rodando 100% local (ONNX)
- Diga *"rêi djárvis"* (pronúncia inglesa simples)
- Sensibilidade configurável: `0.20` (muito permissivo) → `0.70` (estrito)

### Text-to-Speech
- Padrão: **Edge TTS neural** (vozes da Microsoft, qualidade humana, online)
- Fallback automático: **Windows SAPI** se a internet cair
- 3 vozes pt-BR: Antonio (masc), Francisca (fem), Thalita (fem multilingual)
- Botão "Testar" na UI pra ouvir antes de salvar

### Voz IA
- **Groq** (Whisper para STT + LLaMA-3.3-70B pra entender intenção)
- Free tier cobre uso pessoal sobrando
- Decide entre 3 caminhos automaticamente:
  - 🎯 **Modo**: ativa um modo da sua lista
  - 💭 **Chat**: pergunta/comentário ("conta uma piada", "que horas são")
  - ⚙️ **Sistema**: comandos do próprio JARVIS (*"encerra você"*)
- **Follow-up de 12s**: depois de responder, JARVIS fala *"Pronto"* e fica escutando — você fala a próxima coisa sem precisar de wake word

---

## 🛠️ Stack tecnológica

| Camada | Tech |
|---|---|
| Runtime | Python 3.11+ |
| UI | HTML/CSS/JS dentro de **PyWebView** (Edge Chromium) |
| Voz IA | **Groq SDK** (Whisper-large-v3-turbo + LLaMA-3.3-70b-versatile) |
| TTS | **edge-tts** (vozes neurais Microsoft) + SAPI fallback |
| Wake Word | **OpenWakeWord** (ONNX runtime, modelo `hey_jarvis_v0.1`) |
| Áudio | sounddevice + PortAudio |
| Audio control | pycaw + comtypes |
| Window mgmt | pygetwindow + ctypes Win32 |
| Process | psutil |
| Storage | SQLite (histórico) + JSON (config + modes) |
| IPC | TCP localhost (porta 35417) |
| Distribuição | **PyInstaller --onedir** |

---

## 🧬 Arquitetura

```
jarvis/
├── app.py                  # Boot: config → IPC → hotkeys → wake_word → tray → painel
├── state.py                # Estado global compartilhado (RLock re-entrante)
├── constants.py            # Paths frozen-aware (sys._MEIPASS pro PyInstaller)
│
├── triggers/               # O que dispara ações
│   ├── hotkey.py           # Atalhos globais (Ctrl+Alt+J, etc)
│   ├── wake_word.py        # "Hey JARVIS" via OpenWakeWord
│   └── voice_ai.py         # Groq Whisper + LLaMA + follow-up
│
├── recipes/                # Execução de modos
│   ├── executor.py         # Roda actions em sequência + histórico
│   └── validator.py        # Valida campos obrigatórios por action
│
├── actions/                # 9 actions nativas + plugins
│   ├── open_url.py / open_app.py / open_folder.py
│   ├── run_command.py / open_terminal.py / close_app.py
│   ├── set_volume.py / arrange_window.py / wait.py
│   └── registry.py         # Plugin loader com allowlist de segurança
│
├── output/
│   └── tts.py              # Edge TTS + SAPI fallback (mciSendString)
│
├── ui/
│   ├── panel.py            # PyWebView + cache-bust
│   ├── api.py              # Bridge JS ↔ Python
│   ├── tray.py             # Ícone na bandeja
│   └── ipc.py              # IPC TCP localhost
│
├── config/                 # Defaults + loader com deep merge
├── runtime/                # Autostart, feedback, history, scheduler...
└── web/                    # HTML/CSS/JS do painel
```

📐 **Quer mergulhar fundo?** Veja [`JARVIS/ARQUITETURA-JARVIS-V3.md`](JARVIS/ARQUITETURA-JARVIS-V3.md).

---

## 🗺️ Roadmap

### Já entregue ✅
- Modos com 9 actions + drag-and-drop, importar/exportar
- Voz IA (Groq) + TTS neural + Wake Word
- Follow-up de 12s com "Pronto" audível
- Histórico SQLite + Stats com gráficos
- Scheduler (cron-like amigável: `mon-fri 09:00`)
- Autostart com Windows (registry HKCU)
- Feedback via Discord webhook
- Onboarding wizard de 4 telas
- Plugins com allowlist de segurança
- Tema claro/escuro automático
- PyInstaller `.exe` (~230 MB)
- **Master Briefing** pra qualquer IA virar especialista

### Em estudo 🔬
- **C2** — Backend proxy do Groq (usuário não precisa criar conta) + auto-update via GitHub Releases
- **Hotword PT-BR custom** — modelo treinado com amostras em português
- **C3** — Landing + vídeo demo + instalador NSIS
- **B** — Macros gravadas, sugestões por contexto, ações condicionais
- TTS streaming pra reduzir latência da primeira fala

---

## 💡 Filosofia

- **Tudo opt-in/opt-out**: voz IA, autostart, histórico, plugins — tudo desligável.
- **Sem cloud-only**: roda offline (com limitação da Voz IA + TTS robótico via SAPI).
- **Sem conta**: não tem cadastro. Os dados são seus, na sua máquina.
- **Privacidade**: zero telemetria. Feedback é manual via botão.
- **Brasileiro de berço**: UI 100% pt-BR, vozes pt-BR, modos default pensados pro contexto BR.

---

## 📂 Onde ficam seus dados

| O que | Onde |
|---|---|
| Config | `%APPDATA%\JARVIS\jarvis.config.json` |
| Modos | `%APPDATA%\JARVIS\jarvis.modes.json` |
| Histórico | `%APPDATA%\JARVIS\jarvis.history.db` (SQLite) |
| Logs | `%APPDATA%\JARVIS\logs\jarvis.log` |
| Plugins | `dist/JARVIS/plugins/` (ao lado do .exe) |

Pra desinstalar: apaga a pasta extraída + `%APPDATA%\JARVIS\`. Sem rastros.

---

## 🤝 Feedback

Direto pelo painel: ícone de **sininho** no header → escreve → envia. Vai como embed pro Discord do dev.

Ou abre uma [Issue](../../issues) aqui mesmo.

---

## 📜 Licença

Projeto pessoal de **[Arthur Godinho](https://github.com/ArthurGodin)**. Em fase de polimento pra distribuição. Entre em contato pra licenciamento comercial.

---

<div align="center">

**Feito com ☕ em Teresina-PI 🇧🇷**

*"Um sabe-tudo que faz as coisas pra você de forma rápida e responsiva."*

</div>
