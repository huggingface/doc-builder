#!/usr/bin/env python3
"""
Script to strip Python files to only keep docstrings and signatures.
Removes implementations, unused imports, and decorators (except docstring-related ones).

This script processes Python files to:
1. Replace all function and class implementations with 'pass', preserving docstrings
2. Remove all decorators except those matching the pattern *doc*
3. Remove all functions and classes without docstrings or docstring-related decorators
4. Remove unused dependencies/imports from the source files
5. Handle conditional imports (like 'if is_vision_available()') correctly

Usage:
    # Process a single file
    uv run python strip_to_docstrings.py path/to/file.py
    
    # Process an entire directory recursively
    uv run python strip_to_docstrings.py path/to/directory
    
    # Dry run to see what would be processed without making changes
    uv run python strip_to_docstrings.py path/to/directory --dry-run

Example:
    uv run python strip_to_docstrings.py testdir/transformers

Notes:
    - Dataclass field definitions are preserved as they are part of the class structure
    - Type annotations in function signatures are preserved
    - Conditional import blocks are removed if all imports within them are unused
    - Module-level docstrings are preserved
"""

import ast
import os
import sys
import argparse
import re
from pathlib import Path
from typing import Set, List, Optional


def replace_cross_directory_imports(source: str, skip_dirs: Set[str]) -> str:
    """Replace imports from skipped directories with harmless stubs."""
    pattern = re.compile(r'^(?P<indent>\s*)from\s+(?P<module>[\.\w]+)\s+import\s+(?P<names>.+)$')
    lines = source.split('\n')
    new_lines = []
    for line in lines:
        match = pattern.match(line)
        if match:
            module_path = match.group('module')
            names_part = match.group('names').split('#')[0].strip()
            indent = match.group('indent')
            should_stub = any(f'.{skip_dir}' in module_path or module_path.startswith(f'{skip_dir}.') or module_path.endswith(f'.{skip_dir}') for skip_dir in skip_dirs)
            if should_stub:
                names = [n.strip() for n in names_part.split(',') if n.strip()]
                for name in names:
                    base_name = name.split(' as ')[-1].strip()
                    new_lines.append(f"{indent}{base_name} = None  # stripped re-export from {module_path}")
                continue
        new_lines.append(line)
    return '\n'.join(new_lines)


def patch_reexports(source: str, skip_dirs: Set[str]) -> str:
    return replace_cross_directory_imports(source, skip_dirs)


