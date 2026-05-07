import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def send_verification_email(to_email: str, user_name: str, verification_link: str):
    """
    Sends a verification email to a newly created doctor account.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]) or \
       smtp_user == "your-email@gmail.com" or \
       smtp_pass == "your-app-password":
        print("[email_logic] SMTP credentials not configured. Skipping verification email.")
        return False

    subject = "Verify Your PawPoint Doctor Account"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #10B981; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">Welcome to PawPoint</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hi <strong>Dr. {user_name}</strong>,</p>
                <p>A doctor account has been created for you at PawPoint Clinic. To secure your account and access the admin dashboard, please verify your email address by clicking the button below:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" style="background-color: #10B981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Verify Email Address</a>
                </div>

                <p style="font-size: 0.9em; color: #666;">If the button above doesn't work, you can also copy and paste this link into your browser:</p>
                <p style="font-size: 0.8em; color: #10B981; word-break: break-all;">{verification_link}</p>

                <p style="margin-top: 30px;">Once verified, you can log in using the temporary password provided by your administrator.</p>
                <p>Best regards,<br>The PawPoint Team</p>
            </div>
            <div style="background-color: #f8f9fa; padding: 10px; text-align: center; font-size: 0.8em; color: #999;">
                &copy; 2026 PawPoint Clinic. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"PawPoint Clinic <{smtp_user}>"
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"[email_logic] Connecting to {smtp_host}...")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            print(f"[email_logic] Logging in as {smtp_user}...")
            server.login(smtp_user, smtp_pass)
            print("[email_logic] Sending message...")
            server.send_message(msg)
        print(f"[email_logic] SUCCESS: Verification email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[email_logic] ERROR: Failed to send verification email to {to_email}: {e}")
        return False


def send_cancellation_email(
    to_email: str,
    user_name: str,
    appointment_id: str,
    service_name: str,
    pet_name: str,
    appointment_date: str,
    amount_refunded: float,
    reason: str = "",
    refunded: bool = True,
):
    """
    Sends a cancellation and refund receipt email to the user.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    print(f"[email_logic] Attempting to send refund email to {to_email}")
    print(f"[email_logic] SMTP Config: {smtp_host}:{smtp_port} (User: {smtp_user})")

    if not all([smtp_host, smtp_user, smtp_pass]) or \
       smtp_user == "your-email@gmail.com" or \
       smtp_pass == "your-app-password":
        print("[email_logic] ERROR: SMTP credentials not configured or still using placeholders.")
        return False

    subject = f"Appointment Cancelled & Refund Receipt - {service_name}"
    
    # Format currency
    formatted_amount = f"₱{amount_refunded:,.2f}"
    
    # HTML Content
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; overflow: hidden;">
            <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-bottom: 1px solid #ddd;">
                <h1 style="color: #d9534f; margin: 0;">Appointment Cancelled</h1>
                <p style="font-size: 1.1em; color: #777;">Refund Receipt</p>
            </div>
            <div style="padding: 20px;">
                <p>Hi <strong>{user_name}</strong> icon,</p>
                <p>We are writing to inform you that your appointment has been cancelled by the clinic staff. A full refund has been processed for this transaction.</p>
                
                <div style="background-color: #fdf7f7; border-left: 5px solid #d9534f; padding: 15px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #d9534f;">Cancellation Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>Service:</strong></td>
                            <td style="padding: 5px 0;">{service_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Pet:</strong></td>
                            <td style="padding: 5px 0;">{pet_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Date:</strong></td>
                            <td style="padding: 5px 0;">{appointment_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Appointment ID:</strong></td>
                            <td style="padding: 5px 0; font-family: monospace;">{appointment_id}</td>
                        </tr>
                    </table>
                </div>

                <div style="background-color: #f0f8ff; border-left: 5px solid #007bff; padding: 15px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #007bff;">Refund Information</h3>
                    <p style="font-size: 1.2em; margin-bottom: 5px;">Total Refunded: <strong>{formatted_amount}</strong></p>
                    <p style="font-size: 0.9em; color: #555;">The amount has been credited back to your original payment method. Please allow 3-7 business days for the transaction to reflect in your account.</p>
                </div>

                {f'<p><strong>Reason for Cancellation:</strong> {reason}</p>' if reason else ""}

                <p style="margin-top: 30px;">If you have any questions, please contact our support team.</p>
                <p>Best regards,<br>The PawPoint Team</p>
            </div>
            <div style="background-color: #f8f9fa; padding: 10px; text-align: center; font-size: 0.8em; color: #999;">
                &copy; 2026 PawPoint Clinic. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"PawPoint Clinic <{smtp_user}>"
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"[email_logic] Connecting to {smtp_host}...")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            print(f"[email_logic] Logging in as {smtp_user}...")
            server.login(smtp_user, smtp_pass)
            print("[email_logic] Sending message...")
            server.send_message(msg)
        print(f"[email_logic] SUCCESS: Cancellation email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[email_logic] ERROR: Failed to send email to {to_email}: {e}")
        return False
