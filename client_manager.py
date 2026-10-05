import asyncio
import datetime
import json
import os
import uuid
from contextlib import suppress
from typing import Any

from fastapi import WebSocket
from httpx import AsyncClient

from weather_client import WeatherLocation, search_city, build_forecast
from widget import build_from_json, build_widget, WeatherWidget

WIDGETS_FILE = os.path.join(os.path.dirname(__file__), "widgets.json")
WEATHER_DB_FILE = os.path.join(os.path.dirname(__file__), "weather_data.json")


class ClientManager:
    def __init__(self):
        self._widgets_lock = None
        self._weather_lock = None
        self._clients: dict[str, WebSocket] = {}
        if os.path.exists(WIDGETS_FILE):
            with open(WIDGETS_FILE) as f:
                d = json.load(f)
                self._widgets = {
                    widget_id: build_from_json(d[widget_id])
                    for widget_id in d
                }
        else:
            base_widget = build_widget('time')
            self._widgets = {base_widget.widget_id: base_widget}
            self._persist_widgets()
        if os.path.exists(WEATHER_DB_FILE):
            with open(WEATHER_DB_FILE) as f:
                d = json.load(f)
                self._weather_data = d
        else:
            self._weather_data = {'searches': {}, 'locations': {}}
            self._persist_weather_db()
        self._weather_refresh_task = None
        self._weather_state = {}

    async def init_manager(self, client: AsyncClient):
        if self._widgets_lock is None:
            self._widgets_lock = asyncio.Lock()
        if self._weather_lock is None:
            self._weather_lock = asyncio.Lock()

        self._weather_refresh_task = asyncio.create_task(self._refresh_weather_data(client))

    @staticmethod
    async def _sleep_until_next_quarter_hour():
        now = datetime.datetime.now()
        minutes_to_add = 15 - (now.minute % 15)
        next_ts = now + datetime.timedelta(minutes=minutes_to_add)
        next_ts.replace(second=0, microsecond=0)
        while now < next_ts:
            await asyncio.sleep((next_ts - now).total_seconds())
            now = datetime.datetime.now()

    async def _refresh_weather_data(self, client: AsyncClient):
        for widget_id in self._widgets:
            widget = self._widgets[widget_id]
            if self._widgets[widget_id].widget_type != 'weather':
                continue
            assert isinstance(widget, WeatherWidget)
            location = self._weather_data['locations'][widget.open_meteo_id]
            data = await build_forecast(client, location)
            self._weather_state[widget_id] = data

        await self._dispatch_active_state()
        await self._sleep_until_next_quarter_hour()

    async def _dispatch_active_state(self, user_id: str = None):
        await asyncio.gather(*(
            self._clients[client_id].send_json({'msg': 'weather_notif', 'data': self._weather_data})
            for client_id in self._clients
            if user_id is None or client_id == user_id
        ))

    async def close_manager(self):
        self._weather_refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._weather_refresh_task

    def _persist_weather_db(self):
        with open(WEATHER_DB_FILE, 'w') as f:
            json.dump(self._weather_data, f)

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
        async with self._widgets_lock:
            self._widgets[widget.widget_id] = widget
            await asyncio.gather(*(
                self._clients[client_id].send_json({'msg': 'update_widget', 'data': widget.to_json()})
                for client_id in self._clients
                if client_id != user_id
            ))
            self._persist_widgets()

    async def delete_widget(self, widget_id: str):
        async with self._widgets_lock:
            self._widgets.pop(widget_id, None)
            await asyncio.gather(*(
                self._clients[client_id].send_json({'msg': 'delete_widget', 'data': widget_id})
                for client_id in self._clients
            ))
            self._persist_widgets()

    async def new_widget(self, data):
        widget = build_widget(**data)
        async with self._widgets_lock:
            self._widgets[widget.widget_id] = widget
            await asyncio.gather(*(
                self._clients[client_id].send_json({'msg': 'update_widget', 'data': widget.to_json()})
                for client_id in self._clients
            ))
            self._persist_widgets()

    async def search_cities(self, client: AsyncClient, search: str) -> list[WeatherLocation]:
        lower_search = search.lower()

        async with self._weather_lock:
            if lower_search in self._weather_data['searches']:
                return self._weather_data['searches'][lower_search]
            data = await search_city(client, lower_search)
            self._weather_data['searches'][lower_search] = data
            self._persist_weather_db()
            return data

    async def register_client(self, ws: WebSocket) -> str:
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
        await self._dispatch_active_state(user_id)
        return user_id
