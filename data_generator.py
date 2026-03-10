import pandas as pd
import random
from datetime import datetime, timedelta

# -----------------------------
# CONFIG
# -----------------------------
NUM_ROWS = 500   # change to 1000, 5000, etc.
OUTPUT_FILE = "air_sample_sites.csv"

# Bihar districts (used as clusters)
BIHAR_DISTRICTS = [
    "Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga",
    "Purnia", "Ara", "Chapra", "Bettiah", "Saharsa",
    "Katihar", "Munger", "Samastipur", "Hajipur", "Sitamarhi"
]

TOWNS = [
    "Patna City", "Danapur", "Bihta", "Gaya Town",
    "Muzaffarpur Town", "Darbhanga Town", "Bhagalpur Town"
]

OWNERS = ["Airtel", "Indus", "ATC"]
YES_NO = ["Yes", "No"]
OK_NOT_OK = ["OK", "Not OK"]
YN = ["Y", "N"]

# -----------------------------
# Helper generators
# -----------------------------
def rand_date(start_year=2015):
    start = datetime(start_year, 1, 1)
    end = datetime.now()
    return start + timedelta(days=random.randint(0, (end - start).days))

def site_id(district, i):
    return f"{district[:3].upper()}-{str(i).zfill(4)}"

# -----------------------------
# Data generation
# -----------------------------
data = []

for i in range(1, NUM_ROWS + 1):
    district = random.choice(BIHAR_DISTRICTS)
    town = random.choice(TOWNS)

    bb_hours = round(random.uniform(1.0, 6.0), 2)
    bb_alarm = round(bb_hours + random.uniform(-1, 1), 2)

    row = {
        "Sl No.": i,
        "SITE ID": site_id(district, i),
        "Toco ID": f"TCO-{random.randint(10000,99999)}",
        "Cluster": district,
        "Site- Principal Owner": random.choice(OWNERS),
        "Toco": random.choice(OWNERS),
        "DG/Non-DG ULS": random.choice(["DG", "Non-DG"]),
        "DG/Non-DG": random.choice(["DG", "Non-DG"]),
        "DG Deployed Month": random.choice(range(1, 13)),
        "Macro/ULS": random.choice(["Macro", "ULS"]),
        "Fiber": random.choice(YES_NO),
        "OLT": random.choice(YES_NO),
        "URBAN/RURAL": random.choice(["Urban", "Rural"]),
        "District": district,
        "Town": town,
        "Top 8 Towns": random.choice(YES_NO),
        "NSS Town": random.choice(YES_NO),
        "On-Air Date": rand_date().date(),
        "Circle": "Bihar",
        "BZ": "East",

        "DG Automation\n(Yes/No)": random.choice(YES_NO),
        "DG Automation Status (As per SNMP)": random.choice(["Yes", "No", "OK"]),
        "Automation OK (Session Percentage)": round(random.uniform(60, 100), 1),

        "DG Fault Rectification Required\n(Yes/No)": random.choice(YES_NO),
        "DG restriction\n(Yes/No)": random.choice(YES_NO),
        "SMPS/IPMS/PIU Faulty\n(Yes/No)": random.choice(YES_NO),
        "LVD Correction required": random.choice(YES_NO),

        "RM Count\n(N+1)": random.choice(YES_NO),

        "HT/ LT/ Non EB": random.choice(["HT", "LT", "Non EB"]),
        "EB Upgrade\n(Yes/No)": random.choice(YES_NO),
        "EB Disconnection\n(Yes/No)": random.choice(YES_NO),

        "No of BB": random.randint(1, 4),
        "BB Type\n(Lith/VRLA)": random.choice(["Lithium", "VRLA"]),
        "BB Rating": random.choice([300, 400, 600]),

        "Battery Backup\n(Hrs)": bb_hours,
        "Battery Backup As per ALARM\n(Hrs)": bb_alarm,
        "Battery Backup Bucket": random.choice(["<2", "2-4", "4-6", ">6"]),

        "BB Low\n(Yes/No)": "Yes" if bb_hours < 4 else "No",
        "BB Replacement\n(Yes/No)": random.choice(YES_NO),
        "BB Enhancement\n(Yes/No)": random.choice(YES_NO),

        "Transformer Fault\n(Yes/No)": random.choice(YES_NO),
        "Solar Deployment\n(Yes/No)": random.choice(YES_NO),
        "Solar Genaration Status": random.choice(["Active", "Inactive"]),

        "Earthing Status\n(Ok/Not OK)": random.choice(OK_NOT_OK),
        "High Temperature\n(Yes/No)": random.choice(YES_NO),

        "TCU": random.choice(YES_NO),
        "TCU Status\n(OK/Not OK)": random.choice(OK_NOT_OK),

        "PM Status": random.choice(["Completed", "Pending"]),
        "PM Date": rand_date().date(),

        "MCU": random.choice(YES_NO),
        "IP-55": random.choice(YES_NO),
        "IP-55 STATUS\n(OK /Not OK)": random.choice(OK_NOT_OK),

        "Shelter With AC": random.choice(YES_NO),
        "AC Status": random.choice(["Working", "Not Working"]),
        "OD Cabinet USD": random.choice(YES_NO),

        "Cooling Unit\nUSD": random.choice(YES_NO),
        "Cooling Unit\n(OK/Not Ok)": random.choice(OK_NOT_OK),

        "IMD/VMD/RDG  Deployment\n(Yes/No)": random.choice(YES_NO),
        "Owner/Access Issues\n(Yes/No)": random.choice(YES_NO),
        "Technician Issues\n(Yes/No)": random.choice(YES_NO),

        "SDI": random.choice(YES_NO),
        "FF": random.choice(YES_NO),
        "Model Site": random.choice(YES_NO),

        "SNMP\nIntegrated\n(Y/N)": random.choice(YN),
        "SNMP\nCommunicated\n(Y/N)": random.choice(YN),

        "Fuel Sensor Installed\n(Y/N)": random.choice(YN),
        "Fuel Sensor\nCommunicated\n(Y/N)": random.choice(YN),

        "I-Hygien": random.choice(["Closed", "Open"]),
        "Alarm Compliance": random.choice(["Compliant", "Non-Compliant"]),
        "Compliance": random.choice(["Yes", "No"]),
        "TCU Status": random.choice(["OK", "Not OK"]),
        "Infra actions identifed": random.choice(["None", "BB Replace", "DG Service"]),
        "Status": random.choice(["OK", "Attention Required"])
    }

    data.append(row)

# -----------------------------
# Export
# -----------------------------
df = pd.DataFrame(data)
df.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Sample data generated: {OUTPUT_FILE} ({len(df)} rows)")
