# Demo transcript

- valid_micro_payment -> `{"decision":"ACCEPT","reason":"PAYMENT_WITHIN_SCOPE_AND_BUDGET"}`
- over_budget -> `{"decision":"BLOCK","reason":"OVER_BUDGET"}`
- missing_intent -> `{"decision":"BLOCK","reason":"MISSING_PAYMENT_INTENT"}`
- recipient_changed -> `{"decision":"BLOCK","reason":"RECIPIENT_MISMATCH"}`
- recurring_without_approval -> `{"decision":"HOLD","reason":"RECURRING_PAYMENT_REQUIRES_APPROVAL"}`
