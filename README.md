# Seatbelt

**Vibe code like a pro developer, without being one.**

Seatbelt is a free skill for AI assistants (Claude, ChatGPT and Codex, Cursor, Lovable, Bolt,
Replit, v0) that makes the AI build your app the way a careful professional would, and explain
everything in plain English while it does.

You do not need to know what git, an API key or a database policy is. Seatbelt does.

## What it does

When you ask the AI to build, fix or launch an app, Seatbelt makes it:

1. **Talk plainly.** Every technical word gets a one-line explanation.
2. **Ask before building.** A few simple questions (who is it for, what must it do, what
   information it keeps, logins, money), then a one-page plan you approve.
3. **Build in small steps,** and tell you exactly how to check each one works.
4. **Make a save point before every change,** so you can always go back to the last version that
   worked. (It uses git quietly if it can, or a zipped backup if not.)
5. **Keep your secret keys secret.** Never in the code your visitors can see, never uploaded to
   GitHub, and with spending limits set.
6. **Lock down private data.** Database safety rules (like Supabase Row Level Security) on every
   table, so people only see their own information.
7. **Stop the fix loop.** If a fix fails twice, it stops, explains the problem, goes back to the
   last save point and tries a different way, instead of making things worse.
8. **Run a ship check before you go live,** including a no-install scanner for leaked keys and
   open databases, and tell you honestly when a real developer should take a look.

## Why this matters

Vibe coding is brilliant, but the AI does what you ask, and if you do not know to ask for
security, you often do not get it:

