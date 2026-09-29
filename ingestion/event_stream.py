class EventStream:

    def __init__(self, events: list):
        self._events = sorted(events, key=lambda e: e['timestamp'])
        self._index = 0

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        if self._index >= len(self._events):
            raise StopIteration
        event = self._events[self._index]
        self._index += 1
        return event

    def __len__(self):
        return len(self._events)

    @property
    def events(self):
        return self._events