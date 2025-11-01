
from pathlib import Path
import sqlite3
import json
from collections import defaultdict
from datetime import datetime


def run_company_ticket_computation(output_dir: Path):
    """Compute company-level ticket statistics from SQLite DB and output JSON."""

    DB_PATH = Path("databases") / "msp_data.db"

   
    def parse_datetime(dt_str):
        """Parse ISO datetime string safely."""
        if not dt_str:
            return None
        try:
            if dt_str.endswith('Z'):
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    from datetime import timezone
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception:
            return None

    def fetch_all_data():
        """Fetch all required tables from SQLite database."""
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Database not found at {DB_PATH}")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  

        data = {}
        try:
            data["companies"] = conn.execute("SELECT * FROM companies").fetchall()
            data["tickets"] = conn.execute("SELECT * FROM tickets").fetchall()
            data["ticket_categories"] = conn.execute("SELECT * FROM ticket_categories").fetchall()
            data["ticket_category_count"] = conn.execute("SELECT * FROM ticket_category_count").fetchall()
        finally:
            conn.close()

        return data

    def analyze_company_data(data):
        """Analyze ticket data for each company using SQLite data."""

        companies = data["companies"]
        tickets = data["tickets"]
        ticket_categories = data["ticket_categories"]
        ticket_category_count = data["ticket_category_count"]

        category_map = {cat["category_id"]: cat["category_name"] for cat in ticket_categories}

        company_stats = defaultdict(lambda: {
            "resolved_tickets": 0,
            "total_resolution_time": 0,
            "category_counts": defaultdict(int),
            "company_name": "",
            "last_count_update": {}
        })

        company_names = {c["company_id"]: c["company_name"] for c in companies}

        for count_entry in ticket_category_count:
            cid = count_entry["company_id"]
            cat_id = count_entry["category_id"]
            cat_name = category_map.get(cat_id, f"Category {cat_id}")

            company_stats[cid]["category_counts"][cat_name] = count_entry["total_tickets"]
            company_stats[cid]["last_count_update"][cat_id] = parse_datetime(count_entry["last_updated"])
            company_stats[cid]["company_name"] = company_names.get(cid, "Unknown")

        for ticket in tickets:
            cid = ticket["company_id"]
            if cid is None:
                continue
                
            cat_id = ticket["category_id"]
            cat_name = category_map.get(cat_id, f"Category {cat_id}")

            if cid not in company_stats:
                company_stats[cid]["company_name"] = company_names.get(cid, "Unknown")

            ticket_created = parse_datetime(ticket["created_at"])
            last_update = company_stats[cid]["last_count_update"].get(cat_id)

            
            should_increment = False
            if last_update is None:
                should_increment = True
            elif ticket_created is not None and last_update is not None:
                should_increment = ticket_created > last_update
            elif ticket_created is not None:
                should_increment = True
            
            if should_increment:
                company_stats[cid]["category_counts"][cat_name] += 1

        for ticket in tickets:
            cid = ticket["company_id"]
            if cid is None:
                continue
            
            if ticket["status"] == "Closed" and ticket["resolved_at"]:
                company_stats[cid]["resolved_tickets"] += 1
                if ticket["resolution_time_hours"]:
                    company_stats[cid]["total_resolution_time"] += ticket["resolution_time_hours"]

        result = []
        valid_company_ids = [cid for cid in company_stats.keys() if cid is not None]
        for cid in sorted(valid_company_ids):
            stats = company_stats[cid]
            avg_resolution_time = 0

            if stats["resolved_tickets"] > 0:
                avg_resolution_time = round(
                    stats["total_resolution_time"] / stats["resolved_tickets"], 2
                )

            company = next((c for c in companies if c["company_id"] == cid), None)
            satisfaction = company["happiness_score"] if company else 0

            result.append({
                "company_id": cid,
                "company_name": stats["company_name"],
                "resolved_tickets": stats["resolved_tickets"],
                "average_resolution_time_hours": avg_resolution_time,
                "employee_satisfaction": satisfaction,
                "tickets_by_category": dict(stats["category_counts"])
            })

        return result

    try:
        data = fetch_all_data()
        analysis_result = analyze_company_data(data)

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        output_file = output_dir_path / "company_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)

        print(f"Company ticket analysis complete! Results saved to {output_file}")
        print(f"Processed {len(analysis_result)} companies")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
    except Exception as e:
        import traceback
        print(f"Unexpected Error: {e}")
        print(f"Full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    run_company_ticket_computation(Path("output"))
