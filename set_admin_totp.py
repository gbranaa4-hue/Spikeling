"""One-time TOTP setup for the voice/Discord bot's admin gate.

Replaces the old fixed-passphrase unlock (which leaked into Discord chat
history because a reusable secret sent over a chat channel is inherently
exposed). With TOTP, you unlock by sending the CURRENT 6-digit code from
your authenticator app -- even if that code lingers in chat history
forever, it's dead in ~30 seconds and single-use, so there's nothing worth
stealing.

Run once:

    python set_admin_totp.py

It generates a TOTP secret, stores it in the VOICE_ADMIN_TOTP_SECRET user
environment variable (via setx), writes a scannable QR image, and prints
the manual-entry key. Add it to Google Authenticator / Authy / etc., then
tell Claude to restart the bot. From then on: !unlock <6-digit code>.

SECURITY: the TOTP *secret* (the seed) is the one sensitive value here --
anyone who has it can generate valid codes. It's stored locally in your
registry (never sent anywhere) and shown here only so you can add it to
your phone. Delete the QR image after scanning, and don't share the key.
"""
import os
import sys
import subprocess

try:
    import pyotp
    import qrcode
except ImportError as e:
    print(f"Missing dependency: {e}. Run:  python -m pip install pyotp \"qrcode[pil]\"")
    sys.exit(1)

secret = pyotp.random_base32()
uri = pyotp.TOTP(secret).provisioning_uri(name="admin", issuer_name="SPIKE voice bot")

# Store the secret in the user registry env (setx). The bot reads it fresh
# on its next restart. Unlike the old passphrase HASH, a TOTP secret must be
# stored reversibly -- the bot needs it to compute the expected codes.
subprocess.run(["setx", "VOICE_ADMIN_TOTP_SECRET", secret], check=True, stdout=subprocess.DEVNULL)
check = subprocess.run(
    ["reg", "query", "HKCU\\Environment", "/v", "VOICE_ADMIN_TOTP_SECRET"],
    capture_output=True, text=True)
stored_ok = secret in check.stdout

qr_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin_totp_qr.png")
qrcode.make(uri).save(qr_path)

print()
if stored_ok:
    print("SUCCESS: TOTP secret generated, stored, and verified in the registry.")
else:
    print("WARNING: the secret didn't verify in the registry -- tell Claude it failed.")
print()
print("Add it to your authenticator app one of two ways:")
print(f"  * SCAN the QR image:  {qr_path}")
print(f"  * or type this key manually:  {secret}")
print()
print(f"Right now your app should show:  {pyotp.TOTP(secret).now()}")
print("(that changes every 30s -- confirm your app shows the same number)")
print()
print("Then tell Claude 'done' to restart the bot, and unlock in Discord with:")
print("    !unlock <the current 6-digit code>")
print()
print("IMPORTANT: delete the QR image after you've scanned it:")
print(f"    del \"{qr_path}\"")
