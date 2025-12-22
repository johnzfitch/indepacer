 | Feature                 | Spec                               | Implemented |
  |-------------------------|------------------------------------|-------------|
  | Cases Command           |                                    |             |
  | -n, --case-number       | Full case number                   | ✅          |
  | -t, --title             | Case title                         | ✅          |
  | -c, --court             | Court ID (repeatable)              | ✅          |
  | -j, --jurisdiction      | ap/bk/cr/cv/mdl                    | ✅          |
  | --filed-after/before    | Date range                         | ✅          |
  | --closed-after/before   | Date closed range                  | ✅          |
  | --nature-of-suit, --nos | NOS code                           | ✅          |
  | --chapter               | Bankruptcy chapter                 | ✅          |
  | --case-type             | Case type code                     | ✅ (bonus)  |
  | --page                  | Pagination                         | ✅          |
  | --all-pages             | Fetch all                          | ✅          |
  | --json                  | JSON output                        | ✅          |
  | --csv                   | CSV output                         | ✅          |
  | -o, --output            | File output                        | ✅          |
  | --dry-run               | Preview without cost               | ✅ (bonus)  |
  | Parties Command         |                                    |             |
  | -l, --last-name         | Last name/company                  | ✅          |
  | -f, --first-name        | First name                         | ✅          |
  | --middle-name           | Middle name                        | ✅          |
  | --exact-match           | Exact matching                     | ✅          |
  | --ssn                   | SSN (bankruptcy)                   | ✅          |
  | --role                  | Party role                         | ✅          |
  | Case filters            | All case filters                   | ✅          |
  | Output Formatting       |                                    |             |
  | Rich table (default)    | Court, Case#, Title, Filed, Status | ✅          |
  | JSON pretty-print       | --json                             | ✅          |
  | CSV with headers        | --csv                              | ✅          |
  | File output             | -o FILE                            | ✅          |
  | Error Handling          |                                    |             |
  | 401 re-auth retry       | Auto retry                         | ✅          |
  | 406 validation error    | Show API error                     | ✅          |
  | Network errors          | Clear message                      | ✅          |
  | No results              | Friendly message                   | ✅          |
  | Batch Commands          |                                    |             |
  | batch list              | List jobs                          | ✅ (bonus)  |
  | batch status            | Check status                       | ✅ (bonus)  |
  | batch download          | Get results                        | ✅ (bonus)  |
  | batch delete            | Remove job                         | ✅ (bonus)  |

  tep 2: Create models.py

     Define Pydantic models for type-safe API responses:
     - CaseResult - Individual case from search
     - PartyResult - Individual party from search
     - PageInfo - Pagination metadata
     - Receipt - Billing info
     - SearchResponse - Top-level response wrapper
     - CaseSearchCriteria - Input validation for case searches
     - PartySearchCriteria - Input validation for party searches

     Step 3: Create pcl.py

     PCL API client class with methods:
     - search_cases(criteria, page=0) - Immediate case search
     - search_parties(criteria, page=0) - Immediate party search
     - _make_request(endpoint, payload) - Shared request logic with token handling

     Key features:
     - Token caching and refresh from response headers
     - Proper error handling (401 = auth expired, 406 = invalid params)
     - Rate limiting awareness

     Step 4: Add CLI Commands

     New command group pacer pcl with subcommands:

     # Case searches
     pacer pcl cases --case-number "1:2020cv12345"
     pacer pcl cases --title "Smith v. Jones"
     pacer pcl cases --court nysdce --filed-after 2020-01-01
     pacer pcl cases --jurisdiction civil --nature-of-suit 440

     # Party searches
     pacer pcl parties --last-name "Smith" --first-name "John"
     pacer pcl parties --last-name "Acme Corp"
     pacer pcl parties --ssn 123456789  # Bankruptcy only

     # Common options
     --page N           # Page number (0-indexed)
     --all-pages        # Fetch all pages (with confirmation for large results)
     --json             # Output as JSON
     --csv              # Output as CSV
     --output FILE      # Save to file

     CLI Design

     pacer pcl cases [OPTIONS]
       --case-number, -n    Full case number (e.g., 1:2020cv12345)
       --title, -t          Case title (starts-with match)
       --court, -c          Court ID or region (can repeat)
       --jurisdiction, -j   ap|bk|cr|cv|mdl
       --filed-after        Date filed from (YYYY-MM-DD)
       --filed-before       Date filed to (YYYY-MM-DD)
       --closed-after       Date closed from
       --closed-before      Date closed to
       --nature-of-suit     NOS code (can repeat)
       --chapter            Bankruptcy chapter (can repeat)
       --page               Page number (default: 0)
       --all-pages          Fetch all pages
       --json               JSON output
       --output, -o         Output file

     pacer pcl parties [OPTIONS]
       --last-name, -l      Last name or company (required unless SSN)
       --first-name, -f     First name
       --middle-name        Middle name
       --exact-match        Require exact name match
       --ssn                SSN (bankruptcy debtors only)
       --role               Party role code (can repeat)
       (plus all case filter options above via --case-*)
       --page               Page number
       --all-pages          Fetch all pages
       --json               JSON output
       --output, -o         Output file

     Output Formatting

     Default: Rich table with key fields
     - Cases: Court, Case#, Title, Filed, Closed, Link
     - Parties: Name, Role, Court, Case#, Title, Filed

     With --json: Pretty-printed JSON
     With --csv: CSV with headers
     With -o FILE: Write to file instead of stdout

     Error Handling

     - 401: Re-authenticate and retry once
     - 406: Show validation error from API
     - Network errors: Clear message with retry suggestion
     - No results: Friendly message, suggest broader search

     Example Usage

     # Search for cases with "Apple" in title filed in 2023
     pacer pcl cases -t "Apple" --filed-after 2023-01-01 --filed-before 2023-12-31

     # Search for bankruptcy cases in Texas
     pacer pcl cases -c TX --jurisdiction bk --chapter 11

     # Find party "Elon Musk" in civil cases
     pacer pcl parties -l Musk -f Elon -j cv

     # Export all patent cases in SDNY to CSV
     pacer pcl cases -c nysdce --nature-of-suit 830 --all-pages --csv -o patent_cases.csv
