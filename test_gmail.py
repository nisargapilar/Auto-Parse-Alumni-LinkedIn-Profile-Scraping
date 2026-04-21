import smtplib
import os

# Test with hardcoded values first
EMAIL_ADDRESS = "siyask096@gmail.com"  # ← PUT YOUR ACTUAL GMAIL HERE
EMAIL_PASSWORD = "iczzafhcdgtsjavb"    # ← PUT YOUR ACTUAL APP PASSWORD HERE

print("🧪 Testing Gmail connection...")
print(f"Email: {EMAIL_ADDRESS}")
print(f"Password: {'*' * len(EMAIL_PASSWORD)}")

try:
    # Try connection
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    print("✅ TLS connection successful")
    
    # Try login
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    print("🎉 LOGIN SUCCESSFUL!")
    
    server.quit()
    
except smtplib.SMTPAuthenticationError:
    print("❌ AUTHENTICATION FAILED - Check:")
    print("   1. Is 2FA enabled on your Gmail?")
    print("   2. Did you use an APP PASSWORD (16 chars, no spaces)?")
    print("   3. Is the app password for 'Mail'?")
except Exception as e:
    print(f"❌ Other error: {e}")