class DocstringPreserver(ast.NodeTransformer):
    """
    AST transformer that:
    1. Removes function/class implementations, keeping only docstrings
    2. Removes decorators except docstring-related ones (*doc*)
    3. Removes functions/classes without docstrings or docstring decorators
    4. Tracks used names for import cleanup
    5. Converts type annotations to strings (forward references)
    6. Removes backend requirement checks (is_torch_available, etc.)
    """
    
    def __init__(self):
        self.used_names: Set[str] = set()
        self.used_in_annotations: Set[str] = set()
        self.to_remove: List[ast.AST] = []
        self.backend_check_functions = {
            'is_torch_available', 'is_tf_available', 'is_flax_available',
            'is_vision_available', 'is_torchvision_available', 'is_scipy_available',
            'is_cv2_available', 'is_sentencepiece_available', 'is_tokenizers_available',
            'is_torch_fx_available', 'is_accelerate_available', 'is_safetensors_available',
            'is_torchvision_v2_available', 'is_peft_available', 'is_deepspeed_available',
            'is_fairscale_available', 'is_torch_xla_available'
        }
    
    def visit_Module(self, node):
        """Process module and collect names from module-level code."""
        # First, walk through all module-level statements to collect used names
        # This includes setup() calls, variable assignments, etc.
        # But skip backend checks
        new_body = []
        for item in node.body:
            # Skip conditional imports based on backend availability
            if isinstance(item, ast.If) and self._is_backend_check(item.test):
                # Skip this entire if block
                continue
            
            if isinstance(item, (ast.Expr, ast.Assign, ast.AnnAssign)):
                # Collect names from module-level expressions and assignments
                for n in ast.walk(item):
                    if isinstance(n, ast.Name):
                        self.used_names.add(n.id)
            
            new_body.append(item)
        
        node.body = new_body
        
        # Now do the normal visiting
        self.generic_visit(node)
        return node
    
    def _is_backend_check(self, node):
        """Check if this is a backend availability check."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id in self.backend_check_functions
        return False
        
    def has_docstring(self, node) -> bool:
        """Check if a function or class has a docstring."""
        if not hasattr(node, 'body') or not node.body:
            return False
        first_stmt = node.body[0]
        if isinstance(first_stmt, ast.Expr):
            if isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
                return True
            # For compatibility with older Python versions
            if hasattr(ast, 'Str') and isinstance(first_stmt.value, ast.Str):
                return True
        return False
    
    def has_doc_decorator(self, node) -> bool:
        """Check if node has a docstring-related decorator."""
        if not hasattr(node, 'decorator_list'):
            return False
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name and 'doc' in decorator_name.lower():
                return True
        return False
    
    def _get_decorator_name(self, decorator) -> Optional[str]:
        """Extract decorator name from various decorator types."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return None
    
    def _filter_decorators(self, decorator_list):
        """Keep only docstring-related decorators."""
        filtered = []
        for decorator in decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name and 'doc' in decorator_name.lower():
                filtered.append(decorator)
                # Track names used in doc decorators - these are ACTUAL uses, not annotations
                for node in ast.walk(decorator):
                    if isinstance(node, ast.Name):
                        self.used_names.add(node.id)
        return filtered
    
    def _create_minimal_body(self, node, return_true: bool = False):
        """Create minimal body with just docstring (if exists) and pass or return True."""
        new_body = []
        
        # Keep docstring if it exists
        if self.has_docstring(node):
            new_body.append(node.body[0])
        
        # Add return True for backend checks, otherwise pass
        if return_true:
            new_body.append(ast.Return(value=ast.Constant(value=True)))
        else:
            new_body.append(ast.Pass())
        
        return new_body
    
    def _stringify_annotation(self, annotation):
        """Convert an annotation to a string constant (forward reference)."""
        if annotation is None:
            return None
        # Convert the annotation AST to source code string
        try:
            annotation_str = ast.unparse(annotation)
        except AttributeError:
            # Python < 3.9
            import astor
            annotation_str = astor.to_source(annotation).strip()
        return ast.Constant(value=annotation_str)
    
    def _collect_and_stringify_annotation(self, annotation):
        """Collect names from annotation and return stringified version."""
        if annotation is None:
            return None
        # Collect names used in this annotation
        for n in ast.walk(annotation):
            if isinstance(n, ast.Name):
                self.used_in_annotations.add(n.id)
        # Return stringified version
        return self._stringify_annotation(annotation)
    
    def _collect_names_from_node(self, node):
        """Stringify annotations and track which names are used only in annotations."""
        # Handle function/method arguments
        if hasattr(node, 'args') and node.args:
            for arg in node.args.args:
                if arg.annotation:
                    arg.annotation = self._collect_and_stringify_annotation(arg.annotation)
            if node.args.vararg and node.args.vararg.annotation:
                node.args.vararg.annotation = self._collect_and_stringify_annotation(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation:
                node.args.kwarg.annotation = self._collect_and_stringify_annotation(node.args.kwarg.annotation)
            for arg in node.args.kwonlyargs:
                if arg.annotation:
                    arg.annotation = self._collect_and_stringify_annotation(arg.annotation)
        
        # Handle return annotation
        if hasattr(node, 'returns') and node.returns:
            node.returns = self._collect_and_stringify_annotation(node.returns)
    
    def visit_FunctionDef(self, node):
        """Process function definitions."""
        # Check if function should be kept
        has_doc = self.has_docstring(node)
        has_doc_dec = self.has_doc_decorator(node)
        
        # Only remove truly private/internal functions
        # Keep public API functions even without docstrings (they might be referenced in docs)
        is_private = node.name.startswith('_')
        is_test = node.name.startswith('test_')
        
        if not has_doc and not has_doc_dec and (is_private or is_test):
            # Only remove private/test functions without docstrings
            return None
        
        # Filter decorators
        node.decorator_list = self._filter_decorators(node.decorator_list)
        
        # Collect names from annotations
        self._collect_names_from_node(node)
        
        # Replace body with minimal version
        force_return_true = node.name in self.backend_check_functions
        node.body = self._create_minimal_body(node, return_true=force_return_true)
        
        return node
    
    def visit_AsyncFunctionDef(self, node):
        """Process async function definitions."""
        return self.visit_FunctionDef(node)
    
    def visit_ClassDef(self, node):
        """Process class definitions."""
        # Check if class should be kept
        has_doc = self.has_docstring(node)
        has_doc_dec = self.has_doc_decorator(node)
        
        # Only remove truly private/internal classes
        # Keep public API classes even without docstrings (they might be referenced in docs)
        is_private = node.name.startswith('_')
        
        if not has_doc and not has_doc_dec and is_private:
            # Only remove private classes without docstrings
            return None
        
        # Check if this is a dataclass or similar (has @dataclass decorator)
        is_dataclass = any(
            self._get_decorator_name(dec) in ('dataclass', 'attr.s', 'attrs', 'define')
            for dec in node.decorator_list
        )
        
        # Filter decorators (but keep all for dataclasses as they're structural)
        if is_dataclass:
            # For dataclasses, keep all decorators and collect names from them
            for decorator in node.decorator_list:
                for n in ast.walk(decorator):
                    if isinstance(n, ast.Name):
                        self.used_names.add(n.id)
        else:
            node.decorator_list = self._filter_decorators(node.decorator_list)
        
        # Remove all base classes (inheritance) - we only need signatures
        # This will also help remove more unused imports
        node.bases = []
        node.keywords = []  # Remove metaclass and other class keywords
        
        # Process class body
        new_body = []
        
        # Keep docstring if exists
        if has_doc:
            new_body.append(node.body[0])
        
        # Process class items
        for item in node.body[1:] if has_doc else node.body:
            # For dataclasses, keep AnnAssign (field definitions)
            if is_dataclass and isinstance(item, ast.AnnAssign):
                # Stringify annotation and track annotation-only usage
                if item.annotation:
                    item.annotation = self._collect_and_stringify_annotation(item.annotation)
                
                # Handle default values
                if item.value:
                    # Check if default value references attributes (e.g., Enum.VALUE)
                    # These will fail at import time since we strip class bodies to 'pass'
                    has_attribute_access = any(isinstance(n, ast.Attribute) for n in ast.walk(item.value))
                    
                    if has_attribute_access:
                        # Replace problematic defaults with None
                        # This prevents AttributeError when enum/class values don't exist
                        # while maintaining valid dataclass field ordering (can't remove defaults)
                        item.value = ast.Constant(value=None)
                    else:
                        # Keep simple defaults (numbers, strings, None, True/False, etc.)
                        # Collect names from the value (these are actual uses)
                        for n in ast.walk(item.value):
                            if isinstance(n, ast.Name):
                                self.used_names.add(n.id)
                
                new_body.append(item)
            # Process methods and nested classes
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                transformed = self.visit(item)
                if transformed is not None:
                    new_body.append(transformed)
            # Keep other annotated assignments (type hints)
            elif isinstance(item, ast.AnnAssign):
                # Stringify annotation
                if item.annotation:
                    item.annotation = self._collect_and_stringify_annotation(item.annotation)
                new_body.append(item)
        
        # If no items in body, add pass
        if len(new_body) == 0 or (len(new_body) == 1 and isinstance(new_body[0], ast.Expr)):
            new_body.append(ast.Pass())
        
        node.body = new_body
        return node


class ImportCleaner(ast.NodeTransformer):
    """Remove unused imports and clean up conditional import blocks."""
    
    def __init__(self, used_names: Set[str], used_in_annotations: Set[str], is_setup_py: bool = False):
        self.used_names = used_names
        self.used_in_annotations = used_in_annotations
        self.is_setup_py = is_setup_py
        # Names only used in annotations (which we've stringified) should not keep imports
        self.annotation_only_names = used_in_annotations - used_names
        self.conditional_import_checks = {
            'is_torch_available', 'is_tf_available', 'is_flax_available',
            'is_vision_available', 'is_torchvision_available', 'is_scipy_available',
            'is_cv2_available', 'is_sentencepiece_available', 'is_tokenizers_available',
            'is_torch_fx_available', 'is_accelerate_available', 'is_safetensors_available',
            'is_torchvision_v2_available', 'is_peft_available',
        }
        # Essential imports for setup.py to work
        self.setup_py_essential_imports = {'setup', 'find_packages', 'Command', 'Extension'}
    
    def _is_name_used(self, name: str) -> bool:
        """Check if a name is used in actual code (not just annotations)."""
        # For setup.py, always keep essential imports
        if self.is_setup_py and name in self.setup_py_essential_imports:
            return True
        return name in self.used_names
    
    def _should_keep_import(self, names) -> bool:
        """Check if any name in the import is used."""
        for alias in names:
            imported_name = alias.asname if alias.asname else alias.name
            # For 'from x import y', check the actual name
            if isinstance(alias.name, str):
                base_name = alias.name.split('.')[0]
                if self._is_name_used(imported_name) or self._is_name_used(base_name):
                    return True
        return False
    
    def _filter_import_names(self, names):
        """Filter import names to keep only used ones."""
        filtered = []
        for alias in names:
            imported_name = alias.asname if alias.asname else alias.name
            base_name = alias.name.split('.')[0] if isinstance(alias.name, str) else alias.name
            if self._is_name_used(imported_name) or self._is_name_used(base_name):
                filtered.append(alias)
        return filtered
    
    def visit_Import(self, node):
        """Process import statements."""
        filtered = self._filter_import_names(node.names)
        if not filtered:
            return None
        node.names = filtered
        return node
    
    def visit_ImportFrom(self, node):
        """Process from...import statements."""
        filtered = self._filter_import_names(node.names)
        if not filtered:
            return None
        node.names = filtered
        return node
    
    def visit_If(self, node):
        """Process if statements to clean up conditional imports."""
        # Check if this is a conditional import block
        is_conditional_import = False
        if isinstance(node.test, ast.Call):
            if isinstance(node.test.func, ast.Name):
                if node.test.func.id in self.conditional_import_checks:
                    is_conditional_import = True
        
        if is_conditional_import:
            # Process the if body
            new_body = []
            for stmt in node.body:
                transformed = self.visit(stmt)
                if transformed is not None:
                    if isinstance(transformed, list):
                        new_body.extend(transformed)
                    else:
                        new_body.append(transformed)
            
            # Process the else body
            new_orelse = []
            for stmt in node.orelse:
                transformed = self.visit(stmt)
                if transformed is not None:
                    if isinstance(transformed, list):
                        new_orelse.extend(transformed)
                    else:
                        new_orelse.append(transformed)
            
            # If both bodies are empty, remove the entire if block
            if not new_body and not new_orelse:
                return None
            
            # If only else body exists, return the else content directly
            if not new_body and new_orelse:
                return new_orelse
            
            # If body exists but is empty, remove the if
            if not new_body:
                return None
            
            node.body = new_body
            node.orelse = new_orelse
            
            return node
        
        # For non-import if statements, don't process them (remove them)
        # since they're likely implementation-related
        return None
    
    def visit_Assign(self, node):
        """Process assignments - remove if they're not needed."""
        # If this is a top-level assignment and none of the targets are used, remove it
        if isinstance(node, ast.Assign):
            has_used_target = False
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in self.used_names:
                    has_used_target = True
                    break
                # Check for tuple/list unpacking
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name) and elt.id in self.used_names:
                            has_used_target = True
                            break
            
            if not has_used_target:
                return None
        
        return node