- WIRED reported that researchers found more than 5,000 vibe-coded web apps with virtually no
  security, close to 2,000 of which appeared to expose private data such as medical, financial and
  customer information.
  ([WIRED, May 2026](https://www.wired.com/story/thousands-of-vibe-coded-apps-expose-corporate-and-personal-data-on-the-open-web/))
- RedHunt Labs scanned about 130,000 sites built on vibe coding platforms and found that
  **1 in 5** exposed at least one sensitive secret, such as an AI or database key.
  ([RedHunt Labs](https://redhuntlabs.com/blog/echoes-of-ai-exposure-thousands-of-secrets-leaking-through-vibe-coded-sites-wave-15-project-resonance/))
- A student reported a **$55,444.78** Google Cloud bill after their Gemini API key leaked on
  GitHub. Google later waived it, but it is a lesson in setting spending limits.
  ([Reddit, r/googlecloud](https://www.reddit.com/r/googlecloud/comments/1noctxi/student_hit_with_a_5544478_google_cloud_bill/))
- The Canadian Centre for Cyber Security has published guidance on
  [managing security risks in vibe coding](https://www.cyber.gc.ca/en/guidance/managing-security-risks-vibe-coding-itsm60043).

Professional developers avoid most of this with simple habits. Seatbelt hands those habits to
your AI.

## Install (about a minute)

Pick the tool you use.

### Claude.ai (web or desktop app)

1. Download **`seatbelt.zip`** from the
   [latest release](https://github.com/HYDERMAA/seatbelt/releases/latest). Do not unzip it.
2. In Claude, go to **Settings > Capabilities** and make sure **Code execution and file
   creation** is on (newer layouts call it **Create and edit files**).
3. Go to **Customize > Skills**, click **+**, then **+ Create skill**, then **Upload a skill**,
   and choose `seatbelt.zip`.
4. Make sure Seatbelt is switched on in your skills list. That is it: Claude uses it by itself
   when you talk about building an app.

Skills work on Free, Pro, Max, Ultra, Team and Enterprise plans. On Team and Enterprise, your
organisation owner may need to allow skills first. See Anthropic's guide:
[Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude).

### Claude Code

Inside Claude Code, run:

```
/plugin marketplace add HYDERMAA/seatbelt
/plugin install seatbelt@hydermaa
```

Or copy the skill folder yourself:

```bash
git clone https://github.com/HYDERMAA/seatbelt.git
mkdir -p ~/.claude/skills
cp -r seatbelt/skills/seatbelt ~/.claude/skills/
```

### Codex (and other agents that support skills)

Copy the skill into your personal skills folder:

```bash
git clone https://github.com/HYDERMAA/seatbelt.git
mkdir -p ~/.agents/skills
cp -r seatbelt/skills/seatbelt ~/.agents/skills/
```

Restart Codex if it does not appear. You can also ask Codex's built-in `$skill-installer` to
install it from `https://github.com/HYDERMAA/seatbelt/tree/main/skills/seatbelt`, or use the
open skills installer: `npx skills add HYDERMAA/seatbelt`.

### Cursor

Copy [`.cursor/rules/seatbelt.mdc`](.cursor/rules/seatbelt.mdc) into your project's
`.cursor/rules/` folder. It applies to every chat. (Or copy [`AGENTS.md`](AGENTS.md) into your
project's main folder.)

### Lovable, Bolt, Replit, v0

Open [`paste-into-app-builders.md`](paste-into-app-builders.md), copy the box, and paste it into
your builder's always-on instructions (Lovable: **Settings > Instructions**; Bolt: **Project
settings > Knowledge**; Replit: the `replit.md` file; v0: **+ > Instructions**).

### Anything else

Most AI coding tools read an `AGENTS.md` file in your project's main folder. Copy
[`AGENTS.md`](AGENTS.md) there.

## What it looks like

> **You:** make me an app where my yoga students can book classes and pay
>
> **AI (with Seatbelt):** Happy to. A few quick questions first, so we build the right thing:
> 1. Roughly how many students, and will they each have their own login?
> 2. What must it do on day one? For example: see the timetable, book a spot, pay, get a reminder.
> 3. Will it store anything private, like phone numbers or health notes?
> 4. Are you taking payments? Stripe is the usual choice (a payment company that handles card
>    details so you never have to).
> 5. What are you building it in: Lovable, Bolt, Replit, or here?
>
> *(Then: a one-page plan to approve, small steps you can check, a save point before each change,
> card payments through Stripe Checkout, booking data locked to each student, and a ship check
> before you share the link.)*

And when something breaks:

> **AI:** That is the second fix that has not worked, so I am going to stop rather than keep
> guessing. In plain English: the page cannot read bookings because the database's safety rules
> do not yet allow it. I have gone back to your save point "before adding bookings", and this
> time I will add the safety rule first, then the page.

## The ship check scanner

The skill includes [`scripts/check_secrets.py`](skills/seatbelt/scripts/check_secrets.py), a
single Python file with no installs needed. It looks for leaked keys (OpenAI, Anthropic, Google
and Gemini, Stripe, AWS, GitHub, Supabase and more), `.env` files that could be uploaded, secrets
behind public prefixes like `NEXT_PUBLIC_` or `VITE_`, Supabase tables without Row Level Security,
and open Firebase rules. It only reads files and never changes anything.

Your AI runs it for you, but you can too:

```bash
python3 skills/seatbelt/scripts/check_secrets.py /path/to/your/project
```

It is a safety net, not a full security audit.

## FAQ

**Is it free?** Yes. MIT licence. Use it, share it, change it.

**Will it slow me down?** A little at the start (a few questions and a plan). It saves far more
time than it costs, because you spend less time stuck in broken versions.

**Do I need to know git?** No. Seatbelt uses it quietly if it is there and calls it "save
points". If not, it makes zipped backups.

**Does this make my app secure?** No tool can promise that. Seatbelt avoids the most common and
most expensive mistakes, runs a check before launch, and tells you when to get a professional
review (for example if you take payments or store sensitive data).

**Does it work with Lovable or Bolt?** Yes, through the paste-in instructions. The AI will also
give you builder-specific prompts, one change at a time.

**I am a developer. Is this for me?** Probably not. Try
[Superpowers](https://github.com/obra/superpowers) or
[Addy Osmani's agent skills](https://github.com/addyosmani/agent-skills) instead. Seatbelt is for
everyone else.

**Something is wrong or out of date.** App builders change their menus often. Please
[open an issue](https://github.com/HYDERMAA/seatbelt/issues).

## What is inside

```
skills/seatbelt/            the skill itself (this is what gets zipped for Claude.ai)
  SKILL.md                  the main instructions
  references/               extra detail the AI reads only when needed
  scripts/check_secrets.py  the ship check scanner
AGENTS.md                   drop-in rules for Codex, Cursor, Bolt and others
.cursor/rules/seatbelt.mdc  drop-in Cursor rule
paste-into-app-builders.md  short text for Lovable, Bolt, Replit, v0
.claude-plugin/             lets Claude Code install it as a plugin
tests/                      tests for the scanner
tools/                      build and check scripts for maintainers
```

Maintainers: `python3 tools/build.py` rebuilds the Cursor rule and `dist/seatbelt.zip`;
`python3 tools/check.py` validates everything; `python3 -m unittest discover -s tests` runs the
scanner tests.

## Credits

Made by Mohammed Hyder. Built on the open [Agent Skills](https://agentskills.io) format.

Licence: [MIT](LICENSE).
