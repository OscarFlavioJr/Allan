import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango
import threading
import cairo


class AllanOverlay(Gtk.Window):
    def __init__(self, brain, config):
        super().__init__()
        self.brain = brain
        self.brain.capture_hook = self._hide_for_capture
        self.config = config
        self.expanded = False
        self.is_processing = False
        self.current_tab = "chat"
        self._hover_timeout = None
        self._leave_timeout = None

        self._setup_window()
        self._build_ui()
        self._apply_css()

        self.connect("destroy", Gtk.main_quit)
        self.connect("draw", self._on_draw)
        self.connect("realize", lambda w: GLib.timeout_add(50, self._reposition))
        self.connect("size-allocate", lambda w, a: GLib.idle_add(self._reposition))

    def _reposition(self):
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geom = monitor.get_geometry()
        w, h = self.get_size()
        w = max(w, 200)
        h = max(h, 40)
        pos = self.config.get("position")

        if pos == "left":
            x = geom.x
            y = geom.y + (geom.height - h) // 2
        elif pos == "right":
            x = geom.x + geom.width - w
            y = geom.y + (geom.height - h) // 2
        elif pos == "bottom":
            x = geom.x + (geom.width - w) // 2
            y = geom.y + geom.height - h
        else:
            x = geom.x + (geom.width - w) // 2
            y = geom.y

        self.move(x, y)
        return False

    # ── Window ──

    def _setup_window(self):
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_resizable(False)
        self.set_accept_focus(True)
        self.stick()
        self.set_default_size(280, -1)
        self.set_title(self.config.get("name"))

        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK |
            Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.connect("enter-notify-event", self._on_win_enter)
        self.connect("leave-notify-event", self._on_win_leave)

        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height
        r = 16

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()

        cr.set_operator(cairo.OPERATOR_OVER)
        self._draw_rounded_rect(cr, 0, 0, w, h, r)

        accent = self._hex_to_rgb(self.config.get("color"))
        pat = cairo.LinearGradient(0, 0, w, h)
        pat.add_color_stop_rgba(0, 0.08, 0.08, 0.14, 0.92)
        pat.add_color_stop_rgba(0.5, 0.06, 0.06, 0.12, 0.90)
        pat.add_color_stop_rgba(1, accent[0] * 0.1, accent[1] * 0.1, accent[2] * 0.1, 0.88)
        cr.set_source(pat)
        cr.fill_preserve()

        cr.set_source_rgba(1, 1, 1, 0.04)
        cr.set_line_width(1)
        cr.stroke()

        return False

    def _draw_rounded_rect(self, cr, x, y, w, h, r):
        cr.move_to(x, y)
        cr.line_to(x + w, y)
        cr.arc(x + w - r, y + h - r, r, 0, 3.14159 / 2)
        cr.arc(x + r, y + h - r, r, 3.14159 / 2, 3.14159)
        cr.close_path()

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    # ── UI ──

    def _build_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.main_box)

        # --- Barra ---
        self.bar_event = Gtk.EventBox()
        self.bar_event.set_name("allan-bar")
        self.bar_event.connect("button-press-event", self._on_bar_click)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bar.set_margin_start(18)
        bar.set_margin_end(18)
        bar.set_margin_top(10)
        bar.set_margin_bottom(10)

        self.status_dot = Gtk.Label(label="●")
        self.status_dot.set_name("status-dot")
        bar.pack_start(self.status_dot, False, False, 0)

        self.title_label = Gtk.Label(label=self.config.get("name"))
        self.title_label.set_name("title-label")
        bar.pack_start(self.title_label, False, False, 0)

        self.status_label = Gtk.Label(label="Pronto")
        self.status_label.set_name("status-label")
        self.status_label.set_halign(Gtk.Align.END)
        bar.pack_end(self.status_label, False, False, 0)

        self.bar_event.add(bar)
        self.main_box.pack_start(self.bar_event, False, False, 0)

        # --- Painel ---
        self.panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.panel.set_name("allan-panel")
        self.panel.set_no_show_all(True)

        self._build_tabs()
        self._build_chat_tab()
        self._build_settings_tab()
        self._build_connections_tab()

        self.main_box.pack_start(self.panel, True, True, 0)

    # ── Tabs ──

    def _build_tabs(self):
        self.tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tab_bar.set_name("tab-bar")
        self.tab_bar.set_margin_start(12)
        self.tab_bar.set_margin_end(12)
        self.tab_bar.set_margin_top(4)
        self.tab_bar.set_margin_bottom(4)
        self.tab_bar.set_homogeneous(True)

        self.tab_buttons = {}
        tabs = [("chat", "Chat"), ("settings", "Config"), ("connections", "Conexões")]
        for tab_id, label in tabs:
            btn = Gtk.Button(label=label)
            btn.set_name(f"tab-{tab_id}")
            btn.connect("clicked", self._on_tab_click, tab_id)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            self.tab_bar.pack_start(btn, True, True, 0)
            self.tab_buttons[tab_id] = btn

        self.panel.pack_start(self.tab_bar, False, False, 0)

        self.tab_stack = Gtk.Stack()
        self.tab_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.tab_stack.set_transition_duration(150)
        self.panel.pack_start(self.tab_stack, True, True, 0)

    def _on_tab_click(self, btn, tab_id):
        self.current_tab = tab_id
        self.tab_stack.set_visible_child_name(tab_id)
        self._update_tab_styles()
        if tab_id == "connections":
            self._refresh_connections()

    def _update_tab_styles(self):
        for tid, btn in self.tab_buttons.items():
            ctx = btn.get_style_context()
            if tid == self.current_tab:
                ctx.add_class("tab-active")
            else:
                ctx.remove_class("tab-active")

    # ── Chat ──

    def _build_chat_tab(self):
        chat_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.chat_scroll = Gtk.ScrolledWindow()
        self.chat_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.chat_scroll.set_min_content_height(280)
        self.chat_scroll.set_max_content_height(380)

        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.chat_box.set_margin_start(12)
        self.chat_box.set_margin_end(12)
        self.chat_box.set_margin_top(8)
        self.chat_box.set_margin_bottom(8)
        self.chat_scroll.add(self.chat_box)
        chat_page.pack_start(self.chat_scroll, True, True, 0)

        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_box.set_margin_start(12)
        input_box.set_margin_end(12)
        input_box.set_margin_top(4)
        input_box.set_margin_bottom(12)

        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Pergunte algo...")
        self.entry.set_name("chat-input")
        self.entry.connect("activate", self._on_send)
        input_box.pack_start(self.entry, True, True, 0)

        send_btn = Gtk.Button(label="➤")
        send_btn.set_name("send-btn")
        send_btn.connect("clicked", self._on_send)
        input_box.pack_end(send_btn, False, False, 0)

        chat_page.pack_end(input_box, False, False, 0)

        self.tab_stack.add_named(chat_page, "chat")
        name = self.config.get("name")
        self._add_message(name, f"Olá! Sou o {name}. Como posso ajudar?", is_user=False)

    # ── Settings ──

    def _build_settings_tab(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(340)

        s = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        s.set_margin_start(16)
        s.set_margin_end(16)
        s.set_margin_top(14)
        s.set_margin_bottom(14)

        # Nome
        s.pack_start(self._label("NOME"), False, False, 0)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(self.config.get("name"))
        self.name_entry.set_name("s-input")
        self.name_entry.connect("changed", self._on_name_changed)
        s.pack_start(self.name_entry, False, False, 0)

        # Microfone
        s.pack_start(self._row_switch("Microfone", self.config.get("mic_enabled"),
                                       lambda sw, st: self.config.set("mic_enabled", st)), False, False, 0)

        # Hover
        s.pack_start(self._row_switch("Abrir com hover", self.config.get("hover_enabled"),
                                       lambda sw, st: self.config.set("hover_enabled", st)), False, False, 0)

        s.pack_start(Gtk.Separator(), False, False, 2)

        # Cor
        s.pack_start(self._label("COR"), False, False, 0)
        color_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        colors = ["#00ff88", "#00aaff", "#ff6b6b", "#ffd93d", "#c084fc", "#ff8c42", "#ff5ecf", "#44ffdd"]
        for c in colors:
            btn = Gtk.Button()
            btn.set_size_request(28, 28)
            provider = Gtk.CssProvider()
            css = f"""button {{
                background: {c};
                border-radius: 50%;
                border: 2px solid rgba(255,255,255,0.1);
                min-width: 24px; min-height: 24px;
                padding: 0;
            }}
            button:hover {{ border-color: white; }}"""
            provider.load_from_data(css.encode())
            btn.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
            btn.connect("clicked", self._on_color_pick, c)
            color_box.pack_start(btn, False, False, 0)
        s.pack_start(color_box, False, False, 0)

        # Posição
        s.pack_start(self._label("POSIÇÃO"), False, False, 0)
        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        positions = [("top", "⬆ Topo"), ("left", "⬅ Esquerda"), ("right", "➡ Direita"), ("bottom", "⬇ Embaixo")]
        self.pos_buttons = {}
        for pos_id, lbl in positions:
            btn = Gtk.ToggleButton(label=lbl)
            btn.set_name("pos-btn")
            if self.config.get("position") == pos_id:
                btn.set_active(True)
            btn.connect("toggled", self._on_position_changed, pos_id)
            pos_box.pack_start(btn, True, True, 0)
            self.pos_buttons[pos_id] = btn
        s.pack_start(pos_box, False, False, 0)

        # Tamanho
        s.pack_start(self._label("TAMANHO DA BARRA"), False, False, 0)
        self.size_combo = Gtk.ComboBoxText()
        self.size_combo.set_name("s-input")
        for sid, slbl in [("compact", "Compacto"), ("normal", "Normal"), ("wide", "Largo")]:
            self.size_combo.append(sid, slbl)
        self.size_combo.set_active_id(self.config.get("bar_size"))
        self.size_combo.connect("changed", self._on_bar_size_changed)
        s.pack_start(self.size_combo, False, False, 0)

        s.pack_start(Gtk.Separator(), False, False, 2)

        # Instruções
        s.pack_start(self._label("INSTRUÇÕES"), False, False, 0)
        self.instructions_view = Gtk.TextView()
        self.instructions_view.set_name("s-textarea")
        self.instructions_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.instructions_view.get_buffer().set_text(self.config.get("instructions"))
        self.instructions_view.get_buffer().connect("changed", self._on_instructions_changed)
        frame = Gtk.Frame()
        frame.set_name("s-frame")
        frame.add(self.instructions_view)
        frame.set_size_request(-1, 80)
        s.pack_start(frame, False, False, 0)

        # Modelo
        s.pack_start(self._label("MODELO"), False, False, 0)
        self.model_combo = Gtk.ComboBoxText()
        self.model_combo.set_name("s-input")
        self._refresh_model_list()
        self.model_combo.connect("changed", self._on_model_changed)
        s.pack_start(self.model_combo, False, False, 0)

        scroll.add(s)
        self.tab_stack.add_named(scroll, "settings")

    def _label(self, text):
        l = Gtk.Label(label=text)
        l.set_halign(Gtk.Align.START)
        l.set_name("s-label")
        return l

    def _row_switch(self, text, active, callback):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        l = Gtk.Label(label=text)
        l.set_name("s-row-label")
        box.pack_start(l, False, False, 0)
        sw = Gtk.Switch()
        sw.set_active(active)
        sw.set_halign(Gtk.Align.END)
        sw.connect("state-set", callback)
        box.pack_end(sw, False, False, 0)
        return box

    def _refresh_model_list(self):
        from core import ollama_manager as ollama
        self.model_combo.remove_all()
        models = ollama.list_models()
        current = self.config.get("model")
        for i, m in enumerate(models):
            self.model_combo.append_text(m)
            if m == current:
                self.model_combo.set_active(i)
        if not models:
            self.model_combo.append_text("(nenhum modelo)")
            self.model_combo.set_active(0)
        elif current not in models:
            self.model_combo.set_active(0)

    def _on_name_changed(self, entry):
        name = entry.get_text().strip()
        if name:
            self.config.set("name", name)
            self.title_label.set_text(name)

    def _on_color_pick(self, btn, color):
        self.config.set("color", color)
        self._apply_css()
        self.queue_draw()

    def _on_position_changed(self, btn, pos_id):
        if btn.get_active():
            self.config.set("position", pos_id)
            for pid, b in self.pos_buttons.items():
                if pid != pos_id:
                    b.set_active(False)
            self._reposition()

    def _on_bar_size_changed(self, combo):
        size = combo.get_active_id()
        self.config.set("bar_size", size)
        sizes = {"compact": 200, "normal": 280, "wide": 380}
        if not self.expanded:
            self.set_size_request(sizes.get(size, 280), -1)

    def _on_instructions_changed(self, buffer):
        start, end = buffer.get_bounds()
        self.config.set("instructions", buffer.get_text(start, end, False))

    def _on_model_changed(self, combo):
        model = combo.get_active_text()
        if model and model != "(nenhum modelo)":
            self.config.set("model", model)
            self.brain.set_model(model)

    # ── Connections ──

    def _build_connections_tab(self):
        self.conn_scroll = Gtk.ScrolledWindow()
        self.conn_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.conn_scroll.set_min_content_height(340)

        self.conn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.conn_box.set_margin_start(16)
        self.conn_box.set_margin_end(16)
        self.conn_box.set_margin_top(14)
        self.conn_box.set_margin_bottom(14)

        self.conn_scroll.add(self.conn_box)
        self.tab_stack.add_named(self.conn_scroll, "connections")

    def _refresh_connections(self):
        for child in self.conn_box.get_children():
            self.conn_box.remove(child)

        from core.connections import get_all_apps
        apps = get_all_apps(self.config)

        connected = [a for a in apps if a["connected"]]
        available = [a for a in apps if not a["connected"]]

        if connected:
            header = Gtk.Label(label="CONECTADOS")
            header.set_name("s-label")
            header.set_halign(Gtk.Align.START)
            header.set_margin_bottom(4)
            self.conn_box.pack_start(header, False, False, 0)

            for app in connected:
                self.conn_box.pack_start(self._build_connected_row(app), False, False, 0)

        if available:
            header = Gtk.Label(label="DISPONÍVEIS")
            header.set_name("s-label")
            header.set_halign(Gtk.Align.START)
            header.set_margin_top(8 if connected else 0)
            header.set_margin_bottom(4)
            self.conn_box.pack_start(header, False, False, 0)

            for app in available:
                self.conn_box.pack_start(self._build_available_row(app), False, False, 0)

        self.conn_box.show_all()

    def _build_connected_row(self, app):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_name("c-row")

        icon = Gtk.Label(label=app["icon"])
        icon.set_name("c-icon")
        row.pack_start(icon, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=app["label"])
        name.set_halign(Gtk.Align.START)
        name.set_name("c-name")
        info.pack_start(name, False, False, 0)

        if app["running"]:
            st = Gtk.Label(label="● Rodando")
            st.set_name("c-on")
        else:
            st = Gtk.Label(label="○ Disponível")
            st.set_name("c-off")
        st.set_halign(Gtk.Align.START)
        info.pack_start(st, False, False, 0)
        row.pack_start(info, True, True, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        if app["running"]:
            btn = Gtk.Button(label="Parar")
            btn.set_name("c-stop")
            btn.connect("clicked", self._on_conn_action, app["id"], "stop")
        else:
            btn = Gtk.Button(label="Abrir")
            btn.set_name("c-start")
            btn.connect("clicked", self._on_conn_action, app["id"], "start")
        btn.set_valign(Gtk.Align.CENTER)
        btn_box.pack_start(btn, False, False, 0)

        disc_btn = Gtk.Button(label="✕")
        disc_btn.set_name("c-disconnect")
        disc_btn.set_valign(Gtk.Align.CENTER)
        disc_btn.set_tooltip_text("Desconectar")
        disc_btn.connect("clicked", self._on_disconnect, app["id"])
        btn_box.pack_start(disc_btn, False, False, 0)

        row.pack_end(btn_box, False, False, 0)
        return row

    def _build_available_row(self, app):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_name("c-row")

        icon = Gtk.Label(label=app["icon"])
        icon.set_name("c-icon")
        row.pack_start(icon, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Gtk.Label(label=app["label"])
        name.set_halign(Gtk.Align.START)
        name.set_name("c-name")
        info.pack_start(name, False, False, 0)

        type_label = "PWA" if app["type"] == "pwa" else "App"
        st = Gtk.Label(label=f"○ {type_label} detectado")
        st.set_name("c-off")
        st.set_halign(Gtk.Align.START)
        info.pack_start(st, False, False, 0)
        row.pack_start(info, True, True, 0)

        btn = Gtk.Button(label="Conectar")
        btn.set_name("c-start")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_connect, app["id"])
        row.pack_end(btn, False, False, 0)

        return row

    def _on_connect(self, btn, app_id):
        from core.connections import connect_app
        connect_app(app_id, self.config)
        self._refresh_connections()

    def _on_disconnect(self, btn, app_id):
        from core.connections import disconnect_app
        disconnect_app(app_id, self.config)
        self._refresh_connections()

    def _on_conn_action(self, btn, app_id, action):
        from core.connections import launch_app, stop_app
        launch_app(app_id) if action == "start" else stop_app(app_id)
        GLib.timeout_add(1500, self._refresh_connections)

    # ── Hover (window-level) ──

    def _cancel_timer(self, attr):
        tid = getattr(self, attr, None)
        if tid:
            try:
                GLib.source_remove(tid)
            except Exception:
                pass
            setattr(self, attr, None)

    def _on_win_enter(self, widget, event):
        self._cancel_timer("_leave_timeout")
        if not self.expanded and self.config.get("hover_enabled"):
            self._cancel_timer("_hover_timeout")
            self._hover_timeout = GLib.timeout_add(200, self._expand)

    def _on_win_leave(self, widget, event):
        if event.detail == Gdk.NotifyType.INFERIOR:
            return
        self._cancel_timer("_hover_timeout")
        if self.expanded and not self.is_processing:
            self._leave_timeout = GLib.timeout_add(400, self._try_collapse)

    def _try_collapse(self):
        self._leave_timeout = None
        if self.is_processing:
            return False
        focus = self.get_focus()
        if focus and (focus == self.entry or focus == self.instructions_view):
            return False
        self._collapse()
        return False

    def _expand(self):
        self._hover_timeout = None
        if not self.expanded:
            self.expanded = True
            self.panel.set_no_show_all(False)
            self.panel.show_all()
            self.set_size_request(420, 500)
            self.resize(420, 500)
            self._update_tab_styles()
            GLib.idle_add(self._reposition)
        return False

    def _collapse(self):
        self.expanded = False
        self.panel.hide()
        self.panel.set_no_show_all(True)
        sizes = {"compact": 200, "normal": 280, "wide": 380}
        w = sizes.get(self.config.get("bar_size"), 280)
        self.set_size_request(w, -1)
        self.resize(w, 1)
        GLib.idle_add(self._reposition)

    def _on_bar_click(self, widget, event):
        if event.button == 1:
            self._expand() if not self.expanded else self._collapse()
        elif event.button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label="Limpar conversa")
            item.connect("activate", lambda _: self._clear_chat())
            menu.append(item)
            menu.append(Gtk.SeparatorMenuItem())
            item2 = Gtk.MenuItem(label="Sair")
            item2.connect("activate", lambda _: Gtk.main_quit())
            menu.append(item2)
            menu.show_all()
            menu.popup_at_pointer(event)

    # ── Chat messages ──

    def _add_message(self, sender, text, is_user=False):
        msg = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        msg.set_name("m-user" if is_user else "m-bot")
        msg.set_halign(Gtk.Align.END if is_user else Gtk.Align.START)

        head = Gtk.Label()
        head.set_markup(f"<small><b>{sender}</b></small>")
        head.set_halign(Gtk.Align.START)
        head.set_name("m-head")
        msg.pack_start(head, False, False, 0)

        body = Gtk.Label(label=text)
        body.set_line_wrap(True)
        body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        body.set_max_width_chars(42)
        body.set_halign(Gtk.Align.START)
        body.set_selectable(True)
        body.set_name("m-body")
        msg.pack_start(body, False, False, 0)

        self.chat_box.pack_start(msg, False, False, 0)
        msg.show_all()
        GLib.idle_add(self._scroll_bottom)
        return body

    def _scroll_bottom(self):
        adj = self.chat_scroll.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False

    def _clear_chat(self):
        for c in self.chat_box.get_children():
            self.chat_box.remove(c)
        self.brain.clear_history()
        name = self.config.get("name")
        self._add_message(name, "Conversa limpa.", is_user=False)

    def _on_send(self, _):
        text = self.entry.get_text().strip()
        if not text or self.is_processing:
            return
        self.entry.set_text("")
        if self.current_tab != "chat":
            self._on_tab_click(None, "chat")
        self._add_message("Você", text, is_user=True)
        self.status_label.set_text("Pensando...")
        self.is_processing = True
        threading.Thread(target=self._run_chat, args=(text,), daemon=True).start()

    def _run_chat(self, text):
        label = [None]

        def mk():
            label[0] = self._add_message(self.config.get("name"), "", is_user=False)
        GLib.idle_add(mk)

        import time
        time.sleep(0.05)

        full = ""
        try:
            for tok in self.brain.process_stream(text):
                full += tok
                def up(t=full):
                    if label[0]:
                        label[0].set_text(t)
                    self._scroll_bottom()
                GLib.idle_add(up)
        except Exception as e:
            full = f"Erro: {e}"
            GLib.idle_add(lambda: label[0].set_text(full) if label[0] else None)

        GLib.idle_add(lambda: (self.status_label.set_text("Pronto"), setattr(self, "is_processing", False)))

    def _hide_for_capture(self, hide):
        # Chamado da thread do chat: esconde o overlay para ele não sair na captura.
        import time
        done = threading.Event()

        def do():
            if hide:
                self.status_label.set_text("Olhando a tela...")
                self.hide()
            else:
                self.show()
                self.status_label.set_text("Pensando...")
            done.set()
            return False
        GLib.idle_add(do)
        done.wait(2)
        if hide:
            time.sleep(0.4)

    # ── CSS ──

    def _apply_css(self):
        a = self.config.get("color")
        css = f"""
        * {{ font-family: "Inter", "Cantarell", "Segoe UI", sans-serif; }}

        #allan-bar {{
            background: transparent;
            min-height: 38px;
        }}
        #status-dot {{ color: {a}; font-size: 11px; }}
        #title-label {{ color: rgba(255,255,255,0.9); font-weight: 600; font-size: 13px; letter-spacing: 0.5px; }}
        #status-label {{ color: rgba(255,255,255,0.35); font-size: 11px; }}

        #allan-panel {{ background: transparent; }}

        #tab-bar button {{
            color: rgba(255,255,255,0.4);
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 5px 10px;
            font-size: 11px;
            font-weight: 500;
        }}
        #tab-bar button:hover {{ color: rgba(255,255,255,0.7); background: rgba(255,255,255,0.05); }}
        #tab-bar button.tab-active {{ color: {a}; background: rgba(255,255,255,0.06); }}

        #chat-input {{
            background: rgba(255,255,255,0.06);
            color: rgba(255,255,255,0.9);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 8px 14px;
            font-size: 13px;
        }}
        #chat-input:focus {{ border-color: alpha({a}, 0.5); }}

        #send-btn {{
            background: {a};
            color: rgba(0,0,0,0.85);
            border: none;
            border-radius: 10px;
            padding: 6px 14px;
            font-size: 14px;
            font-weight: 700;
        }}

        #m-user {{
            background: alpha({a}, 0.12);
            border-radius: 12px 12px 4px 12px;
            padding: 8px 12px;
        }}
        #m-bot {{
            background: rgba(255,255,255,0.04);
            border-radius: 12px 12px 12px 4px;
            padding: 8px 12px;
        }}
        #m-head {{ color: alpha({a}, 0.7); }}
        #m-body {{ color: rgba(255,255,255,0.88); font-size: 13px; }}

        #s-label {{ color: rgba(255,255,255,0.35); font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }}
        #s-row-label {{ color: rgba(255,255,255,0.75); font-size: 13px; }}
        #s-input, #s-input * {{
            background: rgba(255,255,255,0.06);
            color: rgba(255,255,255,0.9);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 6px 10px;
        }}
        #s-frame {{ border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }}
        #s-textarea, #s-textarea text {{
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.85);
            font-size: 12px;
        }}

        separator {{ background: rgba(255,255,255,0.06); min-height: 1px; }}

        #pos-btn {{
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.5);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 5px;
            font-size: 11px;
        }}
        #pos-btn:checked {{ background: alpha({a}, 0.15); color: {a}; border-color: alpha({a}, 0.3); }}

        switch {{ background: rgba(255,255,255,0.1); border-radius: 12px; }}
        switch:checked {{ background: alpha({a}, 0.4); }}
        switch slider {{ background: white; border-radius: 50%; min-width: 16px; min-height: 16px; }}

        #c-row {{
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 10px 12px;
        }}
        #c-icon {{ font-size: 22px; }}
        #c-name {{ color: rgba(255,255,255,0.9); font-size: 13px; font-weight: 600; }}
        #c-on {{ color: {a}; font-size: 11px; }}
        #c-off {{ color: rgba(255,255,255,0.4); font-size: 11px; }}
        #c-miss {{ color: rgba(255,255,255,0.2); font-size: 11px; }}
        #c-start {{
            background: alpha({a}, 0.12);
            color: {a};
            border: 1px solid alpha({a}, 0.25);
            border-radius: 8px;
            padding: 4px 14px;
            font-size: 12px;
        }}
        #c-stop {{
            background: alpha(#ff6b6b, 0.12);
            color: #ff6b6b;
            border: 1px solid alpha(#ff6b6b, 0.25);
            border-radius: 8px;
            padding: 4px 14px;
            font-size: 12px;
        }}
        #c-disconnect {{
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.3);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 11px;
            min-width: 0;
        }}
        #c-disconnect:hover {{ color: #ff6b6b; border-color: alpha(#ff6b6b, 0.3); }}

        scrolledwindow {{ background: transparent; }}
        viewport {{ background: transparent; }}
        scrollbar {{ background: transparent; }}
        scrollbar slider {{ background: rgba(255,255,255,0.1); border-radius: 4px; min-width: 4px; }}
        """.encode()

        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
