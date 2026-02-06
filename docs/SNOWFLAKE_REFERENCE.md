# Snowflake Reference

Essential database context for querying NHS data. Read this every iteration when working with Snowflake.

---

## Snowflake MCP Server

Use `mcp__snowflake-mcp__*` functions to explore schema and test queries.

### Schema Discovery (USE THESE FIRST)
- `test_connection()` - Verify connectivity
- `list_databases()` - List accessible databases
- `list_schemas(database_name)` - List schemas in a database
- `list_tables(database, schema)` - List tables with descriptions
- `list_views(schema_name, database)` - List views with descriptions
- `describe_table(table_name, database)` - Get detailed table schema
- `describe_query(query, database)` - Preview query output columns without execution

### Query Execution
- `read_data(query, database, max_rows)` - Execute SELECT queries with row limits
- `read_data_paginated(query, database, page_size, page)` - Paginated results with total count
- `read_data_pandas(query, database, max_rows, output_format)` - Results in pandas-friendly formats

### Async Query Support (long-running queries)
- `execute_async(query, database)` - Submit asynchronously, returns query_id
- `get_query_status(query_id, database)` - Check status
- `get_async_results(query_id, database, max_rows)` - Retrieve results

### Usage Guidelines
- **ALWAYS** verify table structures and column names via MCP before writing queries
- Test with small result sets (`LIMIT 20`) before full execution
- Use `describe_query` to preview complex query outputs before running
- Use async queries for operations expected to take >30 seconds

---

## Database Overview

| Database | Purpose |
|----------|---------|
| `DATA_HUB` | **Analyst-curated** data warehouse - primary source for most queries |
| `PRIMARY_CARE` | Raw extracts from EMIS and TPP clinical systems |
| `NATIONAL` | NHS England national datasets (SUS, ECDS, MHSDS, etc.) |
| `FACTS_AND_DIMENSIONS_ALL_DATA` | External reference data (BNF, SNOMED, QOF clusters) |
| `REPORTING_DATASETS_ICB` | Reporting outputs and analyst workspaces (includes SCRATCHPAD) |

**Avoid**: `SYSTEM` database.

---

## Key Tables and Views

### DATA_HUB.DWH (Dimensions)

| View | Purpose | Key Columns |
|------|---------|-------------|
| `DimMedicineAndDevice` | Master medication/device reference | `ProductSnomedCode`, `TherapeuticMoietySnomedCode` (VTM), `BNFParagraphCode`, `StrengthDescription`, `ProductDescription` |
| `DimPerson` | Patient demographics | `PatientPseudonym`, `PersonKey`, `CurrentGeneralPractice`, `IsCurrentNWRegistered`, `YearMonthBirth` |
| `DimSnomedCode` | SNOMED code descriptions | `SnomedCode`, `SnomedDescription` |
| `DimOrganisationAndSite` | GP practices and NHS orgs | `SiteCode`, `OrganisationName`, `OrganisationSubType`, `IsSiteNorfolkAndWaveney`, `IsSiteActive` |
| `DimDate` | Date dimension | |
| `DimCondition` | Clinical conditions | Long-term condition flags |
| `DimDeprivation` | Deprivation rankings by area | |

**CRITICAL**:
- `ProductDescription` is the correct column for product names. `ProductName` does NOT exist.
- `IsLatest` does NOT exist in `DimMedicineAndDevice`.

### DATA_HUB.CDM (Common Data Model)

| View | Purpose | Key Columns |
|------|---------|-------------|
| `Acute__Conmon__PatientLevelDrugs` | HCD activity data | `PseudoNHSNoLinked`, `InterventionDate`, `DrugName`, `Price Actual` |

**Note**: HCD `PseudoNHSNoLinked` = GP `PatientPseudonym` for patient linkage.

### DATA_HUB.PHM (Population Health Management)

| View | Purpose | Key Columns |
|------|---------|-------------|
| `PrimaryCareClinicalCoding` | **Unified** clinical coding (EMIS + TPP, no duplicates) | `PatientPseudonym`, `SNOMEDCode`, `EventDateTime`, `NumericValue` |
| `PrimaryCareMedication` | **Unified** medication data (EMIS + TPP, no duplicates) | `PatientPseudonym`, `SNOMEDCode`, `DateMedicationStart`, `Quantity` |
| `ClinicalCodingClusterSnomedCodes` | SNOMED codes grouped by cluster | `ClusterId`, `SnomedCode` |
| `PersonCohort` | Pre-defined patient cohorts | |

