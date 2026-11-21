#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"

echo "=== Instalando Allan ==="

# Criar start.sh
cat > "$SCRIPT_DIR/start.sh" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
exec python3 "$SCRIPT_DIR/allan.py"
EOF
chmod +x "$SCRIPT_DIR/start.sh"

# Criar .desktop
cat > "$SCRIPT_DIR/allan.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Allan
Comment=Assistente de IA pessoal e local
Exec=$SCRIPT_DIR/start.sh
Icon=utilities-terminal
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

mkdir -p "$AUTOSTART_DIR"
cp "$SCRIPT_DIR/allan.desktop" "$AUTOSTART_DIR/allan.desktop"
echo "✓ Auto-start configurado"

if command -v ollama &> /dev/null; then
    echo "✓ Ollama encontrado"
    MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l)
    echo "  $MODEL_COUNT modelo(s) disponível(is)"
    if [ "$MODEL_COUNT" -eq 0 ]; then
        echo ""
        echo "  Nenhum modelo. Para começar:"
        echo "    ollama pull llama3.2:3b"
        echo "  Ou importe um GGUF:"
        echo "    ollama create meu-modelo -f Modelfile"
    fi
else
    echo "✗ Ollama não encontrado. Instale: https://ollama.ai"
fi

echo ""
echo "=== Allan instalado! ==="
echo "Iniciar: python3 $SCRIPT_DIR/allan.py"
