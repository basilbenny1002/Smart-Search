import os
from models import FileData, Tree

def collect_files(root_dir):
    file_list = []

    for root, dirs, files in os.walk(root_dir):
        for name in files:
            full_path = os.path.join(root, name)
            file_type = os.path.splitext(name)[1].lower().strip('.') or "unknown"

            file_data = FileData(name, full_path, file_type)
            file_list.append(file_data)

    return file_list

trees = {letter: Tree(letter) for letter in 'abcdefghijklmnopqrstuvwxyz'}

def check_letters(string: str):
    for char in string:
        if not char.isalpha():
            return False
    return True

def generate_tree(root_dir: str):
    for files in collect_files(root_dir=root_dir):
        if not check_letters(files.file_name):
            continue
        first_letter = files.file_name[0].lower()
        root_tree = trees[first_letter]  
        for i in range(1, len(files.file_name)):
            
            letter = files.file_name.lower()[i]
            node = getattr(root_tree, letter)
            if node is None:
                new_node = Tree(letter)
                setattr(root_tree, letter, new_node)
                root_tree = new_node
            elif node is not None and i < len(files.file_name) - 1:
                root_tree = node
                root_tree.files.append(files)
            elif node is not None:
                root_tree = node
                
def search_tree(prefix: str):
    first_letter = prefix[0].lower()
    current_node = trees.get(first_letter)

    for letter in prefix[1:]:
        if current_node is None:
            return []
        current_node = getattr(current_node, letter)

    if current_node:
        return current_node.files
    return []
            

            
