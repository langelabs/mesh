import inspect
import uuid
from collections.abc import Awaitable, Callable
from types import NoneType
from typing import Annotated, Any, TypeVar, get_args, get_origin, get_type_hints

from .types import Can, CanParameter, NodeId

_MeshCallable = Callable[..., Awaitable[object]]
_MeshFunction = TypeVar("_MeshFunction", bound=_MeshCallable)


class MeshToolGroup:
    """Collect mesh tools that can be included in other groups or routers."""

    def __init__(self) -> None:
        """Create an empty group with its own capability owner ID."""
        self._id: NodeId = str(uuid.uuid4())
        self._capabilities: dict[str, tuple[Can, _MeshCallable]] = {}

    def add_tool_group(self, tool_group: "MeshToolGroup") -> None:
        """Copy a group's current tools, replacing entries with matching IDs.

        :param tool_group: Group whose tools to advertise under this group's ID.
        """
        self._capabilities.update(
            {
                capability_id: (
                    capability.model_copy(update={"node": self._id}, deep=True),
                    func,
                )
                for capability_id, (
                    capability,
                    func,
                ) in tool_group._capabilities.items()
            }
        )

    def add_to_mesh(self, func: _MeshCallable) -> None:
        """Register an async function for discovery under its module-qualified name.

        :param func: Async function or bound async method to advertise. Its
            docstring describes the capability. Type hints describe the inputs
            and return value, with optional descriptions from ``Annotated``.
        :raises TypeError: If the callable is not an async function or method.
        """
        if not inspect.iscoroutinefunction(func) or not (
            inspect.isfunction(func) or inspect.ismethod(func)
        ):
            raise TypeError("Mesh capabilities must be async functions or methods")

        capability_id = f"{func.__module__}.{func.__qualname__}"
        hints = get_type_hints(func, include_extras=True)
        return_type = hints.get("return", Any)
        outputs = []
        if return_type is not NoneType:
            outputs.append(self._describe_parameter("return", return_type))

        capability = Can(
            node=self._id,
            name=func.__name__,
            description=inspect.getdoc(func) or "",
            id=capability_id,
            input=[
                self._describe_parameter(name, hints.get(name, Any))
                for name in inspect.signature(func).parameters
            ],
            output=outputs,
        )
        self._capabilities[capability_id] = (capability, func)

    def meshed(self, func: _MeshFunction) -> _MeshFunction:
        """Decorate an async function to register it for discovery.

        :param func: Async function or bound async method to advertise.
        :returns: The original callable.
        """
        self.add_to_mesh(func)
        return func

    @staticmethod
    def _describe_parameter(name: str, annotation: object) -> CanParameter:
        """Describe an input or return value using a type name and optional text.

        :param name: The input name or ``return``.
        :param annotation: The resolved Python type annotation.
        :returns: A parameter description suitable for capability discovery.
        """
        description = ""
        if get_origin(annotation) is Annotated:
            annotation, *metadata = get_args(annotation)
            description = next((item for item in metadata if isinstance(item, str)), "")

        return CanParameter(
            name=name,
            type=inspect.formatannotation(annotation),
            description=description,
        )
