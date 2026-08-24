import uuid

import tzlocal


class Widget:
    widget_type = None

    def __init__(self, widget_id, x, y):
        self.widget_id = widget_id
        self.x = x
        self.y = y

    def to_json(self):
        return {
            'widget_id': self.widget_id,
            'widget_type': self.widget_type,
            'x': self.x,
            'y': self.y,
        }


class TimeWidget(Widget):
    widget_type = 'time'

    def __init__(self, widget_id, x, y, tz):
        super().__init__(widget_id, x, y)
        self.tz = tz

    def to_json(self):
        result = super().to_json()
        result['tz'] = self.tz
        return result


def build_default_widget() -> Widget:
    return TimeWidget(str(uuid.uuid4()), 0, 0, tzlocal.get_localzone_name())


def build_from_json(d) -> Widget:
    widget_type = d.pop('widget_type', None)
    if not widget_type:
        raise Exception(f'missing "widget_type" attribute in {d}')

    if widget_type == 'time':
        return TimeWidget(**d)
    raise Exception(f'unknown widget "{widget_type}"')
