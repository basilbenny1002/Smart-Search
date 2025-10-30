from tools import  generate_tree, trees
from models import FileData, Tree
import json
from pyuac import main_requires_admin
@main_requires_admin
def main():
    loaded_trees = {}
    ROOT_DIR = r"c:/"


    generate_tree(ROOT_DIR)


    for letter, tree in trees.items():
        with open(rf"trees/{letter}tree.json", "w") as f:
            json.dump(tree.to_dict(), f, indent=2)
            
if __name__ == "__main__":
    main()

# for letter in "abcdefghijklmnopqrstuvwxyz":
#     with open(f"./trees/{letter}tree.json") as f:
#         loaded_root = Tree.from_dict(json.load(f))
#         loaded_trees[letter] = loaded_root

# trees.clear()
# trees.update(loaded_trees)
# results = search_tree("hehehe")