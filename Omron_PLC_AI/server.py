import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import MCPServer
from omron_plc import OmronPLC


# ==========================
# CREATE MCP SERVER
# ==========================

mcp = MCPServer("Omron PLC Controller")


# ==========================
# CREATE PLC OBJECT
# ==========================

plc = OmronPLC()
plc.connect()



# ==========================
# TOOL 1
# LIST ALL TAGS
# ==========================

@mcp.tool()
def list_tags():

    """
    List all available tags in the Omron PLC tag map (NX1P2).

    Returns each tag name, its FINS address, data type, and comment.
    """

    return str(plc.list_tags())



# ==========================
# TOOL 2
# READ TAG BY NAME
# ==========================

@mcp.tool()
def read_tag(name: str):

    """
    Read a single PLC tag by name from the Omron NX1P2.

    Example:
    read_tag("OK Count")
    read_tag("Emergency Stop")
    read_tag("Temp RTD1")
    """

    result = plc.read_tag(name)

    return str(result)



# ==========================
# TOOL 3
# READ ALL TAGS
# ==========================

@mcp.tool()
def read_all_tags():

    """
    Read all 27 tags from the Omron NX1P2 in one operation.

    Returns a dictionary of tag name -> value for every tag in the tag map.
    """

    result = plc.read_all_tags()

    return str(result)



# ==========================
# TOOL 4
# WRITE TAG BY NAME
# ==========================

@mcp.tool()
def write_tag(name: str, value):

    """
    Write a value to a PLC tag by name on the Omron NX1P2.

    Examples:
    write_tag("LED RED", True)
    write_tag("LED GREEN", False)
    """

    result = plc.write_tag(name, value)

    return str(result)



# ==========================
# START MCP SERVER
# ==========================

if __name__ == "__main__":

    mcp.run()