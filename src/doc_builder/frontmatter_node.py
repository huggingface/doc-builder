import yaml

class FrontmatterNode:
    """
    A helper class that is used in generating frontmatter for mdx files.

    This class is a typical graph node class, which allows it to model
    markdown header hierarchy (i.e. h2 belongs to h1 above it).
    """

    def __init__(self, title, local):
        self.title = title
        self.local = local
        self.children = []

    def add_child(self, child, header_level):
        parent = self
        nested_level = header_level-2
        while nested_level:
            if not parent.children:
                parent.children.append(FrontmatterNode(None, None))
            parent = parent.children[-1]
            nested_level -= 1
        parent.children.append(child)

    def get_frontmatter(self):
        self._remove_null_nodes()
        frontmatter_yaml = yaml.dump(self._dictionarify(), allow_unicode=True).replace('\\U0001F917','🤗')
        return f'---\n{frontmatter_yaml}---\n'

    def _remove_null_nodes(self):
        if len(self.children) == 1 and self.children[0].title is None:
            child_children = self.children[0].children
            self.children = child_children
        for section in self.children:
            section._remove_null_nodes()

    def _dictionarify(self):
        if not self.children:
            return {'title': self.title, 'local': self.local}
        children = [section._dictionarify() for section in self.children]
        return {'title': self.title, 'local': self.local, 'sections': children }
