# Professional Services — M365 Admin (ticket-driven)

- **Industry:** Professional Services
- **Service theme:** m365-admin
- **Source:** 12-month ticket + time-entry data
- **Tickets:** 2  |  **Work periods:** 2  |  **~Hours:** 2.1

## Representative work (anonymized)

- **2025-10-25  (1.1h)** — Ticket Summary – DKIM Configuration Issue (the firm.com) Reported By: Jennifer McCasland Date: October 24–25, 2025 Issue: DKIM status in Apollo reported as “issue detected” for the domain the firm.com . Actions Taken: Reviewed the domain’s CNAME DNS records for DKIM configuration. Verified that the two required CNAME entries (selector1 and selector2) were properly configured in DNS but pending propagation. Monitored DNS propagation progress until both records resolved successfully. Logged into t
- **2025-10-08  (1.0h)** — User mailboxes Josh.Miller@the firm.com and Jen.Mccasland@the firm.com were unable to connect to the Instantly platform due to an SMTP authentication failure. Upon investigation, it was found that SMTP client authentication was disabled for both users in Microsoft 365. Connected to Exchange Online PowerShell and ran the following command to enable SMTP authentication: Set-CASMailbox -Identity "user@domain.com" -SmtpClientAuthenticationDisabled $false. Verified the change using Get-CASMailbox and
