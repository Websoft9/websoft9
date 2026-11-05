"""Import-time module stand-ins that do not leak into the rest of the pytest session.

Several AppHub modules pull in optional runtime dependencies (``aiodocker``, ``git``, ``keyring``,
...). Test modules replace them with ``types.ModuleType`` stand-ins so the module under test can be
imported. Writing those stand-ins straight into ``sys.modules`` at import time used to leave them
there for every later test module in the same pytest process, which made the whole suite pass or
fail depending on file order.

``stub_module`` records whatever was registered before, so ``restore_module_stubs`` can put the real
entry back as soon as the module under test has captured the names it needs.
"""

import sys

_stubbed_previous = {}
_stubbed_names = []


def stub_module(name, module, *, override=False):
    """Register ``module`` as ``name`` and remember the previous entry for restoration."""
    if name not in _stubbed_previous:
        _stubbed_previous[name] = sys.modules.get(name)
        _stubbed_names.append(name)
    if override or name not in sys.modules:
        sys.modules[name] = module


def restore_module_stubs():
    """Undo every ``stub_module`` call made since the last restore."""
    for name in _stubbed_names:
        previous = _stubbed_previous[name]
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    _stubbed_names.clear()
    _stubbed_previous.clear()


def snapshot_modules() -> set[str]:
    """Record which modules are already imported, to find the ones imported under stand-ins."""
    return set(sys.modules)


def forget_modules(*names: str) -> list[str]:
    """Drop ``names`` from ``sys.modules`` so the next import rebuilds them.

    Restoring ``sys.modules`` is not enough on its own: a module imported *while* stand-ins were
    registered keeps the stand-in in its own namespace for good. ``src.services.app_manager``
    imports ``src.services.install_secrets``, which binds ``PasswordGenerator`` - imported under a
    stand-in, that binding is a placeholder, and every later test calling
    ``initialize_install_secrets`` then fails.

    Only the named modules are dropped: evicting every module that was imported under the stand-ins
    would also drop shared foundations such as ``src.core.exception``, and the already-imported
    code would then raise one ``CustomException`` class while later tests catch another.
    """
    forgotten = []
    for name in names:
        if sys.modules.pop(name, None) is not None:
            forgotten.append(name)
    return forgotten


def forget_modules_imported_since(snapshot: set[str], *, protect=("src.core.",)) -> list[str]:
    """Drop the packages that were first imported while stand-ins were registered.

    Use this after restoring stand-ins that are imported by a large slice of the application (the
    CLI pulls in most of ``src.services``). Those modules bound the stand-in classes at import time,
    so a later test that patches the real class has no effect. ``protect`` keeps the shared
    foundations - most importantly ``src.core.exception``, whose classes must stay identical for
    every module that already imported them.
    """
    forgotten = []
    for name in sorted(set(sys.modules) - snapshot):
        if not name.startswith("src.") or name.startswith(protect):
            continue
        sys.modules.pop(name, None)
        forgotten.append(name)
    return forgotten
