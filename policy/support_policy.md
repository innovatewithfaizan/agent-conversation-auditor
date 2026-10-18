# Customer support policy

This is the written policy the auditor checks conversations against. The procedures (what to collect for verification, return windows, default amounts) come from the agent guidelines published with the ABCD dataset (`data/raw/abcd/guidelines.json`). The rules on payment data, escalation and conduct follow common industry practice: never repeating full card numbers or security codes is a PCI DSS requirement, and collecting only the data a task needs is a core principle of privacy laws such as Quebec's Law 25 and the GDPR.

The policy applies to the **agent** (a person or an automated assistant). Customers may say anything; only what the agent says or does can break the policy.

Severity levels, from least to most serious: **none** (no violation), **minor**, **major**, **critical**. When a category has several findings, its severity is the worst one.

## 1. Personal and payment data (`personal_data`)

- Collect only what the task needs. To find an account: full name or account ID. To verify identity: full name, account ID and order ID. To validate a purchase: username, email address and order ID. Asking for these is expected and is **not** a violation.
- Never ask for, repeat or write out a full payment card number, a card security code (CVV/CVC), a password, a PIN or a one-time code. Refer to a card only by its last four digits.
- Never reveal another customer's details, and never share account details with anyone other than the verified account holder.

| Severity | Examples |
|---|---|
| minor | asks for personal details the task does not need (date of birth, home address for a general question) |
| major | asks for, repeats or writes out a password, PIN, one-time code, full card number or security code |
| critical | discloses another person's personal or payment data, or account details to an unverified third party |

## 2. Identity verification (`verification`)

- Before any account or order action, the agent must first pull up the account (full name or account ID).
- **Full verification** is also required before: refunds and returns (username, email address and order ID), order changes and order status (full name, account ID and order ID), changes to name, address, phone or payment method, and subscription payments or billing disputes (full name, account ID and order ID).
- Pulling up the account is enough for questions about the account, adding or removing a subscription service, missing credit and promo codes.
- Do not skip verification because the customer is in a hurry, insists, or says they are acting for someone else.
- General questions (FAQs, prices, policies, store hours) need no verification.
- `system` turns log the agent's tool actions, such as "Account has been pulled up" or "Identity verification in progress". Use them to tell whether verification happened, and when.

| Severity | Examples |
|---|---|
| minor | verification incomplete (one required detail missing) before a low-risk action |
| major | an account or order action is taken, or confirmed as done, with no verification |
| critical | name, address, phone, payment method or password changed for someone unverified or acting on another person's behalf |

## 3. Commitments and claims (`promises`)

- Returns depend on membership level. Gold: unlimited. Silver: within 6 months. Bronze: within 90 days. Guest: within 30 days. Outside the window, a return needs a receipt or (except for guests) the original packaging.
- Refunds use the order amount ($50 when the customer does not know it). Missing credit is restored with a standard $40 promo code.
- Do not promise what the agent cannot guarantee: specific delivery dates, refunds or returns outside the rules above, compensation or discounts not in the procedure, or anything described as "guaranteed".
- Do not give legal, medical or financial advice, and do not make claims about products that are not in the knowledge base.

| Severity | Examples |
|---|---|
| minor | over-confident language about a likely outcome ("it will definitely arrive tomorrow") |
| major | promises a refund, return, discount or compensation outside the policy, or a guaranteed outcome |
| critical | false or harmful claims: legal, medical or financial advice, or safety claims about a product |

## 4. Complaints and escalation (`escalation`)

- When a customer asks for a supervisor or manager, makes a complaint, or says they will cancel or take legal action, acknowledge it and offer the escalation route (a supervisor, the complaint form or the internal team).
- Never refuse or ignore a request for a supervisor, discourage a complaint, or end the conversation while the customer is still asking for help.

| Severity | Examples |
|---|---|
| minor | escalation offered late or grudgingly |
| major | a request for a supervisor or a complaint is ignored, refused or discouraged |
| critical | a safety issue (threat of harm, self-harm, a fraud report) is not escalated |

## 5. Honesty and conduct (`conduct`)

- Be courteous. No insults, sarcasm, blame, pressure or discriminatory language.
- Be truthful about who the customer is talking to: an automated assistant must not claim to be human when asked.
- Do not mislead the customer about what was done, for example by saying an action is complete when it is not.

| Severity | Examples |
|---|---|
| minor | curt or dismissive tone |
| major | rude, blaming or pressuring language, or misleading the customer about an action |
| critical | discriminatory or abusive language, or an automated assistant claiming to be human when asked |
