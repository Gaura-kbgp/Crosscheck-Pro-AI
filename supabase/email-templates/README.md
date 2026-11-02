# Supabase Auth email templates

Branded HTML templates (matching `backend/app/services/email_service.py`'s own
SMTP emails — same CrossCheckPro logo mark, colors, and layout) for Supabase's
built-in auth emails. The default Supabase template is the plain "Reset your
password" email you saw in Gmail.

## How to apply

1. Supabase Dashboard → your project → **Authentication → Emails** (also
   called "Email Templates").
2. For each template below, open the matching tab, paste the file's full
   HTML into the **Message body** box, and click **Save**.

| Supabase tab        | File                   |
| -------------------- | ---------------------- |
| Confirm signup        | `confirm-signup.html`  |
| Invite user            | `invite-user.html`     |
| Magic Link              | `magic-link.html`      |
| Change Email Address | `change-email.html`    |
| Reset Password          | `reset-password.html`  |
| Reauthentication      | `reauthentication.html`|

Subject lines (set in the same tab, above the body box) — optional, Supabase's
defaults are fine, but to match the brand:

- Confirm signup: `Confirm your email - CrossCheckPro`
- Invite user: `You've been invited to CrossCheckPro`
- Magic Link: `Your CrossCheckPro sign-in link`
- Change Email Address: `Confirm your new email - CrossCheckPro`
- Reset Password: `Reset your password - CrossCheckPro`
- Reauthentication: `Your CrossCheckPro verification code`

## Notes

- `{{ .ConfirmationURL }}`, `{{ .Email }}`, `{{ .NewEmail }}`, `{{ .Token }}`
  are Supabase's own template variables — leave them exactly as written, they
  get filled in automatically per email.
- These only affect emails Supabase itself sends (signup confirmation,
  password reset, magic link, email change, invites). CrossCheckPro's own
  custom-SMTP emails (sent by `EmailService` when Supabase isn't used) already
  use this same look and don't need changing.
- After saving, send yourself a real test (e.g. use "Forgot password" on the
  live site) to confirm it renders correctly in Gmail/Outlook.
