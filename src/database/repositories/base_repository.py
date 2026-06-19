from src.database.d1_client import D1Client


class BaseRepository:
    def __init__(self):
        self.db = D1Client()