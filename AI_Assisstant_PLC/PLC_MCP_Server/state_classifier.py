from datetime import datetime


def classify_state(tags):
    """
    Classify machine state from PLC tag values.

    Returns:
        (state, reason) where state is one of:
        - 'RUNNING'   : machine producing
        - 'DOWN'      : machine stopped due to error / e-stop
        - 'IDLE'      : machine not running but no error
        - 'OFFLINE'   : enable flags off
    """

    # OEE module
    if tags.get("Enable OEE"):

        if tags.get("OEE E-Stop"):
            return ("DOWN", "OEE E-Stop pressed")

        if tags.get("OEE Out Machine ERR"):
            return ("DOWN", "OEE Machine Error")

        if tags.get("OEE Out Machine OK"):
            return ("RUNNING", None)

        if tags.get("OEE Auto Man"):
            return ("IDLE", "OEE in Auto/Man idle")
        else:
            return ("IDLE", "OEE not in Auto")

    # DG module
    if tags.get("Enable DG"):

        if tags.get("DG E-Stop"):
            return ("DOWN", "DG E-Stop pressed")

        if tags.get("DG Out Machine ERR"):
            return ("DOWN", "DG Machine Error")

        if tags.get("DG Out Machine OK"):
            return ("RUNNING", None)

        return ("IDLE", "DG idle")

    # Neither enabled
    return ("OFFLINE", "Both DG and OEE disabled")