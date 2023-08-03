from typing import Union, cast
from xml.dom.minidom import Element, Text


def get_text(node: Union[Element, Text]) -> str:
    """Recursively concatenate text nodes in the `node`."""
    if node.nodeType == node.TEXT_NODE:
        # This casting is plain ugly, but otherwise mypy doesn't know it's str.
        return str(cast(Text, node).data)
    return "".join(
        get_text(child)
        for child in node.childNodes
    )