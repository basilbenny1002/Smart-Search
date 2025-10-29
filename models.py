import string

class Tree:
    def __init__(self, value):
        self.value = value
        self.files = []
        for letter in string.ascii_lowercase:
            setattr(self, letter, None)

    def to_dict(self):
        data = {"value": self.value, "files": [f.to_dict() for f in self.files]}
        for letter in string.ascii_lowercase:
            child = getattr(self, letter)
            if child is not None:
                data[letter] = child.to_dict()
        return data

    @classmethod
    def from_dict(cls, data):
        node = cls(data["value"])
        node.files = [FileData.from_dict(f) if isinstance(f, dict) else f for f in data.get("files", [])]
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

    def to_dict(self):
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "length": self.length,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls(data["file_name"], data["file_path"], data["file_type"])
        obj.length = data.get("length", len(obj.file_name))
        return obj


