# skills.md — UC-0C: Number That Looks Right

## Skill Set for BudgetAnalystAgent

---

### Skill 1: CSV Ingestion with Schema Validation

**Purpose:** Load `ward_budget.csv` and validate expected columns are present before any computation.

**Steps:**
1. Read CSV using `csv.DictReader`
2. Assert presence of required columns: `ward`, `category`, `year`, `amount`
3. Cast `year` to `int` and `amount` to `float`; skip or flag rows where casting fails
4. Print row count and column names as a sanity check

**Failure mode caught:** Silent data loss when columns are misnamed or rows have type errors

---

### Skill 2: Strict Per-Ward Per-Category Grouping

**Purpose:** Group budget records so each bucket contains exactly one ward + one category.

**Steps:**
1. Build a nested dict: `data[ward][category][year] = amount`
2. Never use a flat sum across wards
3. For each (ward, category) pair, collect all years available

**Failure mode caught:** Silent cross-ward aggregation that produces numbers that look right but are sums of multiple wards

---

### Skill 3: Year-over-Year Growth Rate Computation

**Purpose:** Compute the growth rate for the most recent year vs the previous year.

**Formula:**
```
growth_rate = ((amount_current - amount_previous) / amount_previous) * 100
```

**Rules:**
- Identify the two most recent years available for each (ward, category)
- If only one year exists → growth_rate = `null`
- If previous year amount = 0 → growth_rate = `null` (no division by zero)
- Round to 2 decimal places

**Failure mode caught:** Division-by-zero crashes and misleading growth rates from wrong year pairing

---

### Skill 4: Output Writer

**Purpose:** Write `growth_output.csv` with one row per (ward, category).

**Output columns:**
| Column | Type | Description |
|---|---|---|
| `ward` | string | Ward name/ID |
| `category` | string | Budget category |
| `year_current` | int | The most recent year in the data |
| `amount_current` | float | Budget amount for current year |
| `year_previous` | int | The previous year |
| `amount_previous` | float | Budget amount for previous year |
| `growth_rate_pct` | float or null | YoY growth percentage |

**Failure mode caught:** Missing rows, incorrect column ordering, null not written as empty string

---

### Skill 5: Anomaly Flagging

**Purpose:** Identify and report (ward, category) pairs with suspicious data.

**Flags:**
- `MISSING_YEAR`: only one year of data exists
- `ZERO_BASELINE`: previous year amount is 0
- `NEGATIVE_AMOUNT`: any amount value is negative
- `HIGH_GROWTH`: growth rate exceeds 200% (may indicate data error)

**Output:** Printed to console as warnings; also written to `anomaly_report.txt`

---

### Skill 6: Scope Enforcement Check (Self-Audit)

**Purpose:** After generating output, verify no row contains aggregated-across-wards data.

**Check:** Count unique `ward` values in input vs in output — they must match exactly.  
**Check:** Count unique `category` values in input vs in output — they must match exactly.  
**Check:** Total output rows must equal `unique_wards × unique_categories` (for combinations that exist in data).

**Failure mode caught:** Missing ward-category combinations silently dropped during grouping
