# Plain-English glossary

Use these one-line explanations the first time a word comes up. Adapt them to the user's app.

| Word | Plain English |
| --- | --- |
| API | A way for one program to ask another for something, like a waiter taking orders between you and the kitchen. |
| API key / secret key / token | A password that lets your app use a service, and often spend money on your account. |
| Authentication (auth) | Checking who someone is, usually by logging in. |
| Authorisation | Checking what that person is allowed to see or do. |
| Backend / server | The part of the app that runs on a computer you control, out of sight of visitors. Safe for secrets. |
| Bug | Something in the app that does not work as intended. |
| Bucket (storage) | A folder in the cloud where uploaded files live. |
| Build | Turning the project into the version that runs live. |
| Cache | A saved copy kept to make things faster, which can show old versions. |
| CAPTCHA | A "prove you are human" check that stops bots. |
| Commit | A save point in git. |
| Console | A panel in the browser (or a window on the computer) that shows messages and errors. |
| CORS | A browser safety rule about which websites may call your server. |
| Database | Where the app stores its information, like a spreadsheet it can read and write. |
| Deploy / publish / go live | Putting the app on the internet so others can use it. |
| Domain | The web address, like myapp.com. |
| Edge function / serverless function | A small piece of backend code that runs on demand. A safe place to use secret keys. |
| `.env` file | A private file on your computer that holds secret keys. It must never be uploaded. |
| Environment variable (env var) | A setting, often a secret, given to the app from outside the code. |
| Frontend / client | The part of the app that runs in the visitor's browser. Anyone can read it. |
| Git | A tool that keeps a history of every version of a project. |
| GitHub | A website that stores git projects online. Public projects can be read by anyone. |
| `.gitignore` | A list of files git must never save, such as `.env`. |
| HTML / CSS / JavaScript | The page's content, its look, and its behaviour. |
| Input validation | Checking what people type before using it. |
| Library / package / dependency | Ready-made code someone else wrote that your app uses. |
| Localhost | Your app running only on your own computer, not on the internet yet. |
| Migration | A saved change to the database's structure. |
| `node_modules` | A big folder of downloaded packages. Never back it up or upload it; it can be re-downloaded. |
| Grant (database) | Permission for a kind of user (for example logged-in users) to reach a table at all. Policies then decide which rows. |
| Policy (database) | One rule saying who may read or change certain rows. |
| Production | The real, live version people use (as opposed to testing). |
| Rate limit | A cap on how often someone can do something, to stop abuse and runaway bills. |
| Repository (repo) | A project folder tracked by git. |
| Rollback / restore | Going back to an earlier save point. |
| Row Level Security (RLS) | Database rules that let each person see only their own rows. |
| Save point | A full snapshot of the project you can return to. |
| SDK | A toolkit for using a particular service from your code. |
| Secret key (`sb_secret_`) or `service_role` key | Supabase's master keys (the second is the older name). They ignore all safety rules, so they must never be in the browser. |
| Publishable key (`sb_publishable_`) or anon key | Supabase's public keys. Safe in the browser only because Row Level Security rules protect each table. |
| Spending limit / budget cap | A setting with a paid service that stops or warns before charges get too high. |
| SQL | The language used to talk to many databases. |
| Supabase / Firebase | Popular services that give your app a database, logins and file storage. |
| Terminal / command line | A text window where you type commands to the computer. |
| Test | A small program that checks part of your app still works. |
| Spending cap | A limit you set with a paid service so the bill cannot grow past it. Some services only send alerts and keep charging. |
| Webhook | A message another service sends your app, like "payment succeeded". |
