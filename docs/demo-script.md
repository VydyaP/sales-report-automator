# Demo script (about 75 seconds)

**Setup before recording:**
- Open the web page (`streamlit run app.py`, or the live link).
- Keep `sample_data/jul_2026_sales_register.xlsx` open in Excel in another window.
- Have the downloaded PDF ready on your phone, if you'll show WhatsApp.

---

**[0:00 to 0:12] The problem. Show the July Excel file and scroll slowly.**

> "This is what a shop's monthly sales export usually looks like. The store name is sitting above the headers, there's a 'Day Total' line after every day, and some rows are typed by hand, like this one dated 31st June. August came from different software, so the amounts are text and the dates are in four formats. Turning this into a summary usually takes someone most of a day."

**[0:12 to 0:22] Upload. Switch to the web page and click "Try the demo store's messy sample data".**

> "I give the tool all three months at once, in three different layouts. That's it."

**[0:22 to 0:40] The results. Point at the numbers, then the findings.**

> "In a few seconds it has read 3,612 rows and tells me net sales were 5.18 lakh across 1,840 bills, with an average bill of 282 rupees. And it explains things in plain language: the top three products bring in 31% of sales, Sunday is the busiest day, and 57% of payments are UPI."

**[0:40 to 0:58] Trust. Scroll to Data quality and the Issues table.**

> "Most importantly, nothing changes silently. It removed 31 'Day Total' lines that would have double-counted sales, a set of bills that appeared in both the July and August exports, and the impossible dates. Each one is listed here with the file and row number. Where it wasn't sure, like an amount that doesn't match quantity times rate, it kept the value and flagged it for a person to check."

**[0:58 to 1:15] The deliverables. Click both download buttons, open the Excel Summary sheet, then the PDF.**

> "The owner gets a formatted Excel report with charts and a breakdown by product, day and payment method, plus a one-page PDF they can forward on WhatsApp. For a new shop, I just add their column names to a small settings file. No code changes, and it runs every month in seconds."

---

**Optional closing line for a client pitch:**

> "If you send me one month of your sales export, I'll show you your own report before you pay anything."
