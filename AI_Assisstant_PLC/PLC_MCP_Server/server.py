from mcp.server import MCPServer
from plc import PLC


# ==========================
# CREATE MCP SERVER
# ==========================

mcp = MCPServer("PLC Controller")


# ==========================
# CREATE PLC OBJECT
# ==========================

plc = PLC()


# Connect PLC

plc.connect()



# ==========================
# TOOL 1
# LIST ALL TAGS
# ==========================

@mcp.tool()
def list_tags():

    """
    List all available tags in the PLC tag map (DB3 'Data').

    Returns each tag name, its DB number, byte offset, data type,
    and bit offset (for bool tags).
    """

    return str(plc.list_tags())



# ==========================
# TOOL 2
# READ TAG BY NAME
# ==========================

@mcp.tool()
def read_tag(name: str):

    """
    Read a single PLC tag by name from DB3.

    Example:
    read_tag("Enable DG")
    read_tag("DG Out Temp RD 0")
    read_tag("OEE Out OK Count")
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
    Read all tags from DB3 in a single operation.

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
    Write a value to a PLC tag by name in DB3.

    Examples:
    write_tag("Enable DG", True)
    write_tag("Enable OEE", False)
    write_tag("OEE Out Step ID", 5)
    write_tag("DG Out Temp RD 0", 25.5)
    """

    result = plc.write_tag(name, value)

    return str(result)



# ==========================
# START MCP SERVER
# ==========================

if __name__ == "__main__":

    mcp.run()