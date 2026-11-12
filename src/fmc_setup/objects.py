"""Helpers for FMC object references."""


def by_name(items):
    return {item["name"]: item for item in items}


def ref(obj):
    """Reference to an FMC object used inside other objects."""
    return {"type": obj["type"], "id": obj["id"], "name": obj["name"]}


def resolve(names, *lookups):
    """Finds object references by name in the lookups (in order). Returns (references, missing names)."""
    objects, missing, seen = [], [], set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        obj = next((lookup[name] for lookup in lookups if name in lookup), None)
        if obj is None:
            missing.append(name)
        else:
            objects.append(ref(obj))
    return objects, missing
