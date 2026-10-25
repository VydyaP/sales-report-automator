# Case study: Sales Report Automator

*Portfolio project built on fictional data for a made-up store, "Namma Angadi Provisions", a neighbourhood provisions shop in Bengaluru.*

## The problem

A small provisions store exports its sales every month. Three months of exports came from three different setups, and none of them could go straight into a summary:

- **July** came from the billing PC: an Excel register with the store name and date range above the headers, a "Day Total" line after every day, blank spacer rows, and a few lines typed by hand (one with the date 31 June).
- **August** came as a CSV after a software change: amounts stored as text (`₹1,250.00`, `Rs. 90`), four different date styles in one column, payment written as `gpay`, `PhonePe`, `upi` or `UPI`, and the last July bills exported again because the date range overlapped.
- **September** used different column names entirely (`Inv Date`, `Particulars`, `Nos`, `MRP`, `Net Amount`), added a GST column, and ended with a Grand Total row.

Doing this by hand means about a day a month of copying, deleting and fixing formulas. A single missed "Day Total" row silently doubles that day's sales.

## What I built

A tool that takes all three files at once and produces:

1. **An Excel workbook:**
   - A summary with key numbers, findings in plain language, and two native charts
   - Breakdowns by product, day, week, month, weekday, payment method and category
   - The clean data, with the original file and row for every line
   - An **Issues** sheet listing every change
2. **A one-page PDF** for the owner to read on a phone.

It runs as a web page (upload, then download) or from the command line. A small settings file adapts it to a new client's column names and product typos without changing any code.

**Design rule: nothing changes silently.** Every removed row, recalculated value and doubtful line is logged with its file and row number. A report the owner can't check is a report the owner won't trust.

## Results on the demo data

| | |
|---|---|
| Rows read | 3,612 |
| Rows used | 3,566 |
| Rows removed | 46 (31 "Day Total" lines, 1 Grand Total, 10 overlap or duplicate lines, 3 bad or missing dates, 1 missing product) |
| Automatic corrections | 32 (missing amounts recalculated, a missing quantity recovered, product spellings and payment labels standardised) |
| Flagged for review | 3 (an amount ₹15 below qty × rate, a return, a line with no quantity) |
| Net sales | ₹5,18,322.00 across 1,840 bills (average bill ₹281.70) |

Findings the tool wrote for the owner:

- The top 3 products (rice, toor dal, atta) are 31% of sales.
- Sunday is the busiest day; Monday is the quietest.
- UPI is 57% of sales.
- September was down 13% on August.

## How the numbers were checked

Testing a tool only with its own output proves very little. So the headline numbers were recalculated **independently**: a separate script read the three raw files with plain pandas, applied the same business rules by hand (skip total rows, drop the overlap and duplicates, recover the missing amounts, exclude the impossible dates), and summed the amounts.

| Month | Independent calculation | Tool |
|---|---|---|
| July | ₹1,70,257.00 | ₹1,70,257.00 |
| August | ₹1,86,409.00 | ₹1,86,409.00 |
| September | ₹1,61,656.00 | ₹1,61,656.00 |
| **Total** | **₹5,18,322.00** | **₹5,18,322.00** |

These values are locked into the test suite, so any future change that alters them fails the tests.

A bug the tests caught while building: pandas, when told dates are day-first, reads `2026-07-05` as **7 May**. The tool uses its own date parser, with tests that ISO dates are never swapped.

## What would change for a real client

- **A settings file for their exports.** Usually 5 to 10 minutes after seeing one sample file.
- **One check of the first report together** to confirm the rules match how they work. For example, do they enter returns as negative lines?
- **Optional extras:**
  - Fill-down for registers that write the date only once per day
  - Category targets
  - Emailing the PDF automatically on the 1st of each month

## Tech

Python, pandas, openpyxl (native Excel charts and lakh-grouped ₹ formats), fpdf2 and matplotlib (PDF), PyYAML (settings), Streamlit (web page), pytest (122 tests). No paid services. Data never leaves the session.
