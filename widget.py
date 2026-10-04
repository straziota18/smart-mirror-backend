import random
import uuid
from typing import Literal

import tzlocal

WidgetType = Literal['time', 'date']


class Widget:
    widget_type: WidgetType = None

    def __init__(self, widget_id, x, y, size):
        self.widget_id = widget_id
        self.size = size
        self.x = x
        self.y = y

    def to_json(self):
        return {
            'widget_id': self.widget_id,
            'widget_type': self.widget_type,
            'size': self.size,
            'x': self.x,
            'y': self.y,
        }


class AbstractTimeWidget(Widget):

    def __init__(self, widget_id, x, y, size, tz=tzlocal.get_localzone_name()):
        super().__init__(widget_id, x, y, size)
        self.tz = tz

    def to_json(self):
        result = super().to_json()
        result['tz'] = self.tz
        return result


class TimeWidget(AbstractTimeWidget):
    widget_type = 'time'


class DateWidget(AbstractTimeWidget):
    widget_type = 'date'


def build_widget(
        widget_type: WidgetType,
        **kwargs
) -> Widget:
    widget_id = str(uuid.uuid4())
    rand_x = random.randint(0, 80) / 100
    rand_y = random.randint(0, 80) / 100
    if widget_type == 'time':
        return TimeWidget(
            widget_id,
            rand_x,
            rand_y,
            kwargs.pop('size', 10),
            **kwargs
        )
    if widget_type == 'date':
        return DateWidget(
            widget_id,
            rand_x,
            rand_y,
            kwargs.pop('size', 10),
            **kwargs
        )
    if widget_type == 'weather':
        return WeatherWidget(
            widget_id,
            rand_x,
            rand_y,
            kwargs.pop('size', 10),
            **kwargs
        )
    raise Exception(f'unknown widget "{widget_type}"')


class WeatherWidget(Widget):
    widget_type = 'weather'

    def __init__(self, widget_id, x, y, size, city, unit):
        super().__init__(widget_id, x, y, size)
        self.city = city
        self.unit = unit

    def to_json(self):
        result = super().to_json()
        result['unit'] = self.unit
        result['city'] = self.city
        return result


def build_from_json(d) -> Widget:
    widget_type = d.pop('widget_type', None)
    if not widget_type:
        raise Exception(f'missing "widget_type" attribute in {d}')

    if widget_type == 'time':
        return TimeWidget(**d)
    if widget_type == 'date':
        return DateWidget(**d)
    if widget_type == 'weather':
        return WeatherWidget(**d)
    raise Exception(f'unknown widget "{widget_type}"')
