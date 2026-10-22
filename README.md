# DigiMarketing

**Turn attention into opportunity.**

Initial working platform: isolated user workspaces, AI-assisted campaign drafts, editable copy, explicit approval, scheduling, receipts, text exports, account deletion and administrator global publishing pause. Original brand artwork is reused on the responsive site and Android app.

## Current scope

Mastodon text publishing is implemented for operator-verified accounts. Facebook, Instagram, X, LinkedIn, TikTok, YouTube, Pinterest and Threads support planning and text export only. OAuth onboarding, publishing adapters for those platforms, media uploads, analytics, billing, paid ads and automated account signup are not implemented. No account farming, verification bypass or promise of reaching everyone.

Backend: Python 3.11 with cryptography, SQLite, PBKDF2 passwords, one-day sessions, CSRF protection, login throttling and AI quotas. Development uses one service process with an embedded worker; production deployment uses the separate Ansible batch timer described below. Restart marks interrupted publishing jobs for review. Provider idempotency keys and atomic job claims reduce duplicates; uncertain delivery is never blindly retried.

## Local development

```sh
pip install -r requirements.txt
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

A successfully built development APK is included at `downloads/DigiMarketing.apk` with its SHA-256 sidecar. The deployment installs this build by default, enabling the website download link. To register it in the existing African Apps Store during deployment add `-e digi_publish_store=true`. `/var/lib/digimarketing/store-package/digimarketing.json` contains submission metadata. The existing African Apps Store hosted_apps schema was inspected. Add `-e digi_publish_store=true` with the APK option to back up the existing store database, insert/update only DigiMarketing metadata, and verify the live hosted-app listing. Downloads point to the DigiMarketing website; the store code and other app listings are preserved. Override `digi_store_db` if your store uses a different database path. Match metadata to the supplied APK version and development channel.

## Operational limits

Live AI and publishing require credentials; tests mock provider calls. Server SSH was unreachable from the initial development environment, so live deployment and African Apps Store publication have not been verified. Email verification, password recovery, rich media campaigns, full audit history and most social integrations remain future work. Review operator identity, support contacts and legal wording before public launch. Delete external posts at their provider. Backups and hosting logs have operator-defined retention.

## Artwork

`static/brand.png` is the master; the Android drawable is its resized derivative. Built-in image generation prompt: an original dimensional digital D combining a broadcasting megaphone and growth arrow, with violet/cyan/coral gradients on midnight navy. The website adds a DigiMarketing wordmark. No third-party platform endorsement is implied.

## Ansible campaign automation and batches

Deployment now disables the web process's embedded publisher and installs `digimarketing-batch.timer`. Every minute it starts a restricted service running `ansible/run-campaign-batch.yml` as the DigiMarketing service user. Ansible invokes `automation.py`; campaign text stays in SQLite and is never treated as shell commands or playbook instructions. AI drafting stays in the campaign studio: these jobs publish already reviewed content, they do not generate new copy and send it without approval.

Select up to 100 campaigns in the campaign library and approve a start time. The API atomically checks ownership and connected channels before scheduling the whole selection, spaced by 60 seconds. Unsupported channels block the selection without partially scheduling it.

Defaults: **10 campaigns per run, 12 attempts per account/channel per hour, 100 per day, at least 60 seconds between posts**. Administrators can adjust these in the dashboard and pause all delivery. Provider limits remain authoritative; local limits do not override platform rules. Counts include failed attempts. The admin dashboard shows the latest 20 batch runs; full history stays in `batch_runs`, delivery attempts in `attempts` and receipts in `deliveries`.

A shared OS lock prevents overlapping workers from sending concurrently, while SQLite records claims and attempts. HTTP 429 responses honor `Retry-After` and receive at most three total attempts. Other failures, network uncertainty and interrupted deliveries require review rather than blind retries. Changing copy still requires manual approval before rescheduling. The batch runner has a 120-second work budget checked between campaigns, plus a five-minute service timeout. A run processes fewer jobs when an account is cooling down or a provider is unavailable.

Preview a batch without publishing (run on the server as the service user):

```sh
sudo -u digimarketing env HOME=/var/lib/digimarketing \
 ansible-playbook -i localhost, -c local \
 /opt/digimarketing/repo/ansible/run-campaign-batch.yml -e digi_dry_run=true
