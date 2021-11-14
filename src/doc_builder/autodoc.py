from collections import defaultdict
import inspect
import json
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


def remove_example_tags(text):
    tags = ['<exampletitle>', '</exampletitle>', '<example>', '</example>']
    for tag in tags:
        text = text.replace(tag, "")
    return text


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
    Retrieves the signature of a class, function or method.
    Returns `List(Dict(str, str))` (i.e. [{'do_lower_case', ' = True'}, ...])
    where `key` of `Dict` is f'{param_name}' & `value` of `Dict` is f': {annotation}  = {default}'
    """
    try:
        signature = inspect.signature(obj)
    except ValueError:
        # TODO: This fails for ModelOutput. Check if this is normal.
        return ""
    params = []

    for idx, param in enumerate(signature.parameters.values()):
        param_name = param.name
        if idx == 0:
            if param_name in ("self", "cls"):
                continue
        if param.kind == inspect._ParameterKind.VAR_POSITIONAL:
            param_name = f"*{param_name}"
        elif param.kind == inspect._ParameterKind.VAR_KEYWORD:
            param_name = f"**{param_name}"
        param_type_val = ""
        if param.annotation != inspect._empty:
            annotation = get_type_name(param.annotation)
            annotation = annotation.replace("<", "&amp;lt;")
            param_type_val += f": {annotation}"
        if param.default != inspect._empty:
            default = param.default
            default = repr(default)
            default = default.replace("<", "&amp;lt;")
            param_type_val += f" = {default}"
        params.append({'name':param_name, 'val':param_type_val})
    return params


_re_parameters = re.compile(r"<parameters>(.*)</parameters>", re.DOTALL)
_re_returns = re.compile(r"<returns>(.*)</returns>", re.DOTALL)
_re_returntype = re.compile(r"<returntype>(.*)</returntype>", re.DOTALL)
_re_example_tags = re.compile(r"(<exampletitle>|<example>)")


def parse_object_doc(object_doc):
    """
    Retrieves & parses the object_doc str into its separate sections 
    (description, parameters, returns, returntype).
    Retusn the parsed result as `Dict(str, str)`.
    """
    def closure1(match, tag):
        """
        This closure ...
        """
        match_str = match.group(1)
        examples_inside = _re_example_tags.search(match_str)
        if examples_inside:
            example_tag = examples_inside.group(1)
            match_str = match_str.replace(example_tag, f'</{tag}>{example_tag}', 1)
            return f'<{tag}>{match_str}'
        return f'<{tag}>{match_str}</{tag}>'

    def closure2(regex):
        """
        This closure ... 
        """
        nonlocal object_doc
        re_match = regex.search(object_doc)
        object_doc = regex.sub("", object_doc)
        return re_match.group(1).strip() if re_match else ""

    object_doc = _re_returns.sub(lambda m: closure1(m, 'returns'), object_doc)
    object_doc = _re_parameters.sub(lambda m: closure1(m, 'parameters'), object_doc)

    return defaultdict(str, **{ 
        "parameters": closure2(_re_parameters),
        "returns": closure2(_re_returns),
        "returntype": closure2(_re_returntype),
        "description": object_doc,
    })


_re_parametername = re.compile(r'\*\*(.*)\*\*', re.DOTALL)


def get_signature_component(name, signature, object_doc):
    """
    Returns the svelte `Docstring` component string. 
    
    Args:
    - **name** (`str`) -- The name of the function or class to document.
    - **signature** (`List(Dict(str,str))`) -- The signature of the object.
    - **object_doc** (`str`) -- The docstring of the the object.
    """
    parsed_obj_doc = parse_object_doc(object_doc) if object_doc is not None else defaultdict(str)
    description = parsed_obj_doc["description"]
    parameters = parsed_obj_doc["parameters"]
    return_description = parsed_obj_doc["returns"]
    returntype = parsed_obj_doc["returntype"]
    returns = {"type": returntype, "description": return_description}
    parameters = parameters.split('\n')

    params_description = []
    # greedy algorithm to find parameter name & its description
    param_name = None
    param_description = []
    def greedyHelper():
        nonlocal param_name, param_description, params_description
        if param_name:
            param_description = re.sub(' +', ' ', ' '.join(param_description))
            params_description.append({"name":param_name, "description": param_description})
    for line in parameters:
        param_name_ = _re_parametername.search(line)
        if param_name_:
            greedyHelper()
            param_name = param_name_.group(1)
            param_description = [line]
        else:
            param_description.append(line)
    greedyHelper()

    svelte_str = f'<Docstring hydrate-props={{{{name: "{name}", parameters:{json.dumps(signature)}, parametersDescription:{json.dumps(params_description)}, returns:{json.dumps(returns)} }}}} />'
    return svelte_str + f'\n{description}'


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


def document_object(object_name, package, page_info, full_name=True):
    """
    Writes the document of a function, class or method.
    
    Args:
    - **object_name** (`str`) -- The name of the object to document.
    - **package** (`types.ModuleType`) -- The package of the object.
    - **full_name** (`bool`, _optional_, defaults to `True`) -- Whether to write the full name of the object or not.
    """
    if page_info is None:
        page_info = {}
    if "package_name" not in page_info:
        page_info["package_name"] = package.__name__
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
    signature_name = prefix+name
    signature = format_signature(obj)
    object_doc = None
    if getattr(obj, "__doc__", None) is not None and len(obj.__doc__) > 0:
        object_doc = convert_rst_docstring_to_mdx(obj.__doc__, page_info)
        if is_rst_docstring(object_doc):
            object_doc = convert_rst_docstring_to_mdx(obj.__doc__, page_info)
    component = get_signature_component(signature_name, signature, object_doc)
    documentation += "\n" + component + "\n"
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


def autodoc(object_name, package, methods=None, return_anchors=False, page_info=None):
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
    - **page_info** (`Dict[str, str]`, *optional*) -- Some information about the page.
    """
    if page_info is None:
        page_info = {}
    if "package_name" not in page_info:
        page_info["package_name"] = package.__name__

    obj = find_object_in_package(object_name=object_name, package=package)
    documentation = document_object(object_name=object_name, package=package, page_info=page_info)
    if return_anchors:
        anchors = [get_shortest_path(obj, package)]
    if isinstance(obj, type):
        documentation = document_object(object_name=object_name, package=package, page_info=page_info)
        if methods is None:
            methods = find_documented_methods(obj)
        elif "all" in methods:
            methods.remove("all")
            methods_to_add = find_documented_methods(obj)
            methods.extend([m for m in methods_to_add if m not in methods])
        for method in methods:
            method_doc = document_object(
                object_name=f"{object_name}.{method}", package=package, page_info=page_info, full_name=False
            )
            documentation += '\n<div class="docstring">' + method_doc + "</div>"
            if return_anchors:
                anchors.append(f"{anchors[0]}.{method}")
    documentation = '<div class="docstring">\n' + documentation + "</div>\n"
    
    return (documentation, anchors) if return_anchors else documentation
