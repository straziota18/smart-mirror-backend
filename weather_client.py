import datetime
import logging

import pytz
from httpx import AsyncClient
from pydantic.dataclasses import dataclass


@dataclass
class WeatherLocation:
    id: str
    name: str
    country: str
    additional_data: str
    longitude: float
    latitude: float
    timezone: str


@dataclass
class WeatherForecast:
    current_temp: float
    current_code: int
    min_temp: float
    max_temp: float
    umbrella_3h: bool
    umbrella_today: bool


async def search_city(client: AsyncClient, search_str: str) -> list[WeatherLocation]:
    logging.log(logging.INFO, f'Requesting Open Meteo API - Searching cities matching "{search_str}"')
    response = await client.get(
        'https://geocoding-api.open-meteo.com/v1/search',
        params={'name': search_str}
    )
    data = response.json()
    return [
        WeatherLocation(it['id'], it['name'], it['country'], it['admin1'], it['longitude'], it['latitude'])
        for it in data['results']
    ]


async def build_forecast(
        client: AsyncClient,
        location: WeatherLocation
) -> WeatherForecast:
    logging.log(logging.INFO, f'Requesting Open Meteo API - Recovering forecast for "{location.id}"')
    response = await client.get(
        'https://api.open-meteo.com/v1/forecast',
        params={
            'latitude': location.latitude,
            'longitude': location.longitude,
            'hourly': 'apparent_temperature,precipitation_probability,precipitation',
            'current': 'apparent_temperature,precipitation,weather_code',
            'temperature_unit': 'celsius',
        }
    )
    data = response.json()
    # JSON format available at https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&hourly=apparent_temperature,precipitation_probability,precipitation,cloud_cover&current=precipitation,apparent_temperature,cloud_cover
    gmt_tz = pytz.timezone('GMT')
    tz = pytz.timezone(location.timezone)
    now = datetime.datetime.now(tz=tz)
    sliced_data = [
        {
            'apparent_temperature': at,
            'umbrella_needed': pp * p > 0.2,
            'is_forecast': datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M').replace(tzinfo=gmt_tz).astimezone(tz) > now
        }
        for dt, at, pp, p in zip(
            data['hourly']['time'],
            data['hourly']['apparent_temperature'],
            data['hourly']['precipitation_probability'],
            data['hourly']['precipitation'],
        )
        if datetime.datetime.strptime(dt, '%Y-%m-%dT%H:%M').replace(tzinfo=gmt_tz).astimezone(tz).date() == now.date()
    ]
    rain_today = any(it['umbrella_needed'] for it in sliced_data)
    rain_3h = any(it['umbrella_needed'] for it in [iit for iit in sliced_data if iit['is_forecast']][:3])
    return WeatherForecast(
        data['current']['apparent_temperature'],
        data['current']['weather_code'],
        min(it['apparent_temperature'] for it in sliced_data),
        max(it['apparent_temperature'] for it in sliced_data),
        rain_3h,
        rain_today,
    )