```

Run the installed service once: `systemctl start digimarketing-batch.service`. Inspect `journalctl -u digimarketing-batch.service` and `systemctl status digimarketing-batch.timer`. The service runs with protected account-file access. It needs no AI key for posting reviewed campaigns. Disable the timer with `systemctl disable --now digimarketing-batch.timer` if switching back to the embedded worker. Application code takes a lock in either mode.

These are controlled batches to authorized accounts. Automated account creation, mass unsolicited messages, posting to all platform users and bypassing provider verification are not included. Direct publishing remains Mastodon-only until other provider integrations are implemented and authorized.


## Terms, privacy and copyright

Public pages `/terms`, `/privacy` and `/copyright` are linked from the website and Android web workspace. Version `2026-10-22.1` covers campaign approval, batch scheduling, provider limits, AI review, advertising responsibilities, rights in content, cookies, provider sharing, acceptance records and automation logs. Registration requires explicit acceptance of the current Terms and acknowledgement of the Privacy Notice. SQLite stores version IDs and acceptance time; no extra IP address is collected for this record. Existing users are not retroactively marked as accepting new terms. Account deletion removes the active acceptance record along with that user's attempt and AI-usage data.

Reference material consulted: [FTC advertising guidance](https://www.ftc.gov/business-guidance/advertising-marketing), [FTC personal-information protection guidance](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business-0), and [U.S. Copyright Office permission FAQ](https://www.copyright.gov/help/faq/faq-fairuse.html). These pages describe implemented behavior; they do not certify regulatory compliance. Configure and verify the operator's support contact and backup retention before public launch.


## Pull the latest GitHub source and deploy in one command

On the hosting server as root, install Ansible if needed, then use:

```sh
apt-get update && apt-get install -y git ansible-core
ansible-pull -U https://github.com/olamidebello/digimarketing.git \
 -C main -d /opt/digimarketing-bootstrap -i localhost, -c local \
 ansible/pull-and-deploy.yml
```

This fetches GitHub main before loading the deployment playbook. Deployment then pulls the application checkout, tests it, backs up the database, installs/restarts the service, enables campaign automation, installs the bundled APK, configures the domain gateway and verifies HTTPS.

On first deployment, append `-e digi_ai_env=/absolute/path/to/the/existing/server.env` to reference your existing AI settings. Subsequent deployments restore the selected path, domain, root, port and TLS email from `/etc/digimarketing/deployment.yml`; explicit `-e` overrides take precedence. This file contains deployment choices, never API key values. Without a selected existing AI file, the application deploys with AI drafting disabled.

After checkout, `bash /opt/digimarketing-bootstrap/scripts/deploy-server.sh` performs the same pull and deployment with a lock against concurrent invocations of that script. Extra Ansible arguments can be appended, such as `-e digi_publish_store=true` to install the app listing in the existing African Apps Store database. Other invocation methods should not be run concurrently. Existing local source edits are preserved: a conflicting checkout stops rather than discarding them.

DNS for `digimarketing.olamidepanel.com` must resolve to this server before certificate issuance. A failed certificate request stops deployment and reports the error; HTTP readiness alone is not a verified HTTPS deployment. Creating the first administrator remains the explicit server-terminal command documented above.

## Repair wrong-site routing

If the DigiMarketing address displays another application, rerun the pull-and-deploy command with the latest source. Deployment stops only `digimarketing.service`, tests its configured port, and selects a free port from 19040–19140 if that port is already occupied. It does not stop the application owning an occupied port. The chosen port is saved for later deployments.

Readiness now requires the explicit `service: digimarketing` marker and a PID matching the DigiMarketing systemd service. The domain configuration is backed up and regenerated using the selected port, preserving its existing domain certificate. Public verification checks both the app identity and homepage branding; a generic HTTP 200 no longer passes.

The route check stops rather than overwriting a site file shared with another hostname, or ignoring another active declaration of the DigiMarketing hostname. Such errors identify the configuration filenames requiring review. The repair cannot verify DNS or inspect server state until run on the server.


### Recover from an invalid saved AI environment path

The AI file preflight now runs before stopping the service or saving deployment choices. If a previous deployment saved a nonexistent placeholder path, override it explicitly during the next pull:

```sh
ansible-pull -U https://github.com/olamidebello/digimarketing.git \
 -C main -d /opt/digimarketing-bootstrap -i localhost, -c local \
 ansible/pull-and-deploy.yml -e '{"digi_ai_env":""}'