class SetupPyDependencyCleaner(ast.NodeTransformer):
    """Clean up dependencies in setup.py files since we've removed all implementations."""
    
    def visit_Assign(self, node):
        """Clear dependency lists in setup.py."""
        # Check if this is an assignment to install_requires or similar
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id in ('install_requires', 'extras_require', 'tests_require', 'setup_requires'):
                    # Replace with empty list/dict
                    if target.id == 'extras_require':
                        node.value = ast.Dict(keys=[], values=[])
                    else:
                        node.value = ast.List(elts=[], ctx=ast.Load())
                    return node
        return node
    
    def visit_Call(self, node):
        """Clean up setup() call arguments."""
        self.generic_visit(node)
        # Check if this is a setup() call
        if isinstance(node.func, ast.Name) and node.func.id == 'setup':
            # Clear dependency-related keyword arguments
            new_keywords = []
            for kw in node.keywords:
                if kw.arg in ('install_requires', 'tests_require', 'setup_requires'):
                    # Replace with empty list
                    new_keywords.append(ast.keyword(arg=kw.arg, value=ast.List(elts=[], ctx=ast.Load())))
                elif kw.arg == 'extras_require':
                    # Replace with empty dict
                    new_keywords.append(ast.keyword(arg=kw.arg, value=ast.Dict(keys=[], values=[])))
                else:
                    new_keywords.append(kw)
            node.keywords = new_keywords
        return node