**Prefer DATA_HUB.PHM unified views** over raw PRIMARY_CARE tables.

---

## Patient Identifiers

| Identifier | Source | Usage |
|------------|--------|-------|
| `PatientPseudonym` | DATA_HUB, NATIONAL | Primary - use for most joins |
| `PseudoNHSNoLinked` | DATA_HUB.CDM (HCD data) | Links to PatientPseudonym |
| `PersonKey` | DATA_HUB.DWH.DimPerson | Integer key for person dimension |

### Standard Join Patterns
```sql
-- HCD Activity to GP Diagnosis
FROM DATA_HUB.CDM."Acute__Conmon__PatientLevelDrugs" hcd
LEFT JOIN DATA_HUB.PHM."PrimaryCareClinicalCoding" pcc
  ON hcd."PseudoNHSNoLinked" = pcc."PatientPseudonym"

-- Activity to Person Demographics
FROM DATA_HUB.CDM."Acute__Conmon__PatientLevelDrugs" hcd
INNER JOIN DATA_HUB.DWH."DimPerson" dp
  ON hcd."PseudoNHSNoLinked" = dp."PatientPseudonym"
```

---

## CRITICAL: Registered Population Filter

**ALWAYS** apply when counting patients:

```sql
WHERE dp."IsCurrentNWRegistered" = 'Yes'
  AND dp."CurrentGeneralPractice" <> '*'
```

Without this filter, counts will be ~2x inflated (includes deceased, deregistered, out-of-area patients).

---

## Query Development Patterns

### Clinical Condition Detection (GP SNOMED Clusters)
```sql
-- Get all SNOMED codes for a clinical cluster
SELECT "SnomedCode"
FROM DATA_HUB.PHM."ClinicalCodingClusterSnomedCodes"
WHERE "ClusterId" = 'RARTH_COD'  -- Rheumatoid arthritis

-- Check if patient has condition
SELECT DISTINCT pcc."PatientPseudonym"
FROM DATA_HUB.PHM."PrimaryCareClinicalCoding" pcc
WHERE pcc."SNOMEDCode" IN (SELECT "SnomedCode" FROM cluster_codes)
  AND pcc."PatientPseudonym" IS NOT NULL
```

### Available SNOMED Clusters for HCD Indications
- `RARTH_COD` (155 codes) - Rheumatoid arthritis
- `PSORIASIS_COD` (116 codes) - Psoriasis
- `CROHNS_COD` (93 codes) - Crohn's disease
- `ULCCOLITIS_COD` (62 codes) - Ulcerative colitis
- `MS_COD` (44 codes) - Multiple sclerosis
- `DM_COD` / `DMTYPE1_COD` / `DMTYPE2AUDIT_COD` - Diabetes

### Sample HCD Activity Query
```sql
SELECT
    hcd."PseudoNHSNoLinked" AS PatientPseudonym,
    hcd."DrugName",
    hcd."InterventionDate",
    hcd."Provider Code",
    hcd."OrganisationName"
FROM DATA_HUB.CDM."Acute__Conmon__PatientLevelDrugs" hcd
WHERE hcd."InterventionDate" >= '2024-01-01'
LIMIT 20
```

---

## Snowflake SQL Syntax

- Double-quote identifiers: `"PatientPseudonym"`
- Date literals: `'2025-04-01'::DATE`
- Date functions: `DATEADD('MONTH', -3, date)`, `DATEDIFF('YEAR', d1, d2)`, `LAST_DAY(date)`
- Boolean: `TRUE`/`FALSE`
- No `TOP N` - use `LIMIT N`
- `COALESCE()`, `NULLIF()`, `GREATEST()` work as expected

---

## Troubleshooting

### Column not found errors
1. Use `describe_table(table_name, database)` to get actual column names
2. Remember: Snowflake identifiers are case-sensitive when quoted
3. Common mistakes: `ProductName` (wrong) vs `ProductDescription` (correct)

### Empty results
1. Check patient identifier filtering (`IS NOT NULL`)
2. Check date ranges
3. Test with `LIMIT 20` first to see sample data

### Slow queries
1. Add `LIMIT` during development
2. Use `describe_query` to validate structure before execution
3. Consider async execution for large result sets
