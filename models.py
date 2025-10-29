import string

class Tree:
    def __init__(self, value):
        self.value = value
        self.files = []
        for letter in string.ascii_lowercase:
            setattr(self, letter, None)

    def to_dict(self):
        data = {"value": self.value, "files": self.files}
        for letter in string.ascii_lowercase:
            child = getattr(self, letter)
            # if child is not None:
            data[letter] = child.to_dict()
        return data

    @classmethod
    def from_dict(cls, data):
        node = cls(data["value"])
        node.files = data["files"]
        for letter in string.ascii_lowercase:
            if letter in data:
                setattr(node, letter, cls.from_dict(data[letter]))
        return node

class FileData:
    def __init__(self, name: str, path: str, type: str):
        self.file_name = name
        self.file_path = path
        self.file_type = type
        self.length = len(self.file_name)

    def __lt__(self, other):
        return self.length < other.length



