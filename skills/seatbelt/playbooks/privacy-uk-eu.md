# Privacy basics for the UK and EU

This is a practical starting point, not legal advice. For anything sensitive (health, children,
finance) or a business with many customers, recommend checking with the ICO's guidance or a
professional.

## Contents

1. Explain it to the user
2. Collect less
3. Privacy notice (what to include)
4. Cookies and analytics
5. Requests from users
6. Where data lives, and who processes it
7. If something leaks
8. The data protection fee (UK)
9. Sensitive data and children

## 1. Explain it to the user

> If your app keeps information about people (names, emails, bookings, photos), UK and EU data
> protection law applies (UK GDPR and the EU GDPR). The basics are simple: collect only what you
> need, tell people what you do with it, keep it safe, and let them see or delete it.

## 2. Collect less

- Ask for each field only if the app needs it. A booking needs a name and a way to contact; it
  probably does not need a date of birth.
- Decide how long to keep data (for example delete cancelled bookings after a year) and write it
  in PROJECT.md.
- Do not put personal data in logs, error messages, analytics events or AI prompts unless needed.

## 3. Privacy notice (what to include)

Offer to draft a plain-English privacy page covering:
1. Who you are and how to contact you.
2. What information you collect, and why (for example "your email, to send booking reminders").
3. The lawful basis for each use (often "to provide the service you asked for", or consent for
   marketing emails).
4. Who you share it with: the services that process it for you (for example Supabase for the
   database, Stripe for payments, your email-sending service, your host).
5. Whether data goes outside the UK or EU, and how it is protected.
6. How long you keep it.
7. People's rights: to see, correct, delete or export their data, to object, and to complain
   to the ICO (UK) or their local data protection authority (EU).
8. The date it was last updated.

Keep it honest and specific to the app; generic copied policies often describe things the app
does not do.

## 4. Cookies and analytics

- Cookies needed for the app to work (like staying logged in) do not need a consent banner.
- Non-essential cookies and similar tracking (most analytics, advertising pixels) need consent
  first under UK and EU rules. Either ask for consent before loading them, or choose a
  privacy-friendly analytics tool configured not to need consent, and check its documentation
  for UK and EU use.

## 5. Requests from users

Make it easy: a contact email in the privacy notice, and a way to delete an account. When
someone asks to see or delete their data, respond without undue delay, usually within one month.
Build an "export my data" and "delete my account" option if the app will have many users.

## 6. Where data lives, and who processes it

- Choose a UK or EU region for the database when creating the project if most users are there
  (Supabase and most hosts let you pick a region at creation).
- The services you use are your processors; check each has a data processing agreement (most
  publish one in their legal pages).

## 7. If something leaks

If personal data is exposed (for example an open table was found), fix the hole first, then work
out what was exposed and for how long. Under UK GDPR, a personal data breach that is likely to
risk people's rights must be reported to the ICO within 72 hours of becoming aware of it, and
people must be told if the risk to them is high. Recommend checking the ICO's breach guidance
straight away.

## 8. The data protection fee (UK)

Most UK organisations and sole traders that handle personal data must pay a yearly data
protection fee to the ICO unless they are exempt. Point the user to the ICO's self-assessment on
its website to check.

## 9. Sensitive data and children

Health, finance, children's data and similar "special category" data raise the bar a lot. Apps
likely to be used by children in the UK should follow the ICO's Children's code (Age appropriate
design code). For these apps, recommend professional advice and a developer security review
before launch.