class EmptyBlockFixer(ast.NodeTransformer):
    """Add pass statements to empty code blocks to maintain valid syntax."""
    
    def _fix_body(self, body):
        """Add pass if body is empty."""
        if not body:
            return [ast.Pass()]
        return body
    
    def visit_Try(self, node):
        """Fix empty try/except blocks."""
        self.generic_visit(node)
        node.body = self._fix_body(node.body)
        for handler in node.handlers:
            handler.body = self._fix_body(handler.body)
        node.orelse = self._fix_body(node.orelse) if node.orelse else []
        node.finalbody = self._fix_body(node.finalbody) if node.finalbody else []
        return node
    
    def visit_For(self, node):
        """Fix empty for loops."""
        self.generic_visit(node)
        node.body = self._fix_body(node.body)
        node.orelse = self._fix_body(node.orelse) if node.orelse else []
        return node
    
    def visit_While(self, node):
        """Fix empty while loops."""
        self.generic_visit(node)
        node.body = self._fix_body(node.body)
        node.orelse = self._fix_body(node.orelse) if node.orelse else []
        return node
    
    def visit_With(self, node):
        """Fix empty with statements."""
        self.generic_visit(node)
        node.body = self._fix_body(node.body)
        return node
    
    def visit_If(self, node):
        """Fix empty if statements."""
        self.generic_visit(node)
        node.body = self._fix_body(node.body)
        node.orelse = self._fix_body(node.orelse) if node.orelse else []
        return node


