import json
import re
from core import ollama_manager as ollama
from core import system_manager as system
from core import media_controller as media
from core import screen

DEFAULT_MODEL = None

NO_MODEL_MSG = """Nenhum modelo encontrado no Ollama.

Para começar, escolha uma opção:
  1. Baixar um modelo: ollama pull llama3.2:3b
  2. Importar um GGUF: ollama create meu-modelo -f Modelfile
  3. Se tiver o Claude Code instalado, peça ajuda para configurar!

Depois de instalar, me envie qualquer mensagem."""

BASE_SYSTEM_PROMPT = """Você é {name}, um assistente de IA pessoal e local. Você roda no computador do usuário e pode:
- Gerenciar modelos de IA (Ollama): listar, baixar, remover
- Ver informações do sistema: RAM, disco, CPU, processos
- Listar arquivos e pastas
- Abrir aplicativos e tocar músicas
- Ver a tela do usuário quando ele pedir (você recebe uma captura de tela como imagem)
- Executar comandos no terminal
- Responder perguntas gerais

Quando o usuário pedir algo relacionado ao sistema, use as ferramentas disponíveis.
Seja direto, útil e fale em português brasileiro.
Responda de forma concisa."""

TOOLS = [
    {"name": "system_info", "desc": "Ver informações do sistema (CPU, RAM, disco)"},
    {"name": "list_models", "desc": "Listar modelos Ollama instalados"},
    {"name": "pull_model", "desc": "Baixar um modelo. Args: name"},
    {"name": "delete_model", "desc": "Remover um modelo. Args: name"},
    {"name": "list_dir", "desc": "Listar arquivos. Args: path"},
    {"name": "list_processes", "desc": "Ver processos rodando"},
    {"name": "kill_process", "desc": "Matar processo. Args: pid"},
    {"name": "open_app", "desc": "Abrir aplicativo. Args: name"},
    {"name": "run_command", "desc": "Executar comando no terminal. Args: cmd"},
]


SCREEN_RE = re.compile(
    r"screenshot|print da tela|captura de tela"
    r"|\b(olh\w*|v[eê]\w*|analis\w*|l[eê]\w*|explic\w*|descrev\w*|o que)\b.*\btela\b"
)


def _detect_tool_call(user_msg):
    msg_lower = user_msg.lower()

    if SCREEN_RE.search(msg_lower):
        return "see_screen", {}

    if any(w in msg_lower for w in ["info do sistema", "informações do sistema", "ram", "cpu", "uso de disco", "memória do sistema"]):
        return "system_info", {}
    if any(w in msg_lower for w in ["listar modelos", "quais modelos", "modelos instalados"]):
        return "list_models", {}
    if any(w in msg_lower for w in ["processos", "o que está rodando", "ps aux"]):
        return "list_processes", {}

    if any(w in msg_lower for w in ["pausar", "pausa", "pause", "para a música", "para a musica"]):
        return "media_pause", {}
    if re.search(r"^(continuar?|resume|despausar?|volta a tocar|play)$", msg_lower.strip()):
        return "media_play", {}
    if any(w in msg_lower for w in ["próxima música", "proxima musica", "next", "pula", "skip"]):
        return "media_next", {}
    if any(w in msg_lower for w in ["música anterior", "musica anterior", "previous", "volta a música", "volta a musica"]):
        return "media_prev", {}
    if any(w in msg_lower for w in ["o que tá tocando", "o que está tocando", "que música é essa", "que musica é essa", "now playing"]):
        return "media_status", {}

    vol_max = re.search(r"volume.*(máximo|maximo|max|100)|bota.*volume.*(máximo|maximo|max)", msg_lower)
    if vol_max:
        return "vol_set", {"percent": 100}
    vol_min = re.search(r"volume.*(mínimo|minimo|min|mudo|mute)|mutar?|silenciar?", msg_lower)
    if vol_min:
        return "vol_mute", {}
    vol_set = re.search(r"volume\s+(?:em\s+|para?\s+|no\s+)?(\d+)", msg_lower)
    if vol_set:
        return "vol_set", {"percent": int(vol_set.group(1))}
    vol_up = re.search(r"(?:aumentar?|sobe|suba|mais)\s*(?:o\s+)?volume|volume\s+(?:mais\s+)?alto", msg_lower)
    if vol_up:
        return "vol_up", {}
    vol_down = re.search(r"(?:diminuir?|abaixa|baixa|menos)\s*(?:o\s+)?volume|volume\s+(?:mais\s+)?baixo", msg_lower)
    if vol_down:
        return "vol_down", {}
    vol_query = re.search(r"(?:qual|quanto).*volume|volume.*(?:tá|está|atual)", msg_lower)
    if vol_query:
        return "vol_get", {}

    music_match = re.search(
        r"(?:tocar?|toca|play|reproduzir?|coloca)\s+(.+?)(?:\s+(?:no|na|pelo|pela|em|on)\s+"
        r"(?:youtube\s*music|spotify|yt\s*music))?$",
        msg_lower,
    )
    if music_match:
        song = music_match.group(1).strip()
        if "spotify" in msg_lower:
            return "play_music", {"song": song, "app": "spotify"}
        return "play_music", {"song": song, "app": "youtube-music"}

    pull_match = re.search(r"(?:baixar?|instalar?|pull)\s+(?:o?\s*modelo\s+)?(\S+)", msg_lower)
    if pull_match:
        return "pull_model", {"name": pull_match.group(1)}

    del_match = re.search(r"(?:remover?|deletar?|apagar?|delete)\s+(?:o?\s*modelo\s+)?(\S+)", msg_lower)
    if del_match:
        return "delete_model", {"name": del_match.group(1)}

    dir_match = re.search(r"(?:listar?|mostrar?|ver)\s+(?:arquivos|pastas|diretório)\s*(.*)", msg_lower)
    if dir_match:
        path = dir_match.group(1).strip() or "~"
        return "list_dir", {"path": path}

    app_match = re.search(r"(?:abrir?|abra|open|iniciar?)\s+(?:o\s+)?(\S+)", msg_lower)
    if app_match:
        return "open_app", {"name": app_match.group(1)}

    return None, {}


