# Turning ideas into clear requests

Use these when the user's request is vague, or teach them the pattern so their next requests are
better. Offer to fill the template in with them by asking the questions in it.

## New feature

```
Feature: [name, e.g. "booking reminders"]
Who uses it: [e.g. customers who have booked]
What they do: [step by step, e.g. "they get an email 24 hours before"]
What they should see: [e.g. "an email with the time, address and a cancel link"]
What must not happen: [e.g. "no reminders for cancelled bookings"]
Done when: [how we will check it, e.g. "I book for tomorrow and get the email"]
Not now: [things to leave for later]
```

## Something is broken

```
What I did: [the clicks, in order]
What I expected: [...]
What happened instead: [...]
Exact error message: [copy the red text or a screenshot]
When it started: [e.g. "after we added payments", "this morning"]
What changed since it last worked: [anything, even outside the app: new key, new plan, new domain]
```

## Change one thing only

```
Change only: [the one thing].
Do not change anything else, and do not delete any features or files.
Make a save point first. When done, tell me how to check it works.
```

## Describe the whole app (first message)

```
I want to build: [one sentence]
For: [who]
Day-one features: 1. ... 2. ... 3. ...
It will store: [information]
People log in: [yes/no]
Money: [payments? paid AI?]
I am using: [Lovable / Bolt / Replit / Cursor / Claude]
Please ask me anything unclear, then show me a short plan before building.
```

## Tips to share with the user

- One request per message. Big requests make big mistakes.
- Say what "done" looks like, so you can both check it.
- Repeat the goal every so often in long sessions, so the app does not drift.
- Ask neutral questions ("What are the risks of this?") rather than "This is fine, right?",
  because AI tends to agree with you.
