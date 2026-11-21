# Allan

Assistente de IA pessoal, local e always-on para Linux.

Allan e um overlay desktop flutuante que roda 100% local com modelos via [Ollama](https://ollama.ai). Ele gerencia seu PC, modelos de IA, arquivos, apps, musica e volume — tudo por linguagem natural em portugues.

![GTK3](https://img.shields.io/badge/GTK3-Python-blue)
![Local](https://img.shields.io/badge/100%25-Local-green)
![Linux](https://img.shields.io/badge/Linux-Only-orange)

---

## Features

- **Chat com IA local** — qualquer modelo Ollama (DeepSeek, Qwen, Llama, etc.)
- **Always-on overlay** — fica no topo da tela, abre com hover ou clique
- **Controle de musica** — toca, pausa, pula e troca musicas no YouTube Music / Spotify
- **Controle de volume** — sistema e player, por voz natural
- **Conexoes automaticas** — detecta PWAs (Brave/Chrome) e apps nativos instalados
- **Gerencia modelos** — listar, baixar e remover modelos Ollama
- **Monitora o sistema** — CPU, RAM, disco, processos
- **Gerencia arquivos** — listar diretorios, navegar pastas
- **Abre aplicativos** — inicia qualquer app instalado
- **Configuravel** — nome, cor, posicao, tamanho, hover, instrucoes custom
- **Auto-start** — inicia automaticamente no login

---

## Comandos por linguagem natural

| Comando | Acao |
|---------|------|
| `toca Back In Black` | Toca a musica no YouTube Music |
| `pausa` | Pausa a musica |
| `proxima musica` | Pula para a proxima |
| `aumenta o volume` | +10% sistema e player |
| `volume 50` | Seta volume em 50% |
| `volume no maximo` | 100% |
| `mudo` | Muta/desmuta |
| `o que ta tocando` | Mostra titulo e artista |
| `info do sistema` | CPU, RAM, disco |
| `listar modelos` | Modelos Ollama instalados |
| `baixar llama3.2:3b` | Baixa um modelo |
| `listar arquivos ~/Downloads` | Lista o diretorio |
| `abrir firefox` | Abre o app |
| `processos` | Top processos por memoria |

---

## Instalacao

### Requisitos

- Linux (GNOME/Wayland ou X11)
- Python 3.10+
- GTK3 (`gir1.2-gtk-3.0`)
- [Ollama](https://ollama.ai) instalado
- `playerctl` e `xdotool` (para controle de musica/volume)

### Setup

```bash
# 1. Clone o projeto
git clone https://github.com/OscarFlavioJr/Allan.git
cd Allan

# 2. Instale dependencias do sistema
sudo apt install -y gir1.2-gtk-3.0 playerctl xdotool

# 3. Instale o auto-start (opcional)
./install.sh

# 4. Inicie
cd ~/scripts/allan && GDK_BACKEND=x11 python3 allan.py &
```

### Configurando um modelo

Allan detecta automaticamente os modelos do Ollama. Se nenhum estiver instalado:

```bash
# Opcao 1: Baixar do Ollama
ollama pull llama3.2:3b

# Opcao 2: Importar um GGUF
echo 'FROM /caminho/para/seu-modelo.gguf' > Modelfile
ollama create meu-modelo -f Modelfile
```

---

## Interface

### Abas

| Aba | Funcao |
|-----|--------|
| **Chat** | Conversa com a IA, comandos por texto |
| **Config** | Nome, cor, posicao, hover, tamanho da barra, instrucoes, modelo |
| **Conexoes** | PWAs e apps detectados, conectar/desconectar, abrir/parar |

### Configuracoes

- **Nome** — muda o titulo do assistente
- **Microfone** — toggle on/off (STT futuro)
- **Hover** — abre ao passar o mouse
- **Cor** — 8 opcoes de cor accent
- **Posicao** — Topo, Esquerda, Direita, Embaixo
- **Tamanho da barra** — Compacto, Normal, Largo
- **Instrucoes** — system prompt customizado
- **Modelo** — selecao do modelo Ollama

---

## Estrutura

```
allan/
├── allan.py                 # Ponto de entrada
├── install.sh               # Gera start.sh e autostart
├── core/
│   ├── brain.py             # Deteccao de comandos + chat com Ollama
│   ├── config.py            # Persistencia em ~/.config/allan/
│   ├── connections.py       # Deteccao de PWAs e apps nativos
│   ├── media_controller.py  # Controle de musica e volume (playerctl/wpctl)
│   ├── ollama_manager.py    # API do Ollama (chat, pull, delete, stream)
│   └── system_manager.py    # Sistema (RAM, disco, processos, arquivos)
└── ui/
    └── overlay.py           # Interface GTK overlay always-on-top
```

---

## Como funciona

1. **Overlay GTK3** com fundo translucido (Cairo), always-on-top, tipo UTILITY
2. **XWayland** (`GDK_BACKEND=x11`) para posicionamento funcionar no GNOME Wayland
3. **Hover** com delay de 200ms para abrir, 400ms para fechar (nao fecha com foco no input)
4. **Chat streaming** — respostas token a token via Ollama API
5. **PWA detection** — escaneia .desktop files para encontrar apps do Brave/Chrome
6. **Media control** — playerctl (MPRIS) para controle do player, wpctl para volume do sistema
7. **Config** — JSON em `~/.config/allan/config.json`, salva imediatamente a cada mudanca

---

## Roadmap

- [ ] Integracao com navegador (extensao)
- [ ] Comandos por voz (speech-to-text local)
- [ ] Plugins para automacao
- [ ] Fallback para Claude API quando Ollama indisponivel
- [ ] Tray icon com notificacoes
- [ ] Temas personalizaveis

---

## Licenca

MIT
