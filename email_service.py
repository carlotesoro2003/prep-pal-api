from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_FROM_NAME="PrepPal",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

fm = FastMail(conf)

async def send_password_reset_email(email: EmailStr, reset_token: str, user_name: str):
    """Send password reset email"""
    
    # Create the reset URL
    reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={reset_token}"
    
    # HTML email template
    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #333; text-align: center; margin-bottom: 30px;">
                    Reset Your PrepPal Password
                </h2>
                
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    Hello {user_name},
                </p>
                
                <p style="color: #666; font-size: 16px; line-height: 1.5;">
                    We received a request to reset your password for your PrepPal account. 
                    Click the button below to reset your password:
                </p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background-color: #007bff; color: white; padding: 15px 30px; 
                              text-decoration: none; border-radius: 5px; font-weight: bold;
                              display: inline-block;">
                        Reset Password
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px; line-height: 1.5;">
                    If you didn't request this password reset, please ignore this email. 
                    Your password will remain unchanged.
                </p>
                
                <p style="color: #666; font-size: 14px; line-height: 1.5;">
                    This link will expire in 1 hour for security reasons.
                </p>
                
                <p style="color: #666; font-size: 14px; line-height: 1.5;">
                    If the button doesn't work, copy and paste this link into your browser:
                    <br>
                    <a href="{reset_url}" style="color: #007bff; word-break: break-all;">
                        {reset_url}
                    </a>
                </p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                
                <p style="color: #999; font-size: 12px; text-align: center;">
                    This email was sent by PrepPal. If you have any questions, please contact our support team.
                </p>
            </div>
        </body>
    </html>
    """
    
    # Plain text version
    text_body = f"""
    Reset Your PrepPal Password
    
    Hello {user_name},
    
    We received a request to reset your password for your PrepPal account.
    
    Click the following link to reset your password:
    {reset_url}
    
    If you didn't request this password reset, please ignore this email.
    
    This link will expire in 1 hour for security reasons.
    
    ---
    PrepPal Team
    """
    
    message = MessageSchema(
        subject="Reset Your PrepPal Password",
        recipients=[email],
        body=text_body,
        html=html_body,
        subtype="html"
    )
    
    await fm.send_message(message)