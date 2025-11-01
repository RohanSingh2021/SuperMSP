from pathlib import Path
import sqlite3
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import arrow


def run_license_audit_computation(output_dir: Path):
    """
    License Audit Computation using SQLite database instead of JSON files.
    Reads data from 'databases/msp_data.db' and generates JSON reports.
    """

    DB_PATH = Path("databases/msp_data.db")
    THRESHOLD_DAYS = 90

    def fetch_all(query: str, params: tuple = ()) -> List[dict]:
        """Helper to fetch query results as list of dicts"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    
    def load_activity_logs() -> List[dict]:
        return fetch_all("SELECT * FROM activity_logs")

    def load_customer_company_employees() -> List[dict]:
        customer_company_employees = fetch_all("SELECT * FROM customer_company_employees")

        for emp in customer_company_employees:
            assigned = emp.get("assigned_software")
            if assigned:
                try:
                    emp["assigned_software"] = json.loads(assigned)
                except json.JSONDecodeError:
                    emp["assigned_software"] = []
            else:
                emp["assigned_software"] = []
        return customer_company_employees

    def load_role_software_map() -> Dict[str, List[str]]:
        """Convert role_software_map table into {role: [software_name, ...]}"""
        data = fetch_all("SELECT * FROM role_software_map")
        role_map: Dict[str, List[str]] = {}
        for row in data:
            role = row["role"].strip()
            software = row["software_name"].strip()
            role_map.setdefault(role, []).append(software)
        return role_map

    def load_software_inventory() -> List[dict]:
        return fetch_all("SELECT * FROM software_inventory")

    def normalize_name(name: str) -> str:
        return name.strip().lower()

    def iso_to_arrow(dt_str: str) -> arrow.Arrow:
        return arrow.get(dt_str)

    def write_json(obj: Any, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        def json_default(o):
            if isinstance(o, arrow.Arrow):
                return o.isoformat()
            return str(o)

        Path(path).write_text(json.dumps(obj, indent=2, default=json_default), encoding="utf-8")

 
    def index_inventory(inventory_list: List[dict]) -> Dict[str, dict]:
        idx: Dict[str, dict] = {}
        for item in inventory_list:
            name = item.get("name")
            if name:
                idx[normalize_name(name)] = item
        return idx

    def normalize_role_map(role_map_raw: Dict[str, List[str]]) -> Dict[str, set]:
        out: Dict[str, set] = {}
        for role, arr in role_map_raw.items():
            out[role.strip()] = set([normalize_name(x) for x in arr])
        return out

    def index_customer_company_employees(customer_company_employees_raw: List[dict]) -> Dict[str, dict]:
        idx: Dict[str, dict] = {}
        for emp in customer_company_employees_raw:
            if "employee_id" not in emp:
                continue
            eid = emp["employee_id"]
            assigned = emp.get("assigned_software", [])
            emp["_assigned_normalized"] = [
                normalize_name(s.get("name")) for s in assigned
                if isinstance(s, dict) and s.get("name")
            ]
            idx[eid] = emp
        return idx

    def index_activity_logs(activity_raw: List[dict]) -> List[dict]:
        return activity_raw

    def detect_anomalous_access(customer_company_employees_raw: Any, role_map_raw: Any, inventory_raw: Any) -> List[dict]:
        customer_company_employees = index_customer_company_employees(customer_company_employees_raw)
        role_map = normalize_role_map(role_map_raw)
        inventory = index_inventory(inventory_raw)

        flagged: List[dict] = []
        for eid, emp in customer_company_employees.items():
            role = (emp.get("role") or "").strip()
            allowed = role_map.get(role, set())
            assigned_norm = emp.get("_assigned_normalized", [])
            for app_name in assigned_norm:
                if app_name not in allowed:
                    inv_item = inventory.get(app_name)
                    license_cost_usd = inv_item.get("license_cost_usd") if inv_item else None
                    license_type = inv_item.get("license_type") if inv_item else None
                    software_display = inv_item.get("name", app_name) if inv_item else app_name
                    flagged.append({
                        "employee_id": eid,
                        "employee_name": emp.get("name"),
                        "role": role,
                        "software_name": software_display,
                        "software_key": app_name,
                        "license_type": license_type,
                        "license_cost_usd": license_cost_usd,
                        "reason": "Role not typically allowed to use this software",
                    })
        return flagged

    def detect_unused_software(
        activity_raw: Any,
        customer_company_employees_raw: Any,
        inventory_raw: Any,
        threshold_days: int = 90,
        now: Optional[arrow.Arrow] = None
    ) -> List[dict]:
        now = now or arrow.utcnow()
        activities = index_activity_logs(activity_raw)
        customer_company_employees = index_customer_company_employees(customer_company_employees_raw)
        inventory = index_inventory(inventory_raw)

        last_used_map: Dict[Tuple[str, str], arrow.Arrow] = {}

        for act in activities:
            emp = act.get("employee_id")
            soft = act.get("software_name")
            if not emp or not soft:
                continue
            soft_norm = normalize_name(soft)
            last_used = act.get("last_used")
            if not last_used:
                continue
            try:
                t = iso_to_arrow(last_used)
            except Exception:
                continue
            key = (emp, soft_norm)
            prev = last_used_map.get(key)
            if not prev or t > prev:
                last_used_map[key] = t

        flagged: List[dict] = []
        for eid, emp in customer_company_employees.items():
            assigned = emp.get("_assigned_normalized", [])
            for app in assigned:
                key = (eid, app)
                last = last_used_map.get(key)
                days = None
                last_used_iso = None
                if last:
                    days = (now - last).days
                    last_used_iso = last.isoformat()
                if last is None or days is None or days > threshold_days:
                    inv = inventory.get(app)
                    license_cost_usd = inv.get("license_cost_usd") if inv else None
                    flagged.append({
                        "employee_id": eid,
                        "employee_name": emp.get("name"),
                        "software_name": inv.get("name") if inv else app,
                        "software_key": app,
                        "last_used_iso": last_used_iso,
                        "days_since_last_use": days if days is not None else "NEVER_USED",
                        "license_cost_usd": license_cost_usd,
                        "reason": f"Not used in last {threshold_days} days" if days is not None else "Never used"
                    })
        return flagged

  
    def main():
        print("Connecting to SQLite database...")
        activity_logs = load_activity_logs()
        customer_company_employees = load_customer_company_employees()
        role_map = load_role_software_map()
        inventory = load_software_inventory()

        print("Data successfully loaded from SQLite")

        print("Running Anomalous Access Detector...")
        anomalies = detect_anomalous_access(customer_company_employees, role_map, inventory)
        print(f"→ Found {len(anomalies)} anomalous software accesses")

        print(f"Running Unused Software Detector (> {THRESHOLD_DAYS} days)...")
        unused = detect_unused_software(activity_logs, customer_company_employees, inventory, THRESHOLD_DAYS)
        print(f"→ Found {len(unused)} unused software licenses")

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(anomalies, str(out_dir / "flagged_anomalous_access.json"))
        write_json(unused, str(out_dir / "flagged_unused_software.json"))

        print(f"Results saved to {out_dir}")

    main()


if __name__ == "__main__":
    run_license_audit_computation(Path("output"))
