import base64
import io
import os
import secrets
import urllib.parse

from gi.repository import Gio, GLib

MAX_SIDE = 1280


def capture_screen(timeout=30):
    """Captura a tela via xdg-desktop-portal (funciona no Wayland). Retorna PNG em bytes ou None."""
    ctx = GLib.MainContext.new()
    ctx.push_thread_default()
    try:
        return _capture(ctx, timeout)
    finally:
        ctx.pop_thread_default()


def _capture(ctx, timeout):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    token = f"allan_{secrets.token_hex(6)}"
    sender = bus.get_unique_name()[1:].replace(".", "_")
    handle = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

    loop = GLib.MainLoop.new(ctx, False)
    result = {}

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        code, results = params.unpack()
        if code == 0:
            result["uri"] = results.get("uri")
        loop.quit()

    sub = bus.signal_subscribe(
        "org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request", "Response",
        handle, None, Gio.DBusSignalFlags.NONE, on_response,
    )
    try:
        bus.call_sync(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot", "Screenshot",
            GLib.Variant("(sa{sv})", ("", {
                "handle_token": GLib.Variant("s", token),
                "interactive": GLib.Variant("b", False),
            })),
            None, Gio.DBusCallFlags.NONE, -1, None,
        )
        timer = GLib.timeout_source_new_seconds(timeout)
        timer.set_callback(lambda *_: loop.quit() or False)
        timer.attach(ctx)
        loop.run()
        timer.destroy()
    except GLib.Error:
        return None
    finally:
        bus.signal_unsubscribe(sub)

    uri = result.get("uri")
    if not uri:
        return None
    path = urllib.parse.unquote(urllib.parse.urlparse(uri).path)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return _shrink(data)


def _shrink(png_bytes):
    try:
        from PIL import Image
    except ImportError:
        return png_bytes
    im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def capture_screen_b64(timeout=30):
    data = capture_screen(timeout)
    return base64.b64encode(data).decode() if data else None
