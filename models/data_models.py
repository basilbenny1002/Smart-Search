"""Data models for file and tree structures"""
import string


class Tree:
    """Tree structure for fast prefix-based file search"""
    
    # Mapping of Windows-valid symbols to safe attribute names
    # Windows allows: space ! # $ % & ' ( ) + , - . ; = @ [ ] ^ _ ` { } ~
    # Forbidden: \ / : * ? " < > |
    SYMBOL_MAP = {
        " ": "space", "!": "exclamation", "#": "hash", "$": "dollar",
        "%": "percent", "&": "ampersand", "'": "apostrophe", ".": "dot",
        "(": "lparen", ")": "rparen", "+": "plus", ",": "comma",
        "-": "dash", ";": "semicolon", "=": "equals", "@": "at",
        "[": "lbracket", "]": "rbracket", "^": "caret", "_": "underscore",
        "`": "backtick", "{": "lbrace", "}": "rbrace", "~": "tilde",
    }

    # Digits → safe names
    DIGIT_MAP = {str(i): f"num{i}" for i in range(10)}

    # Reverse mapping (for saving and loading)
    REVERSE_MAP = {v: k for k, v in {**SYMBOL_MAP, **DIGIT_MAP}.items()}

    def __init__(self, value):
        self.value = value
        self.files = []

        # Create letter attributes
        for ch in string.ascii_lowercase:
            setattr(self, ch, None)

        # Create digit and symbol attributes (safe names)
        for name in [*self.SYMBOL_MAP.values(), *self.DIGIT_MAP.values()]:
            setattr(self, name, None)

    def to_dict(self):
        """Convert tree into a serializable dict"""
        data = {
            "value": self.value,
            "files": [f.to_dict() for f in self.files],
        }

        # Serialize letters, digits, and symbols
        for ch in string.ascii_lowercase:
            child = getattr(self, ch)
            if child:
                data[ch] = child.to_dict()

        for name in [*self.SYMBOL_MAP.values(), *self.DIGIT_MAP.values()]:
            child = getattr(self, name)
            if child:
                data[name] = child.to_dict()

        return data

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Tree object from its dictionary form"""
        node = cls(data["value"])
        node.files = [FileData.from_dict(f) if isinstance(f, dict) else f for f in data.get("files", [])]

        for key, value in data.items():
            if key in ("value", "files"):
                continue
            if isinstance(value, dict):
                setattr(node, key, cls.from_dict(value))
        return node


class FileData:
    """Represents a file or folder with metadata"""
    
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
