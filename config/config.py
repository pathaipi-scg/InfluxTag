from dotenv import load_dotenv
from pathlib import Path
import os

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# SQL Server (new factory DB) -- holds TagMaster (new tags) + InfluxTag_Lists (mapping)
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DB = os.getenv("SQL_DB")
SQL_USER = os.getenv("SQL_USER")
SQL_PASS = os.getenv("SQL_PASS")

# InfluxDB 1.7 (source of the OLD tag names; one server, several databases)
INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT = int(os.getenv("INFLUX_PORT", "8086"))
INFLUX_USER = os.getenv("INFLUX_USER", "")
INFLUX_PASS = os.getenv("INFLUX_PASS", "")

# Databases offered in the "Influx_db" dropdown (old-tag sources).
# Comma separated in .env, e.g. INFLUX_DBS=IOT_CB,CB,CB_IOT,SBR
INFLUX_DBS = [
    d.strip()
    for d in os.getenv("INFLUX_DBS", "IOT_CB,CB,CB_IOT,SBR").split(",")
    if d.strip()
]

# Optional external script that rebuilds the OPC tag tree.
# Leave blank in .env to disable the "Refresh OPC Tree" button.
BROWSER_SCRIPT = os.getenv("BROWSER_SCRIPT", "")