def _execute_tool(name, args):
    if name == "system_info":
        return system.get_system_info()
    elif name == "list_models":
        models = ollama.list_models()
        return models if models else "Nenhum modelo instalado."
    elif name == "pull_model":
        result = ollama.pull_model(args["name"])
        return "Modelo baixado!" if result is True else f"Erro: {result}"
    elif name == "delete_model":
        ok = ollama.delete_model(args["name"])
        return "Modelo removido." if ok else "Erro ao remover."
    elif name == "list_dir":
        return system.list_dir(args.get("path", "~"))
    elif name == "list_processes":
        return system.list_processes()
    elif name == "kill_process":
        ok = system.kill_process(args["pid"])
        return "Processo encerrado." if ok else "Erro ao encerrar."
    elif name == "open_app":
        ok = system.open_app(args["name"])
        return "Aplicativo aberto." if ok else "Erro ao abrir."
    elif name == "run_command":
        return system.run_command(args["cmd"])
    elif name == "play_music":
        return _play_music(args["song"], args.get("app", "youtube-music"))
    elif name == "media_pause":
        return "⏸ Música pausada." if media.pause() else "Nenhum player ativo. Instale playerctl: sudo apt install playerctl"
    elif name == "media_play":
        return "▶ Reproduzindo." if media.play() else "Nenhum player ativo."
    elif name == "media_next":
        return "⏭ Próxima música." if media.next_track() else "Nenhum player ativo."
    elif name == "media_prev":
        return "⏮ Música anterior." if media.prev_track() else "Nenhum player ativo."
    elif name == "media_status":
        st = media.get_status()
        if st and st.get("title"):
            status_txt = "▶ Tocando" if st["status"] == "Playing" else "⏸ Pausado"
            artist = f" — {st['artist']}" if st.get("artist") else ""
            return f"{status_txt}: {st['title']}{artist}"
        return "Nenhuma música tocando."
    elif name == "vol_up":
        ok, vol = media.change_volume(10)
        media.set_player_volume(min(100, (media.get_player_volume() or 100) + 10))
        return f"🔊 Volume do sistema: {vol}%" if ok else "Erro ao alterar volume."
    elif name == "vol_down":
        ok, vol = media.change_volume(-10)
        media.set_player_volume(max(0, (media.get_player_volume() or 100) - 10))
        return f"🔉 Volume do sistema: {vol}%" if ok else "Erro ao alterar volume."
    elif name == "vol_set":
        percent = args["percent"]
        ok = media.set_volume(percent)
        media.set_player_volume(percent)
        return f"🔊 Volume: {percent}%" if ok else "Erro ao alterar volume."
    elif name == "vol_mute":
        ok = media.mute()
        media.set_player_volume(0)
        return "🔇 Mudo." if ok else "Erro ao mutar."
    elif name == "vol_get":
        vol = media.get_volume()
        pvol = media.get_player_volume()
        parts = []
        if vol is not None:
            parts.append(f"Sistema: {vol}%")
        if pvol is not None:
            parts.append(f"Player: {pvol}%")
        return f"🔊 {' | '.join(parts)}" if parts else "Erro ao ler volume."
    return "Ferramenta desconhecida."


def _yt_find_video_id(query):
    import urllib.request, urllib.parse, re
    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=8).read().decode("utf-8", errors="replace")
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        return ids[0] if ids else None
    except Exception:
        return None


