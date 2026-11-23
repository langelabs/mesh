from typing import TypeAlias

NodeId: TypeAlias = str
CmdId: TypeAlias = str

VersionId: TypeAlias = int
AtomicTypes: TypeAlias = int | float | str | bool
BaseTypes: TypeAlias = AtomicTypes | dict[str, AtomicTypes] | list[AtomicTypes]