def inject_torch_mock_at_top(source: str) -> str:
    """
    Inject minimal torch mock at the top of the file to avoid needing PyTorch installed.
    This creates fake torch/tf/jax modules that satisfy imports without actual installation.
    """
    mock_code = '''"""Injected mocks for ML frameworks - no actual installation needed"""
import sys
from types import ModuleType

# Create comprehensive torch mock with dynamic attribute handling
if 'torch' not in sys.modules:
    class _MockTensor:
        """Mock tensor that handles any method call"""
        def __init__(self, *args, **kwargs): pass
        def __getattr__(self, name): return lambda *a, **kw: self
        def __call__(self, *args, **kwargs): return self
        def __repr__(self): return "<MockTensor>"
    
    class _MockModule(ModuleType):
        """Mock module that dynamically creates submodules and registers them"""
        def __getattr__(self, name):
            if name.startswith('__') and name.endswith('__'):
                raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")
            
            # Return a callable mock or another mock module
            if name in ('device', 'dtype') or name.endswith('Tensor'):
                return type(name, (), {})
            elif name.startswith('is_'):
                return lambda: False  # All is_* checks return False
            elif name in ('jit', 'utils', 'nn', 'cuda', 'distributed', 'optim', 'autograd'):
                # Create and register submodule
                submodule_name = f'{self.__name__}.{name}'
                if submodule_name not in sys.modules:
                    submodule = _MockModule(submodule_name)
                    sys.modules[submodule_name] = submodule
                    # Add common attributes for specific submodules
                    if name == 'nn':
                        submodule.Module = type('Module', (), {})
                    elif name == 'cuda':
                        submodule.is_available = lambda: False
                    elif name == 'distributed':
                        submodule.is_available = lambda: False
                        submodule.is_initialized = lambda: False
                    elif name == 'jit':
                        submodule.is_tracing = lambda: False
                    setattr(self, name, submodule)
                return sys.modules[submodule_name]
            else:
                # Create nested mock module and register it
                submodule_name = f'{self.__name__}.{name}'
                if submodule_name not in sys.modules:
                    submodule = _MockModule(submodule_name)
                    sys.modules[submodule_name] = submodule
                    setattr(self, name, submodule)
                return sys.modules[submodule_name]
        
        def __call__(self, *args, **kwargs):
            return _MockTensor()
    
    _torch = _MockModule('torch')
    _torch.__version__ = '2.0.0'
    _torch.__file__ = __file__
    _torch.__path__ = []
    
    # Explicitly set common attributes
    _torch.Tensor = _MockTensor
    for name in ['FloatTensor', 'LongTensor', 'BoolTensor', 'IntTensor', 'DoubleTensor']:
        setattr(_torch, name, _MockTensor)
    
    # Mock dtypes
    class _MockDtype: pass
    for dtype_name in ['float16', 'float32', 'float64', 'int8', 'int16', 'int32', 'int64',
                       'uint8', 'bool', 'bfloat16', 'complex64', 'complex128']:
        setattr(_torch, dtype_name, _MockDtype())
    
    # Mock common functions
    for func_name in ['zeros', 'ones', 'tensor', 'from_numpy', 'as_tensor', 'save', 'load']:
        setattr(_torch, func_name, lambda *args, **kwargs: _MockTensor())
    
    # Register base torch module
    sys.modules['torch'] = _torch

# Create minimal tensorflow mock
if 'tensorflow' not in sys.modules:
    _tf = ModuleType('tensorflow')
    _tf.__version__ = '2.0.0'
    sys.modules['tensorflow'] = _tf
    sys.modules['tf'] = _tf

# Create minimal jax mock  
if 'jax' not in sys.modules:
    _jax = ModuleType('jax')
    _jax.__version__ = '0.4.0'
    sys.modules['jax'] = _jax

'''
    # Find the first import or code line (after docstring)
    lines = source.split('\n')
    insert_pos = 0
    in_docstring = False
    docstring_char = None
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Handle module docstring
        if i == 0 or (i == 1 and not lines[0].strip()):
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                if stripped.count(docstring_char) == 2:  # Single-line docstring
                    insert_pos = i + 1
                    continue
                else:
                    in_docstring = True
                    continue
        
        if in_docstring:
            if docstring_char in stripped:
                in_docstring = False
                insert_pos = i + 1
            continue
        
        # Found first real code line
        if stripped and not stripped.startswith('#'):
            insert_pos = i
            break
    
    # Insert mock code
    lines.insert(insert_pos, mock_code)
    return '\n'.join(lines)


