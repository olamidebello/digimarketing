# DigiMarketing

**Turn attention into opportunity.**

Initial working platform: isolated user workspaces, AI-assisted campaign drafts, editable copy, explicit approval, scheduling, receipts, text exports, account deletion and administrator global publishing pause. Original brand artwork is reused on the responsive site and Android app.

## Current scope

Mastodon text publishing is implemented for operator-verified accounts. Facebook, Instagram, X, LinkedIn, TikTok, YouTube, Pinterest and Threads support planning and text export only. OAuth onboarding, publishing adapters for those platforms, media uploads, analytics, billing, paid ads and automated account signup are not implemented. No account farming, verification bypass or promise of reaching everyone.

Backend: Python 3.11 standard library, SQLite, PBKDF2 passwords, one-day sessions, CSRF protection, login throttling and AI quotas. Use one service process with its embedded worker. Restart marks interrupted publishing jobs for review. Provider idempotency keys and atomic job claims reduce duplicates; uncertain delivery is never blindly retried.

## Local development

```sh
DIGI_DEV=1 python3 app.py
python3 -m unittest discover -s tests -v
node --check static/app.js
```

Open http://127.0.0.1:18840. Production sign-in cookies require HTTPS.

## Deploy through Olamidepanel

Point `digimarketing.olamidepanel.com` DNS to your server. On the server:

```sh
git clone https://github.com/olamidebello/digimarketing.git /opt/digimarketing-bootstrap
cd /opt/digimarketing-bootstrap
ansible-playbook -i localhost, -c local ansible/deploy.yml \
  -e digi_ai_env=/ABSOLUTE/PATH/TO/EXISTING/SERVER.env
```

Replace the path with your existing server environment file containing `OPENAI_API_KEY` and `OPENAI_MODEL`. It is referenced by systemd without copying or exposing the credentials. No file selected means drafting stays disabled. The current adapter requires OpenAI credentials; other AI providers are not wired.

The playbook pulls main, tests, backs up SQLite, installs a dedicated systemd service on 127.0.0.1:18840, creates a separate Nginx host, validates Nginx, requests TLS and verifies HTTPS health. It preserves existing Nginx site files to avoid overwriting Certbot modifications. Resolve conflicting host definitions before deployment. Keep the configured port stable on upgrades. Configure offsite backups and retention separately.

Create the administrator in the server terminal; public registration never grants admin:

```sh
sudo -u digimarketing env DIGI_DB=/var/lib/digimarketing/app.db \
 python3 /opt/digimarketing/repo/manage.py create-admin YOUR_EMAIL
```

The command prompts privately for a password. This initial admin dashboard shows counts, AI readiness, user ID and global publishing pause; full user provisioning and billing controls are future work.

## Connect Mastodon

As root edit `/etc/digimarketing/accounts.json`:

```json
{"USER_ID":{"Mastodon":{"instance":"https://YOUR_INSTANCE","access_token":"SERVER_ONLY_TOKEN"}}}
```

Use the numeric user ID from the state response (also shown for administrators). Verify account ownership and permission first. Configure only a trusted public HTTPS instance, with a provider-issued token permitting posting. Keep owner root, group digimarketing, mode 0640. Tokens are never browser-visible or committed. On deletion remove this mapping and revoke the token at the provider manually.

## Android build and website download

Push to main triggers GitHub Actions **Test and build DigiMarketing**. Its `DigiMarketing-Android-development` artifact contains `app-debug.apk`. The HTTPS-only WebView app uses the website and original brand icon. It is not an offline native campaign editor. The development package is `com.olamidepanel.digimarketing.dev`; the debug signing key is ephemeral, so upgrades may require uninstalling. Stable release signing and production distribution are not yet configured.

Copy the actual APK onto your server, then run:

```sh
ansible-playbook -i localhost, -c local ansible/deploy.yml \
 -e digi_ai_env=/ABSOLUTE/PATH/TO/EXISTING/SERVER.env \
 -e digi_apk_source=/ABSOLUTE/PATH/TO/app-debug.apk
```

The site shows its Android download link only after the APK is installed. `/var/lib/digimarketing/store-package/digimarketing.json` contains submission metadata. The existing African Apps Store hosted_apps schema was inspected. Add `-e digi_publish_store=true` with the APK option to back up the existing store database, insert/update only DigiMarketing metadata, and verify the live hosted-app listing. Downloads point to the DigiMarketing website; the store code and other app listings are preserved. Override `digi_store_db` if your store uses a different database path. Match metadata to the supplied APK version and development channel.

## Operational limits

Live AI and publishing require credentials; tests mock provider calls. Server SSH was unreachable from the initial development environment, so live deployment and African Apps Store publication have not been verified. Email verification, password recovery, rich media campaigns, full audit history and most social integrations remain future work. Review operator identity, support contacts and legal wording before public launch. Delete external posts at their provider. Backups and hosting logs have operator-defined retention.

## Artwork

`static/brand.png` is the master; the Android drawable is its resized derivative. Built-in image generation prompt: an original dimensional digital D combining a broadcasting megaphone and growth arrow, with violet/cyan/coral gradients on midnight navy. The website adds a DigiMarketing wordmark. No third-party platform endorsement is implied.
