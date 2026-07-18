import requests
import json
import re
import csv
import time
from datetime import date, timedelta


def scrape_kino_date(target_date):
    """Scrape Kino TV results. Returns list of (date, numbers) for ~14 days."""
    url = "https://enloteria.com/resultados-super-kino-tv-%s" % target_date.strftime("%Y-%m-%d")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    except requests.RequestException:
        return []

    if resp.status_code != 200:
        return []

    json_ld = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        resp.text, re.DOTALL
    )
    if not json_ld:
        return []

    results = []
    for block in json_ld:
        try:
            data = json.loads(block)
            for event in data.get("@graph", []):
                if event.get("@type") != "Event":
                    continue
                start = event.get("startDate", "")[:10]
                if not start:
                    continue
                nums = []
                for prop in event.get("additionalProperty", []):
                    if re.match(r"N.mero \d+", prop.get("name", "")):
                        nums.append(int(prop["value"]))
                if len(nums) == 20:
                    results.append((date.fromisoformat(start), nums))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return results


def main():
    start = date(2023, 10, 9)
    end = date.today()

    all_results = {}
    current = start
    req_count = 0

    while current <= end:
        results = scrape_kino_date(current)
        for d, nums in results:
            if d not in all_results:
                all_results[d] = nums

        req_count += 1
        if req_count % 10 == 0:
            print("  requests=%d  dates=%d  latest=%s" % (
                req_count, len(all_results),
                max(all_results.keys()) if all_results else "?"
            ))

        current += timedelta(days=13)
        time.sleep(0.3)

    sorted_dates = sorted(all_results.keys())
    print("\n=== DONE ===")
    print("Requests: %d" % req_count)
    print("Unique dates: %d" % len(sorted_dates))
    if sorted_dates:
        print("Range: %s to %s" % (sorted_dates[0], sorted_dates[-1]))

    csv_path = "kino_tv_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Fecha"] + ["N%d" % i for i in range(1, 21)])
        for d in sorted_dates:
            w.writerow([d.isoformat()] + all_results[d])

    print("Saved: %s" % csv_path)
    print("\nLast 5:")
    for d in sorted_dates[-5:]:
        print("  %s: %s" % (d, all_results[d]))


if __name__ == "__main__":
    main()
