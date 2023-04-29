import time
# from datetime import datetime


class Result:
    def __init__(self, line: str = ""):
        self.line = line
        self.time = time.time()
        self.parameters = {}
        self.command = None

    def __str__(self):
        return self.line
