import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from httpx import AsyncClient

from client_manager import ClientManager
from weather_client import WeatherLocation

client_manager = ClientManager()
http_client = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http_client
    http_client = AsyncClient()
    await http_client.__aenter__()
    await client_manager.init_manager(http_client)
    yield
    await client_manager.close_manager()
    await http_client.__aexit__()


app = FastAPI(lifespan=lifespan)

if 'ANGULAR_DIST_PATH' in os.environ:
    ANGULAR_DIST_PATH = os.environ['ANGULAR_DIST_PATH']
else:
    ANGULAR_DIST_PATH = os.path.join(os.path.dirname(__file__), 'dist', 'browser')


@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    user_id = await client_manager.register_client(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data['msg'] == 'update_widget':
                await client_manager.update_widget(user_id, data['data'])
            if data['msg'] == 'new_widget':
                await client_manager.new_widget(data['data'])
            if data['msg'] == 'delete_widget':
                await client_manager.delete_widget(data['data'])
    except WebSocketDisconnect:
        client_manager.unregister(user_id)


@app.get('/search-city')
async def search_city(city: str) -> list[WeatherLocation]:
    return await client_manager.search_cities(http_client, city)


if os.path.exists(ANGULAR_DIST_PATH):
    assets_path = os.path.join(ANGULAR_DIST_PATH, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")


    @app.get('/{full_path:path}')
    async def serve_angular_app(full_path: str):
        file_path = os.path.join(ANGULAR_DIST_PATH, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(ANGULAR_DIST_PATH, "index.html"))
else:
    print('Angular assets file not found', file=sys.stderr)

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8080)
