"""Loopback preview server shared by CLI and browser checks."""

from http.server import ThreadingHTTPServer


class PreviewServer(ThreadingHTTPServer):
    # Modern browsers open several asset connections at once. Avoid the small
    # stdlib default backlog dropping simultaneous image/font connections.
    request_queue_size = 128
