from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
REGIONS = ["华东", "华南", "华北", "华中", "西南", "西北", "东北"]
SEGMENTS = ["个人客户", "企业客户", "会员客户"]
CATEGORIES = ["家用电器", "数码配件", "家居用品", "办公用品", "服饰鞋包", "食品饮料", "美妆个护", "运动户外"]
CUSTOMER_STATUS = ["active", "inactive"]
PAYMENT_STATUS = ["paid", "refunded", "cancelled"]


def write_csv(path: Path, rows, headers=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = headers or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(seed: int = 20261008):
    rng = random.Random(seed)
    start = date(2024, 1, 1)
    customers = []
    for idx in range(1, 401):
        customers.append({
            "customer_id": f"C{idx:06d}",
            "name": f"客户{idx:04d}",
            "email": f"customer{idx:04d}@example.com",
            "region": rng.choice(REGIONS),
            "segment": rng.choice(SEGMENTS),
            "join_date": (start + timedelta(days=rng.randint(0, 700))).isoformat(),
            "status": rng.choice(CUSTOMER_STATUS),
        })

    products = []
    for idx in range(1, 101):
        price = round(rng.uniform(29, 2999), 2)
        products.append({
            "product_id": f"P{idx:04d}",
            "product_name": f"商品{idx:04d}",
            "category": rng.choice(CATEGORIES),
            "unit_cost": f"{price * rng.uniform(0.5, 0.75):.2f}",
            "list_price": f"{price:.2f}",
            "status": "active" if rng.random() > 0.08 else "inactive",
        })

    orders = []
    for idx in range(1, 6001):
        customer = rng.choice(customers)
        product = rng.choice(products)
        order_date = start + timedelta(days=rng.randint(0, 700))
        orders.append({
            "order_id": f"O{idx:08d}",
            "order_date": order_date.isoformat(),
            "customer_id": customer["customer_id"],
            "product_id": product["product_id"],
            "quantity": rng.choices([1, 2, 3, 4, 5], weights=[45, 25, 15, 10, 5], k=1)[0],
            "unit_price": product["list_price"],
            "discount_rate": f"{rng.choices([0, 0.05, 0.1, 0.15, 0.2], weights=[55, 18, 14, 9, 4], k=1)[0]:.2f}",
            "payment_status": rng.choices(PAYMENT_STATUS, weights=[88, 7, 5], k=1)[0],
            "region": customer["region"],
        })

    # Intentional known defects for testing all rule families.
    customers[0]["email"] = "bad-email"
    customers[1]["email"] = ""
    customers[2]["status"] = "unknown"
    customers[3]["customer_id"] = ""
    customers[4]["join_date"] = (date(2026, 12, 31)).isoformat()
    customers.append(dict(customers[5]))  # Duplicate primary key.

    products[0]["unit_cost"] = "-10.00"
    products[1]["category"] = ""
    products[2]["list_price"] = "0.00"
    products.append(dict(products[3]))  # Duplicate product key.

    orders[0]["quantity"] = -2
    orders[1]["unit_price"] = "-99.00"
    orders[2]["discount_rate"] = "0.80"
    orders[3]["payment_status"] = "unknown"
    orders[4]["order_date"] = "2026-12-31"
    orders[5]["customer_id"] = "C999999"
    orders[6]["product_id"] = "P9999"
    orders[7]["region"] = "海外"
    orders.append(dict(orders[8]))  # Duplicate order key.
    orders[9]["order_id"] = ""

    write_csv(RAW_DIR / "customers.csv", customers)
    write_csv(RAW_DIR / "products.csv", products)
    write_csv(RAW_DIR / "orders.csv", orders)
    print({"customers": len(customers), "products": len(products), "orders": len(orders)})


if __name__ == "__main__":
    main()