```

This restores deployment with AI drafting disabled and saves the empty selection. It does not delete any existing AI key or server environment file. Re-enable drafting later using the verified existing file path. Never create an empty placeholder environment file just to pass the existence check.


## Super admin API and key management

After deployment, sign in as an administrator and open **API & keys**. This screen supports:

- AI drafting enable/disable, editable OpenAI model ID and drafts-per-user hourly limit.
- Add or replace a stored OpenAI key, remove it, or switch back to the existing server environment key. Blank key input with Keep preserves the current key. Remove disconnects rather than silently falling back to an environment key.
- Test the saved OpenAI connection, with an explicit small-usage notice and one-minute test cooldown.
- Assign, replace, disable or remove an authorized Mastodon token for a specific existing user; optionally return that user to the root-managed account file. Changing the instance requires replacing its token.
- Redacted provider status, key-source labels, an SHA-256 fingerprint for the AI key and a recent integration audit log. Plaintext keys and tokens are never returned by these APIs.

Every settings change and connection test requires the administrator's current password plus a valid session and CSRF token. Five failed password confirmations trigger a five-minute cooldown. Admin changes, tests and failed confirmations are logged without submitted credentials. Provider secrets entered in the GUI are Fernet-encrypted in SQLite. Production deployment generates `/etc/digimarketing/master.key` once, restricts it to root and the service group, and preserves it on upgrades. Back this key up separately and securely: losing it makes stored provider secrets unreadable. Encryption does not protect against a fully compromised running server.

Existing server environment files and root-managed social account files remain read-only to this GUI. Removing a GUI key does not revoke the credential with its provider or erase old encrypted backups. Revoke compromised keys in the provider console. GUI-managed social tokens are removed on local account deletion; root-managed account-file entries still require operator removal. The integration audit retains numeric actor/target IDs without email or campaign text. API-key creation at a provider, automated OAuth onboarding, other social publishing adapters, and creation of public DigiMarketing API client keys are not included.

No service restart is required for GUI changes. No existing provider key was changed during implementation. Before deployment, the encrypted-store features are not available on the running site.


## Marketplace and payment gateways

The marketplace ships with eight proposed one-time USD prices, editable by the administrator: Caption Template Kit $9, Content Calendar Kit $12, AI Copy Review Pack $19, Video Script Pack $25, Brand Creative Brief $29, Landing Page Audit $39, Campaign Launch Plan $49, and 30-Day Growth Campaign Plan $149. These are product defaults, not market-price benchmarks. Template kits deliver stored text after verified payment. Managed services require the operator to perform the listed work; they are not automatically fulfilled by AI or Ansible.

Open Administration → Marketplace management to add or edit products, hide listings, manage Stripe/PayPal credentials and update paid service fulfillment. Prices use integer cents; customer requests cannot override them. Orders retain the purchased price, title and digital-content snapshot after product edits. Gateway credentials are encrypted, require admin password confirmation and are never returned by the settings API. Both gateways default to disabled test mode. Sandbox checkout is restricted to administrators.

### Stripe

Configure a test or live secret key plus the corresponding webhook signing secret. Register `https://digimarketing.olamidepanel.com/api/payments/webhooks/stripe` for `checkout.session.completed` and `checkout.session.async_payment_succeeded`. Verify the exact signing secret in the matching Stripe account and mode. Signatures use the raw request body and a five-minute timestamp tolerance. Event IDs are deduplicated. The application also retrieves the Checkout Session from Stripe and checks its ID, order reference, amount, currency, live/test mode and paid status before marking the order paid. Customers can use Verify payment to reconcile a pending order without relying on the browser redirect.

### PayPal

Configure the sandbox or live client ID and secret. Checkout creates an Orders v2 order and redirects to PayPal approval. On return the customer must choose Confirm / complete payment in My orders. The server retrieves the order, captures an approved payment with an idempotency key, and checks the completed capture amount, currency and order references. If a capture response is lost, verification can retrieve the completed order rather than blindly creating another payment. Background PayPal webhook capture/reconciliation is not implemented; users must return or revisit My orders. The Android wrapper opens hosted checkout in the browser; sign in there if its session differs from the app.

Disable a gateway to stop new checkouts while preserving its credentials for pending-order verification. Replacing or removing credentials, switching modes or merchant accounts can interrupt pending-order reconciliation; settle or review outstanding orders first. Provider-side key revocation, automatic refunds, chargeback/refund synchronization, recurring billing, tax automation, seller payouts and third-party seller onboarding are not implemented. Refund review is a service status, not a movement of funds. Process refunds in the merchant provider dashboard and reconcile their effects operationally. Do not enable live checkout until merchant credentials, domain routing, product delivery and applicable pricing/tax treatment are ready.

No live payment or merchant setup was performed during development. Automated tests use mocked provider replies. Review the official APIs when configuring merchant accounts: [Stripe Checkout](https://docs.stripe.com/api/checkout/sessions/create), [Stripe webhook verification](https://docs.stripe.com/events/manage-webhook-endpoints), and [PayPal Orders v2](https://developer.paypal.com/api/orders/v2).

## Facebook Page publishing and super admin controls

API & keys now includes Facebook Page settings for each workspace owner: encrypted token add/replace/remove, enable/disable, Graph version, Page ID, identity verification and audit events. Admin password confirmation and CSRF protection are required. Save a new connection disabled, verify it, then enable publishing. Changing the token, Page ID or version resets verification. Tokens are never returned to the browser or written to audit logs. Use the numeric Graph Page ID from Meta (not the public profile URL ID).

The Meta app ID is 1409571857518808. Its published status does not grant posting permission automatically. Obtain a Page access token with pages_manage_posts and pages_read_engagement for the intended Page; the earlier read-only connection is insufficient for writes. Enter it directly in the protected admin form, never in GitHub or chat. Identity verification performs a read-only /me request and does not prove write permission. Test one reviewed campaign before enabling routine schedules. No live Facebook post was sent during development.

Facebook text campaigns use the versioned /PAGE_ID/feed API. Global pause, account pacing, batch limits, campaign approval and delivery receipts also apply. Failures require review instead of automatic replay, because a lost response may hide a successful post. Disabling a connection cannot recall an in-flight post. Removal deletes the local encrypted token; revoke provider access separately in Meta Business Integrations. This implementation does not include OAuth onboarding, automatic token renewal, media uploads, ads, analytics or Page post deletion. See https://developers.facebook.com/documentation/pages-api/posts.

Deploy using the existing ansible/pull-and-deploy.yml playbook. Then sign in as super admin and open API & keys → Facebook Pages. No database migration or secret in Ansible is required.
