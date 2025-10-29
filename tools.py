import os
from models import FileData

def collect_files(root_dir):
    file_list = []

    for root, dirs, files in os.walk(root_dir):
        for name in files:
            full_path = os.path.join(root, name)
            file_type = os.path.splitext(name)[1].lower().strip('.') or "unknown"

            file_data = FileData(name, full_path, file_type)
            file_list.append(file_data)

    return file_list