def _play_music(song, app):
    import urllib.parse
    import subprocess
    from core.connections import _find_pwa_desktop, _pwa_cache, _is_process_running

    if app == "spotify":
        url = f"https://open.spotify.com/search/{urllib.parse.quote(song)}"
        ok = system.open_app(url)
        return f"🎵 Buscando \"{song}\" no Spotify..." if ok else "Erro ao abrir o Spotify."

    video_id = _yt_find_video_id(song)
    if video_id:
        url = f"https://music.youtube.com/watch?v={video_id}"
    else:
        url = f"https://music.youtube.com/search?q={urllib.parse.quote(song)}"

    pwa = _find_pwa_desktop(["youtube music", "youtube.com/music", "music.youtube"])
    wmclass = pwa.get("wmclass") if pwa else None
    pwa_exec = pwa.get("exec") if pwa else None

    media.play_song_in_existing(url, wmclass, pwa_exec)
    msg = "Tocando" if video_id else "Buscando"
    return f"🎵 {msg} \"{song}\" no YouTube Music..."


class Brain:
    def __init__(self, config=None):
        self.history = []
        self.model = DEFAULT_MODEL
        self.config = config
        self.capture_hook = None
        self._detect_model()

    def _detect_model(self):
        models = ollama.list_models()
        if models:
            self.model = models[0]

    def set_model(self, model):
        self.model = model

    def process(self, user_msg):
        tool_name, tool_args = _detect_tool_call(user_msg)
        if tool_name == "see_screen":
            return "".join(self._see_screen(user_msg))
        if tool_name:
            result = _execute_tool(tool_name, tool_args)
            return self._format_tool_result(tool_name, result)

        return self._chat(user_msg)

    def process_stream(self, user_msg):
        tool_name, tool_args = _detect_tool_call(user_msg)
        if tool_name == "see_screen":
            yield from self._see_screen(user_msg)
            return
        if tool_name:
            result = _execute_tool(tool_name, tool_args)
            yield self._format_tool_result(tool_name, result)
            return

        self.history.append({"role": "user", "content": user_msg})
        messages = [{"role": "system", "content": self._get_system_prompt()}] + self.history[-20:]
        yield from self._stream(messages)

    def _see_screen(self, user_msg):
        if self.capture_hook:
            self.capture_hook(True)
        try:
            image = screen.capture_screen_b64()
        finally:
            if self.capture_hook:
                self.capture_hook(False)
        if not image:
            yield "Não consegui capturar a tela. Verifique se o xdg-desktop-portal está rodando e se a permissão de captura foi concedida."
            return

        self.history.append({"role": "user", "content": f"{user_msg}\n(captura de tela enviada)"})
        messages = [{"role": "system", "content": self._get_system_prompt()}] + self.history[-20:]
        messages[-1] = {
            "role": "user",
            "content": f"{user_msg}\n\n[Captura da tela atual do usuário anexada. Analise o que aparece e responda.]",
            "images": [image],
        }
        yield from self._stream(messages)

    def _stream(self, messages):
        if not ollama.is_running():
            ollama.start_server()

        models = ollama.list_models()
        if not models:
            yield NO_MODEL_MSG
            return

        if not self.model or self.model not in models:
            self.model = models[0]

        full_response = ""
        try:
            for token in ollama.chat(self.model, messages, stream=True):
                full_response += token
                yield token
        except Exception as e:
            yield f"\nErro: {e}"
            return

        if full_response:
            self.history.append({"role": "assistant", "content": full_response})
            if len(self.history) > 40:
                self.history = self.history[-30:]

    def _get_system_prompt(self):
        name = self.config.get("name") if self.config else "Allan"
        prompt = BASE_SYSTEM_PROMPT.format(name=name)
        if self.config:
            custom = self.config.get("instructions")
            if custom:
                prompt += f"\n\nInstruções adicionais do usuário:\n{custom}"
        return prompt

    def _chat(self, user_msg):
        self.history.append({"role": "user", "content": user_msg})
        messages = [{"role": "system", "content": self._get_system_prompt()}] + self.history[-20:]

        if not ollama.is_running():
            ollama.start_server()

        models = ollama.list_models()
        if not models:
            return NO_MODEL_MSG

        if not self.model or self.model not in models:
            self.model = models[0]

        response = ollama.chat(self.model, messages)
        if response:
            self.history.append({"role": "assistant", "content": response})
            if len(self.history) > 40:
                self.history = self.history[-30:]
            return response
        return "Desculpe, não consegui processar. Verifique se o Ollama está rodando."

    def _format_tool_result(self, name, result):
        if isinstance(result, dict):
            lines = []
            for k, v in result.items():
                lines.append(f"  {k}: {v}")
            return f"**{name}**\n" + "\n".join(lines)
        elif isinstance(result, list):
            if not result:
                return "Nenhum resultado."
            if isinstance(result[0], dict):
                lines = []
                for item in result[:30]:
                    parts = [f"{k}={v}" for k, v in item.items()]
                    lines.append("  " + " | ".join(parts))
                return "\n".join(lines)
            return "\n".join(f"  - {item}" for item in result)
        return str(result)

    def clear_history(self):
        self.history.clear()
