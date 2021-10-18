import importlib
import inspect
import re

from .convert_rst_to_mdx import convert_rst_docstring_to_mdx


def find_object_in_package(object_name, package):
    """
    Find an object from its name inside a given package.
    
    Args:
    - **object_name** (`str`) -- The name of the object to retrieve.
    -- **package** (`types.ModuleType`) -- The package to look into.
    """
    path_splits = object_name.split(".")
    if path_splits[0] == package.__name__:
        path_splits = path_splits[1:]
    module = package
    for split in path_splits:
        module = getattr(module, split, None)
        if module is None:
            return
    return module


def get_shortest_path(obj, package):
    """
    Simplifies the path to `obj` to be the shortest possible, for instance if `obj` is in the main init of its
    package.
    """
    if not hasattr(obj, "__module__"):
        return None
    long_path = obj.__module__
    # Sometimes methods are defined in another module from the class (flax.struct.dataclass)
    if not long_path.startswith(package.__name__):
        return None
    long_name = obj.__qualname__ if hasattr(obj, "__qualname__") else obj.__name__
    short_name = long_name.split(".")[0]
    path_splits = long_path.split(".")
    idx = 0
    module = package
    while idx < len(path_splits) and not hasattr(module, short_name):
        idx += 1
        module = getattr(module, path_splits[idx])
    return ".".join(path_splits[:idx+1]) + "." + long_name


def get_type_name(typ):
    """
    Returns the name of the type passed, properly dealing with type annotions.
    """
    if hasattr(typ, "__qualname__"):
        return typ.__qualname__
    elif hasattr(typ, "__name__"):
        return typ.__name__
    name = str(typ)
    return re.sub(r"typing.Union\[(\S+), NoneType\]", r"typing.Optional[\1]", name)


def format_signature(obj):
    """
    Retrieves and properly formats the signature of a class, function or method.
    """
    try:
        signature = inspect.signature(obj)
    except ValueError:
        # TODO: This fails for ModelOutput. Check if this is normal.
        return ""
    params = []
    for param in signature.parameters.values():
        param_name = param.name
        if param.kind == inspect._ParameterKind.VAR_POSITIONAL:
            param_name = f"*{param_name}"
        elif param.kind == inspect._ParameterKind.VAR_KEYWORD:
            param_name = f"**{param_name}"
        formatted_param = param_name
        if param.annotation != inspect._empty:
            formatted_param += f": {get_type_name(param.annotation)}"
        if param.default != inspect._empty:
            formatted_param += f" = {param.default}"
        params.append(formatted_param)
    return ", ".join(params)


# Re pattern to catch :obj:`xx`, :class:`xx`, :func:`xx` or :meth:`xx`.
_re_rst_special_words = re.compile(r":(?:obj|func|class|meth):`([^`]+)`")
# Re pattern to catch things between double backquotes.
_re_double_backquotes = re.compile(r"(^|[^`])``([^`]+)``([^`]|$)")


def is_rst_docstring(docstring):
    """
    Returns `True` if `docstring` is written in rst.
    """
    if _re_rst_special_words.search(docstring) is not None:
        return True
    if _re_double_backquotes.search(docstring) is not None:
        return True
    return False


def document_object(object_name, package, full_name=True):
    """
    Writes the document of a function, class or method.
    
    Args:
    - **object_name** (`str`) -- The name of the object to document.
    - **package** (`types.ModuleType`) -- The package of the object.
    - **full_name** (`bool`, _optional_, defaults to `True`) -- Whether to write the full name of the object or not.
    """
    obj = find_object_in_package(object_name=object_name, package=package)
    anchor_name = get_shortest_path(obj, package)
    if full_name:
        # TODO: check if sphinx uses fulle name, object_name or anchor_name here.
        # name = f"{obj.__module__}.{obj.__name__}"
        name = anchor_name
    else:
        name = obj.__name__
    # Escape underscores in magic method names
    name = name.replace("_", "\_")
    
    prefix = "class " if isinstance(obj, type) else ""
    documentation = f"<a id='{anchor_name}'></a>\n" if anchor_name is not None else ""
    documentation += f"**{prefix}{name}**({format_signature(obj)})\n"
    if getattr(obj, "__doc__", None) is not None and len(obj.__doc__) > 0:
        object_doc = convert_rst_docstring_to_mdx(obj.__doc__)
        if is_rst_docstring(object_doc):
            object_doc = convert_rst_docstring_to_mdx(obj.__doc__)
        documentation += "\n" + object_doc + "\n"
    
    return documentation


def find_documented_methods(clas):
    """
    Find all the public methods of a given class that have a nonempty documentation, filtering the methods documented
    the exact same way in a superclass.
    """
    public_attrs = {a: getattr(clas, a) for a in dir(clas) if not a.startswith("_")}
    public_methods = {a: m for a, m in public_attrs.items() if callable(m)}
    documented_methods = {a: m for a, m in public_methods.items() if getattr(m, "__doc__", None) is not None and len(m.__doc__) > 0}
    
    superclasses = clas.mro()[1:]
    for superclass in superclasses:
        superclass_methods = {a: getattr(superclass, a) for a in documented_methods.keys() if hasattr(superclass, a)}
        documented_methods = {
            a: m for a, m in documented_methods.items() 
            if (
                a not in superclass_methods or 
                getattr(superclass_methods[a], "__doc__", None) is None or 
                m.__doc__ != superclass_methods[a].__doc__
            )
        }
    return list(documented_methods.keys())


def autodoc(object_name, package, methods=None, return_anchors=False):
    """
    Generates the documentation of an object, with a potential filtering on the methods for a class.
    
    Args:
    - **object_name** (`str`) -- The name of the function or class to document.
    - **package** (`types.ModuleType`) -- The package of the object.
    - **methods** (`List[str]`, _optional_) -- A list of methods to document if `obj` is a class. If nothing is passed,
      all public methods with a new docstring compared to the superclasses are documented. If a list of methods is
      passed and ou want to add all those methods, the key "all" will add them.
    - **return_anchors** (`bool`, _optional_, defaults to `False`) -- Whether or not to return the list of anchors
      generated.
    """
    obj = find_object_in_package(object_name=object_name, package=package)
    documentation = document_object(object_name=object_name, package=package)
    if return_anchors:
        anchors = [get_shortest_path(obj, package)]
    if isinstance(obj, type):
        documentation = document_object(object_name=object_name, package=package)
        if methods is None:
            methods = find_documented_methods(obj)
        elif "all" in methods:
            methods.remove("all")
            methods_to_add = find_documented_methods(obj)
            methods.extend([m for m in methods_to_add if m not in methods])
        for method in methods:
            method_doc = document_object(object_name=f"{object_name}.{method}", package=package, full_name=False)
            documentation += "\n<blockquote>" + method_doc + "</blockquote>"
            if return_anchors:
                anchors.append(f"{anchors[0]}.{method}")
    documentation = "<blockquote>\n" + documentation + "</blockquote>\n"

    return (documentation, anchors) if return_anchors else documentation
