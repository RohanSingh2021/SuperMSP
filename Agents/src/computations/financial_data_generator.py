
from pathlib import Path
import sqlite3
import json
from datetime import datetime, timedelta


def run_financial_computation():
    """Performs financial computations for MSP companies using SQLite database."""

    DB_PATH = Path("databases") / "msp_data.db"
    OUTPUT_DIR = Path("output")
    OUTPUT_DIR.mkdir(exist_ok=True)

 
    def fetch_all_data():
        """Fetch all relevant tables from SQLite database."""
        if not DB_PATH.exists():
            raise FileNotFoundError(f"Database not found at {DB_PATH}")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  
        try:
            companies = conn.execute("SELECT * FROM companies").fetchall()
            payments = conn.execute("SELECT * FROM payments").fetchall()
            tickets = conn.execute("SELECT * FROM tickets").fetchall()
        finally:
            conn.close()

        return companies, payments, tickets

 
    BASE_INFLATION_RATE = 0.06  
    TICKET_VOLUME_WEIGHT = 0.15
    ENDPOINT_WEIGHT = 0.10
    PAYMENT_DELAY_PENALTY = 0.00066  
    HAPPINESS_WEIGHT = 0.15
    CONTRACT_LENGTH_DISCOUNT = {
        1: 0.00,
        2: 0.03,
        3: 0.05
    }

   
    companies, payments, tickets = fetch_all_data()
    current_date = datetime.now()


    payments_by_company = {}
    for p in payments:
        cid = p["company_id"]
        payments_by_company.setdefault(cid, []).append(p)

    tickets_by_company = {}
    for t in tickets:
        cid = t["company_id"]
        tickets_by_company[cid] = tickets_by_company.get(cid, 0) + 1


    overdue_payments = []
    upcoming_due_dates = []
    delayed_payments = []
    price_revisions = []

    

    for company in companies:
        cid = company["company_id"]
        company_payments = payments_by_company.get(cid, [])
        company_tickets = tickets_by_company.get(cid, 0)

        for payment in company_payments:
            try:
                due_date = datetime.strptime(payment["due_date"], "%Y-%m-%d")
            except Exception:
                continue

            payment_date = None
            if payment["payment_date"]:
                try:
                    payment_date = datetime.strptime(payment["payment_date"], "%Y-%m-%d")
                except Exception:
                    payment_date = None

            if payment["status"] != "Paid" and current_date > due_date:
                days_overdue = (current_date - due_date).days
                overdue_payments.append({
                    "company_id": cid,
                    "company_name": company["company_name"],
                    "contact_person": company["contact_person"],
                    "contact_email": company["contact_email"],
                    "payment_id": payment["payment_id"],
                    "invoice_month": payment["invoice_month"],
                    "amount_due": payment["amount_due"],
                    "due_date": payment["due_date"],
                    "days_overdue": days_overdue,
                    "status": payment["status"]
                })

            elif payment["status"] == "Paid" and payment_date and payment_date > due_date:
                days_delayed = (payment_date - due_date).days
                delayed_payments.append({
                    "company_id": cid,
                    "company_name": company["company_name"],
                    "contact_person": company["contact_person"],
                    "contact_email": company["contact_email"],
                    "payment_id": payment["payment_id"],
                    "invoice_month": payment["invoice_month"],
                    "amount_due": payment["amount_due"],
                    "due_date": payment["due_date"],
                    "payment_date": payment["payment_date"],
                    "days_delayed": days_delayed,
                    "status": payment["status"],
                    "delay_penalty_applied": round(payment["amount_due"] * days_delayed * PAYMENT_DELAY_PENALTY, 2)
                })

            elif payment["status"] != "Paid" and 0 <= (due_date - current_date).days <= 15:
                days_until_due = (due_date - current_date).days
                upcoming_due_dates.append({
                    "company_id": cid,
                    "company_name": company["company_name"],
                    "contact_person": company["contact_person"],
                    "contact_email": company["contact_email"],
                    "payment_id": payment["payment_id"],
                    "invoice_month": payment["invoice_month"],
                    "amount_due": payment["amount_due"],
                    "due_date": payment["due_date"],
                    "days_until_due": days_until_due,
                    "status": payment["status"]
                })

        inflation_factor = BASE_INFLATION_RATE

        endpoints = company["endpoints_scale"] or 0
        avg_tickets_per_endpoint = (company_tickets / endpoints) if endpoints > 0 else 0
        ticket_factor = min(avg_tickets_per_endpoint / 0.05, 1.0) * TICKET_VOLUME_WEIGHT

        if endpoints >= 2000:
            endpoint_factor = -0.05
        elif endpoints >= 1000:
            endpoint_factor = 0.0
        else:
            endpoint_factor = 0.05
        endpoint_factor *= ENDPOINT_WEIGHT

        total_delay_days = 0
        for p in company_payments:
            if p["payment_date"] and p["due_date"]:
                try:
                    payment_dt = datetime.strptime(p["payment_date"], "%Y-%m-%d")
                    due_dt = datetime.strptime(p["due_date"], "%Y-%m-%d")
                    if payment_dt > due_dt:
                        total_delay_days += (payment_dt - due_dt).days
                except Exception:
                    continue
        
        avg_delay_days = total_delay_days / len(company_payments) if company_payments else 0
        delay_penalty = avg_delay_days * PAYMENT_DELAY_PENALTY

        happiness_score = company["happiness_score"] or 0
        if happiness_score >= 4.5:
            happiness_factor = 0.05
        elif happiness_score >= 4.0:
            happiness_factor = 0.0
        elif happiness_score >= 3.5:
            happiness_factor = -0.03
        else:
            happiness_factor = -0.05
        happiness_factor *= HAPPINESS_WEIGHT

        contract_years = company["contract_length_years"] or 1
        if contract_years >= 3:
            length_discount = CONTRACT_LENGTH_DISCOUNT[3]
        elif contract_years == 2:
            length_discount = CONTRACT_LENGTH_DISCOUNT[2]
        else:
            length_discount = CONTRACT_LENGTH_DISCOUNT[1]

        total_revision_factor = (
            inflation_factor
            + ticket_factor
            + endpoint_factor
            + delay_penalty
            + happiness_factor
            - length_discount
        )
        total_revision_factor = max(-0.10, min(0.25, total_revision_factor))

        recent_payment = company_payments[-1] if company_payments else None
        current_monthly_cost = recent_payment["amount_due"] if recent_payment else 0
        revised_monthly_cost = current_monthly_cost * (1 + total_revision_factor)

        price_revisions.append({
            "company_id": cid,
            "company_name": company["company_name"],
            "contact_person": company["contact_person"],
            "contact_email": company["contact_email"],
            "endpoints_scale": endpoints,
            "happiness_score": happiness_score,
            "tickets_raised": company["tickets_raised"],
            "contract_length_years": contract_years,
            "avg_payment_delay_days": round(total_delay_days / len(company_payments), 2) if company_payments else 0,
            "current_monthly_cost": round(current_monthly_cost, 2),
            "revision_factor": round(total_revision_factor, 4),
            "revision_percentage": f"{round(total_revision_factor * 100, 2)}%",
            "revised_monthly_cost": round(revised_monthly_cost, 2),
            "annual_cost_change": round((revised_monthly_cost - current_monthly_cost) * 12, 2),
            "factor_breakdown": {
                "base_inflation": round(inflation_factor, 4),
                "ticket_volume_impact": round(ticket_factor, 4),
                "endpoint_scale_impact": round(endpoint_factor, 4),
                "payment_delay_penalty": round(delay_penalty, 4),
                "happiness_adjustment": round(happiness_factor, 4),
                "contract_length_discount": round(length_discount, 4)
            }
        })

    overdue_payments.sort(key=lambda x: x["days_overdue"], reverse=True)
    upcoming_due_dates.sort(key=lambda x: x["days_until_due"])
    delayed_payments.sort(key=lambda x: x["days_delayed"], reverse=True)
    price_revisions.sort(key=lambda x: x["revision_factor"], reverse=True)

 
    print("=" * 80)
    print("MSP FINANCIAL ANALYSIS REPORT (SQLite Version)")
    print("=" * 80)
    print(f"Report Generated: {current_date.strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"OVERDUE PAYMENTS: {len(overdue_payments)}")
    print(f"UPCOMING DUE DATES (Next 15 days): {len(upcoming_due_dates)}")
    print(f"DELAYED PAYMENTS (Paid after due date): {len(delayed_payments)}")
    print(f"PRICE REVISIONS CALCULATED FOR: {len(price_revisions)} COMPANIES\n")

    with open(OUTPUT_DIR / "overdue_payments.json", "w", encoding="utf-8") as f:
        json.dump(overdue_payments, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "upcoming_due_dates.json", "w", encoding="utf-8") as f:
        json.dump(upcoming_due_dates, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "delayed_payments.json", "w", encoding="utf-8") as f:
        json.dump(delayed_payments, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_DIR / "price_revisions.json", "w", encoding="utf-8") as f:
        json.dump(price_revisions, f, indent=2, ensure_ascii=False)

    print("JSON output files created successfully:")
    print("  - output/overdue_payments.json")
    print("  - output/upcoming_due_dates.json")
    print("  - output/delayed_payments.json")
    print("  - output/price_revisions.json")
    print("=" * 80)


if __name__ == "__main__":
    run_financial_computation()
