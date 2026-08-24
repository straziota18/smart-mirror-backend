import json
import os
import uuid
from typing import Any
import asyncio

from fastapi import WebSocket
from widget import build_from_json, build_default_widget

WIDGETS_FILE = os.path.join(os.path.dirname(__file__), "widgets.json")


class ClientManager:
    def __init__(self):
        self._lock = None
        self._clients: dict[str, WebSocket] = {}
        if os.path.exists(WIDGETS_FILE):
            with open(WIDGETS_FILE) as f:
                d = json.load(f)
                self._widgets = {
                    widget_id: build_from_json(d[widget_id])
                    for widget_id in d
                }
        else:
            base_widget = build_default_widget()
            self._widgets = {base_widget.widget_id: base_widget}
            self._persist_widgets()

    def _persist_widgets(self):
        with open(WIDGETS_FILE, 'w') as f:
            json.dump({
                widget_id: self._widgets[widget_id].to_json()
                for widget_id in self._widgets
            }, f)

    def unregister(self, user_id: str):
        self._clients.pop(user_id)

    async def update_widget(self, user_id: str, widget: Any):
        widget = build_from_json(widget)
        async with self._lock:
            self._widgets[widget.widget_id] = widget
            for client_id in self._clients:
                if client_id == user_id:
                    continue
                await self._clients[client_id].send_json('update_widget', widget.to_json())

    async def register_client(self, ws: WebSocket) -> str:
        if self._lock is None:
            self._lock = asyncio.Lock()
        await ws.accept()
        user_id = str(uuid.uuid4())
        self._clients[user_id] = ws
        await ws.send_json({
            'msg': 'widgets',
            'data': {
                widget_id: self._widgets[widget_id].to_json()
                for widget_id in self._widgets
            }
        })
        return user_id
