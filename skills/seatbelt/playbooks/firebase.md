# Firebase playbook

## Contents

1. Explain it to the user
2. Firestore rules patterns
3. Storage rules
4. Keys and App Check
5. Mistakes to watch for

## 1. Explain it to the user

> Your app's Firebase settings, including an "apiKey", are visible in the website. That is
> normal for Firebase, but it means the **security rules** are the only thing deciding who can
> read or change data. "Test mode" rules let anyone in, and they stop working after a while.

The Firebase Admin SDK's **service account** file (a JSON file with a private key) is a real
secret: server only, never in the website or GitHub.

## 2. Firestore rules patterns

Private documents per user (`users/{userId}` and everything under it):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

Public to read, nobody can write from the app (change in the console or from server code):

```
match /services/{id} {
  allow read: if true;
  allow write: if false;
}
```

Users create their own bookings but cannot mark them paid:

```
match /bookings/{id} {
  allow read: if request.auth != null && resource.data.userId == request.auth.uid;
  allow create: if request.auth != null
    && request.resource.data.userId == request.auth.uid
    && request.resource.data.status == 'pending';
  allow update, delete: if false; // only server code (Admin SDK) changes bookings
}
```

Never store a plan, credits or role in a document the user can write. Keep them in a document
only server code writes (for example `entitlements/{uid}` with `allow write: if false`).

Test rules in the console's **Rules Playground** or the Firebase emulator before publishing.

## 3. Storage rules

```
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    match /users/{userId}/{fileName} {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if request.auth != null && request.auth.uid == userId
        && request.resource.size < 5 * 1024 * 1024
        && request.resource.contentType.matches('image/.*');
    }
  }
}
```

Reading and writing are separate rules because the size and type checks only make sense for
uploads.

## 4. Keys and App Check

- In Google Cloud console, **APIs & Services > Credentials**, restrict the Firebase web API key to
  your website addresses and to the Firebase APIs you use. Do not reuse that key for Gemini or
  other paid APIs.
- Turn on **App Check** to make it harder for scripts outside your app to use your backend.
- Set a **budget and alerts** in Google Cloud Billing (alerts only; they do not stop spending).

## 5. Mistakes to watch for

- `allow read, write: if true;` or test-mode rules left in place.
- Rules that check `request.auth != null` but not **whose** data it is.
- Service account JSON committed to GitHub or bundled in the website.
- Admin or paid flags writable by the user.
