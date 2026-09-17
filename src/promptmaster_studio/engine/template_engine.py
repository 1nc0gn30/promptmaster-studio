"""High-performance template interpolation engine for PromptMaster Studio.

Supports variable interpolation, typed validation, default values, filters,
nested conditionals ({{#if}} / {{#unless}} / {{else}}), and loops ({{#each}}).
100% Python Standard Library.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from promptmaster_studio.models import PromptTemplate, PromptVariable, VariableType


class TemplateError(Exception):
    """Base exception for all template processing errors."""
    pass


class TemplateSyntaxError(TemplateError):
    """Raised when template structure or tags are malformed."""
    pass


class VariableMissingError(TemplateError):
    """Raised when a required variable is missing in strict mode."""
    pass


class VariableValidationError(TemplateError):
    """Raised when variable content fails type or constraint validation."""
    pass


class TemplateNode:
    """Base AST node for parsed template syntax."""
    pass


class TextNode(TemplateNode):
    """Plain text literal node."""
    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return f"TextNode({self.text!r})"


class VariableNode(TemplateNode):
    """Variable evaluation node with optional filters and default fallbacks."""
    def __init__(self, raw_expr: str) -> None:
        self.raw_expr = raw_expr.strip()

    def __repr__(self) -> str:
        return f"VariableNode({self.raw_expr!r})"


class IfNode(TemplateNode):
    """Conditional branching node."""
    def __init__(
        self,
        condition: str,
        true_body: List[TemplateNode],
        false_body: Optional[List[TemplateNode]] = None,
        is_unless: bool = False,
    ) -> None:
        self.condition = condition.strip()
        self.true_body = true_body
        self.false_body = false_body or []
        self.is_unless = is_unless

    def __repr__(self) -> str:
        return f"IfNode({self.condition!r}, true={len(self.true_body)}, false={len(self.false_body)}, unless={self.is_unless})"


class EachNode(TemplateNode):
    """Loop iteration node."""
    def __init__(self, collection_expr: str, body: List[TemplateNode]) -> None:
        self.collection_expr = collection_expr.strip()
        self.body = body

    def __repr__(self) -> str:
        return f"EachNode({self.collection_expr!r}, body={len(self.body)})"


class BuiltinFilters:
    """Standard transformations available in template expressions."""

    @staticmethod
    def upper(val: Any) -> str:
        return str(val).strip().upper()

    @staticmethod
    def lower(val: Any) -> str:
        return str(val).strip().lower()

    @staticmethod
    def title(val: Any) -> str:
        return str(val).strip().title()

    @staticmethod
    def capitalize(val: Any) -> str:
        return str(val).strip().capitalize()

    @staticmethod
    def trim(val: Any) -> str:
        return str(val).strip()

    @staticmethod
    def strip(val: Any) -> str:
        return str(val).strip()

    @staticmethod
    def length(val: Any) -> int:
        if val is None:
            return 0
        if isinstance(val, (list, tuple, dict, set, str)):
            return len(val)
        return len(str(val))

    @staticmethod
    def json(val: Any, indent: Optional[int] = None) -> str:
        if indent is not None:
            try:
                indent_num = int(indent)
            except (ValueError, TypeError):
                indent_num = 2
            return json.dumps(val, indent=indent_num, ensure_ascii=False)
        return json.dumps(val, ensure_ascii=False)

    @staticmethod
    def join(val: Any, delimiter: str = ", ") -> str:
        if isinstance(val, (list, tuple, set)):
            return delimiter.join(str(item) for item in val)
        return str(val)

    @staticmethod
    def bullets(val: Any, prefix: str = "- ") -> str:
        if isinstance(val, (list, tuple, set)):
            return "\n".join(f"{prefix}{item}" for item in val)
        return f"{prefix}{val}"

    @staticmethod
    def numbered(val: Any) -> str:
        if isinstance(val, (list, tuple)):
            return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(val))
        return f"1. {val}"

    @staticmethod
    def indent(val: Any, spaces: int = 4) -> str:
        try:
            sp = int(spaces)
        except (ValueError, TypeError):
            sp = 4
        pad = " " * sp
        lines = str(val).splitlines()
        return "\n".join(pad + line if line.strip() else line for line in lines)

    @staticmethod
    def default(val: Any, fallback: Any = "") -> Any:
        if val is None or val == "" or val == [] or val == {}:
            return fallback
        return val


class PromptTemplateEngine:
    """Production template compiler and variable interpolator."""

    TAG_PATTERN = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
    
    def __init__(self) -> None:
        self.filters: Dict[str, Callable[..., Any]] = {
            "upper": BuiltinFilters.upper,
            "lower": BuiltinFilters.lower,
            "title": BuiltinFilters.title,
            "capitalize": BuiltinFilters.capitalize,
            "trim": BuiltinFilters.trim,
            "strip": BuiltinFilters.strip,
            "length": BuiltinFilters.length,
            "len": BuiltinFilters.length,
            "json": BuiltinFilters.json,
            "join": BuiltinFilters.join,
            "bullets": BuiltinFilters.bullets,
            "bullet": BuiltinFilters.bullets,
            "numbered": BuiltinFilters.numbered,
            "indent": BuiltinFilters.indent,
            "default": BuiltinFilters.default,
        }

    def register_filter(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a custom filter function."""
        self.filters[name.lower()] = fn

    def validate_variable(self, spec: PromptVariable, value: Any, strict: bool = False) -> Any:
        """Validate and coerce a single variable against its specification.
        
        Args:
            spec: The PromptVariable constraint spec.
            value: The runtime input value.
            strict: If True, raises VariableMissingError for missing required variables.
            
        Returns:
            Coerced or validated value.
            
        Raises:
            VariableValidationError: If validation fails.
            VariableMissingError: If a required variable is not provided in strict mode.
        """
        if value is None:
            if spec.default_value is not None:
                value = spec.default_value
            elif spec.required:
                if strict:
                    raise VariableMissingError(f"Required variable '{spec.name}' is missing.")
                return ""
            else:
                return None

        # Enum check
        if spec.enum_values:
            val_str = str(value)
            if val_str not in spec.enum_values:
                raise VariableValidationError(
                    f"Variable '{spec.name}' value '{val_str}' is not one of allowed enum values: {spec.enum_values}"
                )

        # Regex check
        if spec.validation_regex and isinstance(value, str):
            if not re.search(spec.validation_regex, value):
                raise VariableValidationError(
                    f"Variable '{spec.name}' failed regex pattern: {spec.validation_regex}"
                )

        # Type conversion and validation
        vtype = spec.var_type.lower()
        if vtype == VariableType.STRING.value:
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        elif vtype == VariableType.NUMBER.value:
            if isinstance(value, (int, float)):
                return value
            try:
                if "." in str(value):
                    return float(value)
                return int(value)
            except ValueError:
                raise VariableValidationError(
                    f"Variable '{spec.name}' expected number, got '{value}'"
                )
        elif vtype == VariableType.BOOLEAN.value:
            if isinstance(value, bool):
                return value
            val_s = str(value).strip().lower()
            if val_s in ("true", "1", "yes", "y", "on"):
                return True
            if val_s in ("false", "0", "no", "n", "off"):
                return False
            raise VariableValidationError(
                f"Variable '{spec.name}' expected boolean, got '{value}'"
            )
        elif vtype == VariableType.LIST.value:
            if isinstance(value, list):
                return value
            if isinstance(value, (tuple, set)):
                return list(value)
            if isinstance(value, str):
                # Try parsing as JSON array or split by newlines/commas
                stripped = value.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    try:
                        parsed = json.loads(stripped)
                        if isinstance(parsed, list):
                            return parsed
                    except json.JSONDecodeError:
                        pass
                lines = [line.strip() for line in stripped.splitlines() if line.strip()]
                if len(lines) > 1:
                    return lines
                return [value]
            raise VariableValidationError(
                f"Variable '{spec.name}' expected list, got {type(value).__name__}"
            )
        elif vtype == VariableType.OBJECT.value:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    pass
            raise VariableValidationError(
                f"Variable '{spec.name}' expected object/dict, got {type(value).__name__}"
            )

        return value

    def validate_variables(
        self,
        variables: Optional[Dict[str, Any]],
        specs: List[PromptVariable],
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Validate and apply defaults for all variables against a list of specs.
        
        Args:
            variables: Runtime variables mapping.
            specs: List of expected variable definitions.
            strict: Enforce strict variable presence.
            
        Returns:
            Validated and populated variables dictionary.
        """
        input_vars = dict(variables or {})
        result: Dict[str, Any] = {}

        for spec in specs:
            raw_val = input_vars.get(spec.name)
            result[spec.name] = self.validate_variable(spec, raw_val, strict=strict)

        # Include any extra variables passed in that weren't in specs
        for k, v in input_vars.items():
            if k not in result:
                result[k] = v

        return result

    def extract_variables(self, template_str: str) -> List[str]:
        """Extract all unique variable names referenced in the template.
        
        Filters out internal keywords, control structures, and loop loop-scoped variables.
        
        Args:
            template_str: The prompt template text.
            
        Returns:
            Sorted list of required or referenced variable names.
        """
        extracted: Set[str] = set()
        special_keywords = {
            "this", "@index", "@first", "@last", "@total", "@key",
            "else", "#else", "/if", "/unless", "/each", "true", "false", "null", "none"
        }

        for match in self.TAG_PATTERN.finditer(template_str):
            tag_content = match.group(1).strip()
            if not tag_content:
                continue

            # Check block openings
            if tag_content.startswith("#if ") or tag_content.startswith("#unless "):
                expr = tag_content.split(maxsplit=1)[1].strip()
                # Condition might contain comparators (e.g. x == 'val')
                parts = re.split(r"[=!<>]+", expr)
                var_name = parts[0].strip().split(".")[0]
                if var_name and var_name.lower() not in special_keywords:
                    extracted.add(var_name)
            elif tag_content.startswith("#each "):
                coll = tag_content.split(maxsplit=1)[1].strip()
                var_name = coll.split(".")[0].split("|")[0].strip()
                if var_name and var_name.lower() not in special_keywords:
                    extracted.add(var_name)
            elif (
                tag_content.startswith("/")
                or tag_content in ("else", "#else")
            ):
                continue
            else:
                # Variable interpolation expression
                # Check for pipe filters or colon defaults
                expr = tag_content.split("|")[0]
                if ":-" in expr:
                    expr = expr.split(":-")[0]
                elif ":" in expr and not expr.startswith("http"):
                    expr = expr.split(":")[0]
                var_name = expr.strip().split(".")[0].split("[")[0]
                if var_name and var_name.lower() not in special_keywords:
                    extracted.add(var_name)

        return sorted(list(extracted))

    def _tokenize(self, template_str: str) -> List[Tuple[str, str]]:
        """Split template into text chunks and tag contents."""
        tokens: List[Tuple[str, str]] = []
        last_end = 0

        for match in self.TAG_PATTERN.finditer(template_str):
            start, end = match.span()
            if start > last_end:
                tokens.append(("text", template_str[last_end:start]))
            tokens.append(("tag", match.group(1).strip()))
            last_end = end

        if last_end < len(template_str):
            tokens.append(("text", template_str[last_end:]))

        return tokens

    def _parse_nodes(self, tokens: List[Tuple[str, str]], index: int = 0) -> Tuple[List[TemplateNode], int]:
        """Recursive descent parser to construct AST from token stream."""
        nodes: List[TemplateNode] = []
        n = len(tokens)

        while index < n:
            token_type, token_val = tokens[index]
            index += 1

            if token_type == "text":
                nodes.append(TextNode(token_val))
            elif token_type == "tag":
                # Check control blocks
                if token_val.startswith("#if "):
                    cond = token_val[4:].strip()
                    true_body, false_body, index = self._parse_if_block(tokens, index, cond, is_unless=False)
                    nodes.append(IfNode(cond, true_body, false_body, is_unless=False))
                elif token_val.startswith("#unless "):
                    cond = token_val[8:].strip()
                    true_body, false_body, index = self._parse_if_block(tokens, index, cond, is_unless=True)
                    nodes.append(IfNode(cond, true_body, false_body, is_unless=True))
                elif token_val.startswith("#each "):
                    coll = token_val[6:].strip()
                    body, index = self._parse_each_block(tokens, index)
                    nodes.append(EachNode(coll, body))
                elif token_val in ("else", "#else", "/if", "/unless", "/each"):
                    # Encountered closing or else tag for parent block
                    index -= 1  # Put back for caller to handle
                    break
                else:
                    nodes.append(VariableNode(token_val))

        return nodes, index

    def _parse_if_block(
        self, tokens: List[Tuple[str, str]], index: int, condition: str, is_unless: bool
    ) -> Tuple[List[TemplateNode], List[TemplateNode], int]:
        """Parse the true and optional else branch of an if/unless block."""
        true_body: List[TemplateNode] = []
        false_body: List[TemplateNode] = []
        n = len(tokens)
        target_close = "/unless" if is_unless else "/if"

        in_else = False
        while index < n:
            token_type, token_val = tokens[index]
            index += 1

            if token_type == "text":
                if in_else:
                    false_body.append(TextNode(token_val))
                else:
                    true_body.append(TextNode(token_val))
            elif token_type == "tag":
                if token_val in ("else", "#else"):
                    in_else = True
                elif token_val == target_close:
                    return true_body, false_body, index
                elif token_val.startswith("#if "):
                    inner_cond = token_val[4:].strip()
                    t_b, f_b, index = self._parse_if_block(tokens, index, inner_cond, is_unless=False)
                    node = IfNode(inner_cond, t_b, f_b, is_unless=False)
                    (false_body if in_else else true_body).append(node)
                elif token_val.startswith("#unless "):
                    inner_cond = token_val[8:].strip()
                    t_b, f_b, index = self._parse_if_block(tokens, index, inner_cond, is_unless=True)
                    node = IfNode(inner_cond, t_b, f_b, is_unless=True)
                    (false_body if in_else else true_body).append(node)
                elif token_val.startswith("#each "):
                    coll = token_val[6:].strip()
                    e_body, index = self._parse_each_block(tokens, index)
                    node = EachNode(coll, e_body)
                    (false_body if in_else else true_body).append(node)
                else:
                    (false_body if in_else else true_body).append(VariableNode(token_val))

        return true_body, false_body, index

    def _parse_each_block(
        self, tokens: List[Tuple[str, str]], index: int
    ) -> Tuple[List[TemplateNode], int]:
        """Parse loop iteration body until /each tag."""
        body: List[TemplateNode] = []
        n = len(tokens)

        while index < n:
            token_type, token_val = tokens[index]
            index += 1

            if token_type == "text":
                body.append(TextNode(token_val))
            elif token_type == "tag":
                if token_val == "/each":
                    return body, index
                elif token_val.startswith("#if "):
                    cond = token_val[4:].strip()
                    t_b, f_b, index = self._parse_if_block(tokens, index, cond, is_unless=False)
                    body.append(IfNode(cond, t_b, f_b, is_unless=False))
                elif token_val.startswith("#unless "):
                    cond = token_val[8:].strip()
                    t_b, f_b, index = self._parse_if_block(tokens, index, cond, is_unless=True)
                    body.append(IfNode(cond, t_b, f_b, is_unless=True))
                elif token_val.startswith("#each "):
                    coll = token_val[6:].strip()
                    e_body, index = self._parse_each_block(tokens, index)
                    body.append(EachNode(coll, e_body))
                else:
                    body.append(VariableNode(token_val))

        return body, index

    def _eval_path(self, context_stack: List[Dict[str, Any]], path: str) -> Any:
        """Resolve dotted or indexed path across scoped context stack (innermost first)."""
        path = path.strip()
        if not path:
            return None

        # Check literals
        if path in ("true", "True"):
            return True
        if path in ("false", "False"):
            return False
        if path in ("null", "none", "None", "nil"):
            return None
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            return path[1:-1]
        try:
            if "." in path and not path.startswith("."):
                return float(path)
            return int(path)
        except ValueError:
            pass

        # Parse dotted path components
        parts = re.split(r"\.|(?=\[)", path)
        root = parts[0].strip()

        # Search context stack from top to bottom
        val: Any = None
        found = False

        for ctx in reversed(context_stack):
            if root in ctx:
                val = ctx[root]
                found = True
                break

        if not found:
            return None

        # Resolve subsequent path segments
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue
            if part.startswith("[") and part.endswith("]"):
                key = part[1:-1].strip().strip("\"'")
                try:
                    idx = int(key)
                    val = val[idx] if (isinstance(val, (list, tuple)) and 0 <= idx < len(val)) else None
                except (ValueError, TypeError, IndexError):
                    val = val.get(key) if isinstance(val, dict) else getattr(val, key, None)
            else:
                if isinstance(val, dict):
                    val = val.get(part)
                elif hasattr(val, part):
                    val = getattr(val, part)
                else:
                    val = None

        return val

    def _eval_condition(self, context_stack: List[Dict[str, Any]], condition: str) -> bool:
        """Evaluate a boolean condition or simple comparison expression."""
        cond = condition.strip()

        # Check comparison operators (==, !=, >=, <=, >, <, in)
        comparison_ops = ["==", "!=", ">=", "<=", ">", "<", " in "]
        for op in comparison_ops:
            if op in cond:
                left_str, right_str = cond.split(op, 1)
                left_val = self._eval_path(context_stack, left_str)
                right_val = self._eval_path(context_stack, right_str)

                op_clean = op.strip()
                if op_clean == "==":
                    return str(left_val) == str(right_val) if (left_val is not None and right_val is not None) else (left_val == right_val)
                elif op_clean == "!=":
                    return str(left_val) != str(right_val) if (left_val is not None and right_val is not None) else (left_val != right_val)
                elif op_clean == ">=":
                    return float(left_val) >= float(right_val)
                elif op_clean == "<=":
                    return float(left_val) <= float(right_val)
                elif op_clean == ">":
                    return float(left_val) > float(right_val)
                elif op_clean == "<":
                    return float(left_val) < float(right_val)
                elif op_clean == "in":
                    if isinstance(right_val, (list, tuple, set, str)):
                        return left_val in right_val
                    return str(left_val) in str(right_val)

        # Single variable truthiness
        val = self._eval_path(context_stack, cond)
        if val is None or val is False or val == "" or val == 0 or val == [] or val == {}:
            return False
        return True

    def _apply_filter(self, val: Any, filter_expr: str) -> Any:
        """Execute a single filter pipeline step."""
        filter_expr = filter_expr.strip()
        match = re.match(r"^(\w+)(?:\((.*)\))?$", filter_expr)
        if not match:
            return val

        filter_name = match.group(1).lower()
        args_str = match.group(2)
        args: List[Any] = []

        if args_str:
            # Parse arguments separated by comma
            raw_args = [a.strip() for a in args_str.split(",")]
            for a in raw_args:
                if (a.startswith('"') and a.endswith('"')) or (a.startswith("'") and a.endswith("'")):
                    args.append(a[1:-1])
                else:
                    try:
                        args.append(int(a))
                    except ValueError:
                        try:
                            args.append(float(a))
                        except ValueError:
                            args.append(a)

        fn = self.filters.get(filter_name)
        if fn:
            try:
                return fn(val, *args)
            except Exception:
                return val
        return val

    def _eval_variable_node(
        self,
        node: VariableNode,
        context_stack: List[Dict[str, Any]],
        strict: bool,
    ) -> str:
        """Evaluate a variable expression with filters and defaults."""
        raw = node.raw_expr

        # Split filters by pipe
        pipe_parts = [p.strip() for p in raw.split("|")]
        base_expr = pipe_parts[0]
        filter_list = pipe_parts[1:]

        # Handle inline default syntax (var:-default or var:default)
        default_val: Optional[str] = None
        if ":-" in base_expr:
            base_expr, default_val = base_expr.split(":-", 1)
        elif ":" in base_expr and not base_expr.startswith("http"):
            parts = base_expr.split(":", 1)
            base_expr, default_val = parts[0], parts[1]

        base_expr = base_expr.strip()
        val = self._eval_path(context_stack, base_expr)

        if val is None:
            if default_val is not None:
                val = default_val.strip("\"'")
            elif strict:
                raise VariableMissingError(
                    f"Variable '{base_expr}' is missing and strict rendering is enabled."
                )
            else:
                val = ""

        # Apply filters in order
        for f_expr in filter_list:
            val = self._apply_filter(val, f_expr)

        if val is None:
            return ""
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    def _render_ast(
        self,
        nodes: List[TemplateNode],
        context_stack: List[Dict[str, Any]],
        strict: bool,
    ) -> str:
        """Render AST nodes into final string output."""
        output_parts: List[str] = []

        for node in nodes:
            if isinstance(node, TextNode):
                output_parts.append(node.text)
            elif isinstance(node, VariableNode):
                output_parts.append(self._eval_variable_node(node, context_stack, strict))
            elif isinstance(node, IfNode):
                cond_result = self._eval_condition(context_stack, node.condition)
                if node.is_unless:
                    cond_result = not cond_result

                if cond_result:
                    output_parts.append(self._render_ast(node.true_body, context_stack, strict))
                elif node.false_body:
                    output_parts.append(self._render_ast(node.false_body, context_stack, strict))
            elif isinstance(node, EachNode):
                coll_val = self._eval_path(context_stack, node.collection_expr)
                if coll_val and isinstance(coll_val, (list, tuple, set)):
                    items = list(coll_val)
                    total = len(items)
                    for idx, item in enumerate(items):
                        item_ctx: Dict[str, Any] = {
                            "this": item,
                            "@index": idx,
                            "@first": idx == 0,
                            "@last": idx == total - 1,
                            "@total": total,
                        }
                        if isinstance(item, dict):
                            item_ctx.update(item)
                        context_stack.append(item_ctx)
                        output_parts.append(self._render_ast(node.body, context_stack, strict))
                        context_stack.pop()
                elif coll_val and isinstance(coll_val, dict):
                    items_dict = list(coll_val.items())
                    total = len(items_dict)
                    for idx, (k, v) in enumerate(items_dict):
                        item_ctx = {
                            "this": v,
                            "@key": k,
                            "@index": idx,
                            "@first": idx == 0,
                            "@last": idx == total - 1,
                            "@total": total,
                        }
                        if isinstance(v, dict):
                            item_ctx.update(v)
                        context_stack.append(item_ctx)
                        output_parts.append(self._render_ast(node.body, context_stack, strict))
                        context_stack.pop()

        return "".join(output_parts)

    def render(
        self,
        template_str: str,
        variables: Optional[Dict[str, Any]] = None,
        strict: bool = False,
        specs: Optional[List[PromptVariable]] = None,
    ) -> str:
        """Compile and render a template string with given variables.
        
        Args:
            template_str: Template string with mustache-style tags.
            variables: Variables dictionary.
            strict: If True, raises VariableMissingError for missing variables.
            specs: Optional variable specifications for validation & default application.
            
        Returns:
            Rendered text string.
        """
        vars_dict = dict(variables or {})
        if specs:
            vars_dict = self.validate_variables(vars_dict, specs, strict=strict)

        tokens = self._tokenize(template_str)
        nodes, _ = self._parse_nodes(tokens, index=0)
        return self._render_ast(nodes, [vars_dict], strict=strict)

    def render_template(
        self,
        template: PromptTemplate,
        variables: Optional[Dict[str, Any]] = None,
        strict: bool = False,
    ) -> str:
        """Render a PromptTemplate dataclass instance using its embedded variable specs.
        
        Args:
            template: PromptTemplate instance.
            variables: Runtime variables.
            strict: Enforce strict variable presence.
            
        Returns:
            Rendered prompt string.
        """
        return self.render(
            template_str=template.template_str,
            variables=variables,
            strict=strict,
            specs=template.variables,
        )