def patch_import_utils_for_docbuild(file_path: Path) -> bool:
    """
    Special handling for import_utils.py to disable backend checks using AST.
    This allows doc-building without installing heavy ML frameworks.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        class BackendPatcher(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                # Patch backend check functions to return True
                backend_functions = {
                    'is_torch_available', 'is_tf_available', 'is_flax_available',
                    'is_vision_available', 'is_torchvision_available', 'is_scipy_available',
                    'is_tokenizers_available', 'is_sentencepiece_available',
                    'is_torch_fx_available', 'is_accelerate_available', 'is_safetensors_available',
                    'is_torchvision_v2_available', 'is_peft_available'
                }
                
                if node.name in backend_functions:
                    # Replace body with: return True
                    node.body = [ast.Return(value=ast.Constant(value=True))]
                    return node
                
                
                # Patch requires_backends to be a no-op
                if node.name == 'requires_backends':
                    # Replace body with: pass
                    node.body = [ast.Pass()]
                    return node
                
                return node
            
            def visit_ClassDef(self, node):
                # Patch DummyObject metaclass
                if node.name == 'DummyObject':
                    # Find and patch __getattribute__
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == '__getattribute__':
                            # Replace with simple return super().__getattribute__(key)
                            item.body = [
                                ast.Return(
                                    value=ast.Call(
                                        func=ast.Attribute(
                                            value=ast.Call(
                                                func=ast.Name(id='super', ctx=ast.Load()),
                                                args=[],
                                                keywords=[]
                                            ),
                                            attr='__getattribute__',
                                            ctx=ast.Load()
                                        ),
                                        args=[ast.Name(id='key', ctx=ast.Load())],
                                        keywords=[]
                                    )
                                )
                            ]
                self.generic_visit(node)
                return node
        
        patcher = BackendPatcher()
        tree = patcher.visit(tree)
        ast.fix_missing_locations(tree)
        
        # Generate patched source
        new_source = ast.unparse(tree)
        
        # Inject torch mock at the very top
        new_source = inject_torch_mock_at_top(new_source)
        
        # Additional text-based patch for _is_package_available to bypass ML framework checks
        # Insert a check at the beginning of the function
        patch_lines = [
            "# Patched for doc-building: pretend ML frameworks are available",
            "if pkg_name in ('torch', 'tensorflow', 'tf', 'flax', 'jax'):",
            "    if return_version:",
            "        return (True, '2.0.0')",
            "    return True"
        ]
        
        # Find the _is_package_available function and inject the patch
        if 'def _is_package_available(' in new_source:
            lines = new_source.split('\n')
            new_lines = []
            in_function = False
            patched = False
            
            for i, line in enumerate(lines):
                if 'def _is_package_available(' in line:
                    new_lines.append(line)
                    in_function = True
                elif in_function and not patched and line.strip() and not line.strip().startswith('"""') and not line.strip().startswith("'''"):
                    # Found first real line in function, insert patch before it
                    indent = len(line) - len(line.lstrip())
                    for patch_line in patch_lines:
                        new_lines.append(' ' * indent + patch_line)
                    new_lines.append(line)
                    patched = True
                    in_function = False
                else:
                    new_lines.append(line)
            
            new_source = '\n'.join(new_lines)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_source)
        
        print(f"Patched: {file_path} (backend checks disabled)")
        return True
    except Exception as e:
        print(f"Error patching {file_path}: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_file(file_path: Path, dry_run: bool = False) -> bool:
    """
    Process a single Python file.
    Returns True if successful, False otherwise.
    """
    # Detect which package we're processing
    path_str = str(file_path)
    is_transformers = '/transformers/' in path_str
    
    # Skip files that contain infrastructure/import logic and don't contribute to docs
    skip_files = {'__init__.py', 'dependency_versions_check.py', 'dependency_versions_table.py'}
    if file_path.name in skip_files:
        print(f"Skipped: {file_path} (infrastructure file)")
        return True
    
    # Skip entire directories that don't contain documentation-relevant code
    # NOTE: utils/integrations/kernels are only skipped for transformers
    # Other packages (accelerate, diffusers, peft) have actual API in utils/
    base_skip_dirs = {'commands', 'tests', 'benchmark', 'examples', 'templates', 'scripts', 'docker'}
    transformers_only_skip = {'utils', 'integrations', 'kernels', 'auto'}
    
    skip_dirs = base_skip_dirs
    if is_transformers:
        skip_dirs = base_skip_dirs | transformers_only_skip
    
    # Special handling for import_utils.py - patch backend checks (transformers only)
    if is_transformers and file_path.name == 'import_utils.py' and '/utils/' in path_str:
        return patch_import_utils_for_docbuild(file_path)
    
    for skip_dir in skip_dirs:
        if f'/{skip_dir}/' in path_str or path_str.endswith(f'/{skip_dir}'):
            print(f"Skipped: {file_path} (in {skip_dir} directory)")
            return True
    
    # For transformers: only process files matching specific patterns or setup.py
    # For other packages: process all remaining Python files (they're part of the API)
    if is_transformers:
        doc_relevant_patterns = ('modeling_', 'configuration_', 'tokenization_', 'processing_',
                                'image_processing_', 'video_processing_', 'feature_extraction_',
                                'audio_processing_')
        is_doc_relevant = (
            file_path.name == 'setup.py' or
            file_path.name.startswith(doc_relevant_patterns)
        )
        
        if not is_doc_relevant:
            print(f"Skipped: {file_path} (not documentation-relevant)")
            return True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        # Replace re-exports from skipped directories with harmless stubs
        source = replace_cross_directory_imports(source, skip_dirs)
        
        # Check if file needs torch mock injection (has module-level torch imports)
        needs_torch_mock = (
            'import torch' in source and 
            not file_path.name.startswith('test_') and
            '/tests/' not in str(file_path)
        )
        
        # Parse the source code
        tree = ast.parse(source)
        
        # First pass: preserve docstrings and collect used names
        docstring_preserver = DocstringPreserver()
        tree = docstring_preserver.visit(tree)
        
        # Check if this is a setup.py file
        is_setup_py = file_path.name == 'setup.py'
        
        # Second pass: clean up imports (only keep imports used in actual code, not just annotations)
        import_cleaner = ImportCleaner(docstring_preserver.used_names, docstring_preserver.used_in_annotations, is_setup_py)
        tree = import_cleaner.visit(tree)
        
        # Special handling for setup.py files - clear dependencies
        if is_setup_py:
            setup_cleaner = SetupPyDependencyCleaner()
            tree = setup_cleaner.visit(tree)
        
        # Third pass: fix empty blocks
        empty_block_fixer = EmptyBlockFixer()
        tree = empty_block_fixer.visit(tree)
        
        # Fix missing locations
        ast.fix_missing_locations(tree)
        
        # Generate new source code
        try:
            new_source = ast.unparse(tree)
        except AttributeError:
            # Python < 3.9 doesn't have ast.unparse
            import astor
            new_source = astor.to_source(tree)
        
        # Inject torch mock at the top of files that need it
        if needs_torch_mock:
            new_source = inject_torch_mock_at_top(new_source)

        # Replace imports from skipped directories with stubs
        new_source = patch_reexports(new_source, skip_dirs)

        if dry_run:
            print(f"Would process: {file_path}")
            return True
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_source)
        
        print(f"Processed: {file_path}" + (" [+torch mock]" if needs_torch_mock else ""))
        return True
        
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def process_directory(path: Path, dry_run: bool = False):
    """Process all Python files in a directory recursively or a single file."""
    if not path.exists():
        print(f"Error: Path {path} does not exist")
        sys.exit(1)
    
    # Handle single file
    if path.is_file():
        if not path.suffix == '.py':
            print(f"Error: {path} is not a Python file")
            sys.exit(1)
        python_files = [path]
    # Handle directory
    elif path.is_dir():
        python_files = list(path.rglob("*.py"))
        if not python_files:
            print(f"No Python files found in {path}")
            return
    else:
        print(f"Error: {path} is neither a file nor a directory")
        sys.exit(1)
    
    print(f"Found {len(python_files)} Python file(s) to process")
    
    successful = 0
    failed = 0
    
    for py_file in python_files:
        if process_file(py_file, dry_run):
            successful += 1
        else:
            failed += 1
    
    print(f"\nProcessing complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(
        description="Strip Python files to keep only docstrings and signatures"
    )
    parser.add_argument(
        "path",
        type=str,
        help="Directory or Python file to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes"
    )
    
    args = parser.parse_args()
    
    path = Path(args.path)
    process_directory(path, args.dry_run)


if __name__ == "__main__":
    main()
