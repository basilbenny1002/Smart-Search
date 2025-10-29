class Tree:
    def __init__(self, value):
        self.value = value
        self.files = {}
        self.a = None
        self.b = None
        self.c = None
        self.d = None



class FileData:
    def __init__(self, name: str, path: str, type: str):
        self.file_name = name
        self.file_path = path
        self.file_type = type
        self.length = len(self.file_name)

    def __lt__(self, other):
        return self.length < other.length



