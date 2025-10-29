
from tools import collect_files, generate_tree, search_tree, trees
from models import FileData, Tree
import json

loaded_trees = {}
ROOT_DIR = r"c:/"


generate_tree(ROOT_DIR)


for value, tree in enumerate(trees):
    with open("{value}tree.json", "w") as f:
        json.dump(tree.to_dict(), f, indent=2)

for letter in "abcdefghijklmnopqrstuvwxyz":
    with open("{value}tree.json") as f:
        loaded_root = Tree.from_dict(json.load(f))
        loaded_trees[letter] = loaded_root


trees.clear()
trees.update(loaded_trees)
results = search_tree("hehehe")
