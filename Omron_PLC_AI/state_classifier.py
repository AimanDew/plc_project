def classify_state(tags):
    """
    Classify machine state from Omron PLC tag values.

    Returns:
        (state, reason) where state is one of:
        - 'RUNNING'   : machine producing (OEE mode, no errors)
        - 'DOWN'      : machine stopped due to error / e-stop
        - 'IDLE'      : machine not running but no error
        - 'OFFLINE'   : mode disabled or not in OEE
    """

    # Check E-Stop first (highest priority)
    # Note: "Emergency Stop" is pre-normalized by the logger (NC raw bit inverted),
    # so True here means the E-stop IS actually pressed.
    if tags.get("Emergency Stop"):
        return ("DOWN", "Emergency Stop pressed")

    # Check if in OEE mode
    if not tags.get("Operation Selector"):
        return ("OFFLINE", "Not in OEE mode (DG mode selected)")

    # Check tower lights for error state
    if tags.get("TL Red"):
        return ("DOWN", "Red tower light (error)")

    # Check if running (green TL or yellow TL active)
    if tags.get("TL Green"):
        return ("RUNNING", None)

    if tags.get("TL Yellow"):
        return ("IDLE", "Yellow tower light (waiting)")

    # Check Mode Auto/Man
    if tags.get("Mode Auto Man"):
        return ("IDLE", "Manual mode")

    # Default: check if any output is active
    if tags.get("K1 Small Fan") or tags.get("K2 Large Fan") or tags.get("K3 Peltier"):
        return ("RUNNING", None)

    return ("IDLE", "No active signals")