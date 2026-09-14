# AI Assistant - PLC / OEE Monitoring

Collection of Python projects that connect to industrial PLCs (Omron NX1P2 via FINS, Siemens S7 via snap7), log tag data to SQLite, calculate OEE, and expose MCP servers + web dashboards.

## Projects

| Folder | PLC | Notes |
|---|---|---|
| `Omron_PLC_AI/` | Omron NX1P2 (FINS) | MCP server, dashboard, OEE calculator, ERP sync |
| `AI_Assisstant_PLC/PLC_MCP_Server/` | Siemens S7 (snap7) | MCP server, dashboard, OEE calculator, DB3 logging |
| `AI_Assisstant_PLC/PLC_AI_Project/` | Siemens S7 (snap7) | Simple read/write test scripts |
| `AI_Assisstant_PLC_MCP Server/` | - | CPU info test utility |

## Setup

Each project has its own virtual environment and requirements file:

```powershell
# Omron project
cd Omron_PLC_AI
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# Siemens MCP server
cd AI_Assisstant_PLC\PLC_MCP_Server
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Usage

```powershell
# Omron MCP server
cd Omron_PLC_AI
venv\Scripts\python server.py

# Omron dashboard
venv\Scripts\python dashboard.py

# Siemens MCP server
cd AI_Assisstant_PLC\PLC_MCP_Server
venv\Scripts\python server.py
```

## Notes

- `frappe_docker/` is a separate upstream clone and is excluded from this repo.
- Local data files (`*.db`, `*.csv`, `logs/`) are gitignored; `tag_map.json` / config files are committed.