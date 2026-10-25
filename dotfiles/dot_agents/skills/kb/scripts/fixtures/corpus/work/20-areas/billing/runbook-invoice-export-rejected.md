---
title: "Runbook: invoice export rejected"
created: 2025-12-03
type: runbook
tags: [billing, runbook, edi]
---
# Runbook: invoice export rejected

Error in billing-gateway: `EDI 810 rejected: segment N1 missing for bill-to party`.

Meaning: a customer's EDI partner refused an invoice. Nothing is billed until it is sent again.

## Check
1. Which customer? The rejection carries the interchange control number.
2. Did the customer's bill-to address change this week? Most rejections follow an address change in the customer master.

## Act
- Fix the customer master, then resend from the billing console ("Resend 810").
- More than 20 rejections in an hour: pause the export job and page the billing lead.
- Never edit the EDI file by hand; resend from source so the audit trail stays intact.
