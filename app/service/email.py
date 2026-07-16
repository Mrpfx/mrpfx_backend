"""
Email service for sending verification and password reset emails.
Supports SMTP and Mailjet drivers, switchable via MAIL_DRIVER in .env.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
import os
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings


logger = logging.getLogger(__name__)

# Setup Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
env = Environment(loader=FileSystemLoader(template_dir))


async def _send_smtp(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = ""
) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured. Email not sent to %s", to_email)
        logger.info("Email content: Subject=%s, To=%s", subject, to_email)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if str(settings.SMTP_PORT) == "465":
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_TLS:
                server.starttls()

        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        logger.info("Email sent successfully via SMTP to %s", to_email)
        return True

    except Exception as e:
        logger.error("Failed to send SMTP email to %s: %s", to_email, str(e))
        return False


async def _send_mailjet(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = ""
) -> bool:
    if not settings.MAILJET_API_KEY or not settings.MAILJET_SECRET_KEY:
        logger.warning("Mailjet not configured. Email not sent to %s", to_email)
        logger.info("Email content: Subject=%s, To=%s", subject, to_email)
        return True

    try:
        from mailjet_rest import Client

        mailjet = Client(
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
            version="v3.1",
        )

        data = {
            "Messages": [
                {
                    "From": {
                        "Email": settings.SMTP_FROM_EMAIL,
                        "Name": settings.SMTP_FROM_NAME,
                    },
                    "To": [
                        {
                            "Email": to_email,
                        }
                    ],
                    "Subject": subject,
                    "HTMLPart": html_content,
                    "TextPart": text_content or None,
                }
            ]
        }

        result = mailjet.send.create(data=data)

        if result.status_code == 200 or result.status_code == 201:
            logger.info("Email sent successfully via Mailjet to %s", to_email)
            return True
        else:
            logger.error(
                "Mailjet send failed for %s: status=%s, body=%s",
                to_email, result.status_code, result.json(),
            )
            return False

    except Exception as e:
        logger.error("Failed to send Mailjet email to %s: %s", to_email, str(e))
        return False


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = ""
) -> bool:
    """
    Send an email using the configured mail driver.

    MAIL_DRIVER=smtp  -> uses SMTP (default)
    MAIL_DRIVER=mailjet -> uses Mailjet API
    """
    if settings.MAIL_DRIVER == "mailjet":
        return await _send_mailjet(to_email, subject, html_content, text_content)
    return await _send_smtp(to_email, subject, html_content, text_content)


def render_template(template_name: str, **context) -> str:
    """Render a Jinja2 template."""
    template = env.get_template(template_name)
    # Add common context variables
    context["app_name"] = settings.APP_NAME
    return template.render(**context)


async def send_verification_email(email: str, code: str, username: str) -> bool:
    """
    Send email verification code to user.
    """
    subject = f"Verify your email - {settings.APP_NAME}"

    html_content = render_template(
        "email/verification.html",
        username=username,
        code=code
    )

    text_content = f"""
    Hello {username},

    Thank you for signing up! Please use the verification code below to verify your email address:

    {code}

    This code will expire in 24 hours.

    If you didn't create an account, you can safely ignore this email.
    """

    return await send_email(email, subject, html_content, text_content)


async def send_password_reset_email(email: str, token: str, username: str) -> bool:
    """
    Send password reset link to user.
    """
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}&email={email}"
    subject = f"Reset your password - {settings.APP_NAME}"

    html_content = render_template(
        "email/reset_password.html",
        username=username,
        reset_link=reset_link
    )

    text_content = f"""
    Hello {username},

    We received a request to reset your password. Click the link below to create a new password:

    {reset_link}

    This link will expire in 1 hour.

    If you didn't request a password reset, you can safely ignore this email.
    """

    return await send_email(email, subject, html_content, text_content)


async def send_welcome_email(email: str, username: str) -> bool:
    """
    Send welcome email to user after verification.
    """
    subject = f"Welcome to {settings.APP_NAME}!"

    html_content = render_template(
        "email/welcome.html",
        username=username,
        dashboard_url=f"{settings.FRONTEND_URL}/dashboard"
    )

    text_content = f"""
    Welcome {username}!

    Your account has been successfully verified. We are thrilled to have you on board.

    You can now explore our courses and start learning:
    {settings.FRONTEND_URL}/dashboard
    """

    return await send_email(email, subject, html_content, text_content)


async def send_order_confirmation_email(
    email: str,
    order_id: int,
    total: float,
    currency: str,
    items: list
) -> bool:
    """
    Send order confirmation email.
    """
    subject = f"Order Confirmation #{order_id} - {settings.APP_NAME}"

    html_content = render_template(
        "email/order_confirmation.html",
        order_id=order_id,
        total=total,
        currency=currency,
        items=items
    )

    items_text = "\n".join([f"- {item}" for item in items])
    text_content = f"""
    Order Confirmed

    Thank you for your order! Here are the details:

    Order ID: #{order_id}
    Total: {total} {currency}
    Items:
    {items_text}

    We will notify you when your order status changes.
    """

    return await send_email(email, subject, html_content, text_content)


async def send_order_status_update_email(
    email: str,
    order_id: int,
    new_status: str
) -> bool:
    """
    Send order status update email.
    """
    subject = f"Order #{order_id} Update - {settings.APP_NAME}"

    html_content = render_template(
        "email/order_status.html",
        order_id=order_id,
        new_status=new_status
    )

    text_content = f"""
    Order Update

    The status of your order #{order_id} has changed to: {new_status.upper()}

    You can check the details in your dashboard.
    """

    return await send_email(email, subject, html_content, text_content)


async def send_propfirm_login_success_email(
    email: str,
    username: str,
    login_id: str,
    platform: str,
    dashboard_url: str
) -> bool:
    """
    Send notification for successful prop firm login.
    """
    subject = f"MRPFX Login Notification - {settings.APP_NAME}"

    html_content = render_template(
        "email/propfirm_login_success.html",
        username=username,
        login_id=login_id,
        platform=platform,
        dashboard_url=dashboard_url
    )

    text_content = f"""
    MRPFX Login Notification

    Hello {username},

    This is a quick notification to let you know that your MRPFX account has been successfully accessed.

    Account Details:
    Login: {login_id}
    Platform: {platform}

    If this was you, no further action is needed.
    """

    return await send_email(email, subject, html_content, text_content)


async def send_course_enrollment_email(
    email: str,
    username: str,
    course_name: str,
    course_url: str
) -> bool:
    """
    Send course enrollment confirmation.
    """
    subject = f"Enrolled in {course_name} - {settings.APP_NAME}"

    html_content = render_template(
        "email/course_enrollment.html",
        username=username,
        course_name=course_name,
        course_url=course_url
    )

    text_content = f"""
    Course Enrollment Successful!

    Hello {username},

    You have successfully enrolled in the course: {course_name}.

    Start learning now:
    {course_url}
    """

    return await send_email(email, subject, html_content, text_content)


async def send_admin_new_user_email_notification(
    admin_email: str,
    new_username: str,
    new_user_email: str
) -> bool:
    """
    Notify admin of new user registration.
    """
    subject = f"New User Registration: {new_username} - {settings.APP_NAME}"

    dashboard_url = f"{settings.FRONTEND_URL}/admin/users"

    html_content = render_template(
        "email/admin_new_user.html",
        new_username=new_username,
        new_user_email=new_user_email,
        registration_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        admin_dashboard_url=dashboard_url
    )

    text_content = f"""
    New User Registration

    A new user has registered on MRPFX.

    Username: {new_username}
    Email: {new_user_email}
    """

    return await send_email(admin_email, subject, html_content, text_content)


async def send_admin_new_order_notification(
    admin_email: str,
    order_id: int,
    customer_name: str,
    customer_email: str,
    total: float,
    currency: str,
    items: list
) -> bool:
    """
    Notify admin of new order.
    """
    subject = f"New Order Recieved #{order_id} - {settings.APP_NAME}"

    admin_order_url = f"{settings.FRONTEND_URL}/admin/orders/{order_id}"

    html_content = render_template(
        "email/admin_new_order.html",
        order_id=order_id,
        customer_name=customer_name,
        customer_email=customer_email,
        total=total,
        currency=currency,
        items=items,
        admin_order_url=admin_order_url
    )

    items_text = "\n".join([f"- {item}" for item in items])
    text_content = f"""
    New Order Received

    Order ID: #{order_id}
    Customer: {customer_name} ({customer_email})
    Total: {total} {currency}
    Items:
    {items_text}
    """

    return await send_email(admin_email, subject, html_content, text_content)


async def send_propfirm_status_update_email(
    email: str,
    username: str,
    order_id: str,
    status: str
) -> bool:
    """
    Send notification to user when their Prop Firm registration status changes.
    """
    subject = f"Prop Firm Registration Update: {order_id} - {settings.APP_NAME}"

    html_content = render_template(
        "email/propfirm_status_update.html",
        username=username,
        order_id=order_id,
        status=status.upper(),
        dashboard_url=f"{settings.FRONTEND_URL}/dashboard"
    )

    text_content = f"""
    Prop Firm Registration Update

    Hello {username},

    The status of your Prop Firm registration ({order_id}) has been updated to: {status.upper()}.

    You can check the progress in your dashboard:
    {settings.FRONTEND_URL}/dashboard
    """

    return await send_email(email, subject, html_content, text_content)


async def send_admin_propfirm_status_update_notification(
    admin_email: str,
    username: str,
    user_email: str,
    order_id: str,
    status: str
) -> bool:
    """
    Notify admin when a Prop Firm registration status is updated.
    """
    subject = f"Prop Firm Update: {order_id} ({status.upper()}) - {settings.APP_NAME}"

    html_content = render_template(
        "email/admin_propfirm_status_update.html",
        username=username,
        user_email=user_email,
        order_id=order_id,
        status=status.upper(),
        update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        admin_dashboard_url=f"{settings.FRONTEND_URL}/admin/prop-firm/registrations"
    )

    text_content = f"""
    Prop Firm Registration Updated

    User: {username} ({user_email})
    Order ID: {order_id}
    New Status: {status.upper()}
    """

    return await send_email(admin_email, subject, html_content, text_content)

async def send_account_mgmt_status_update_email(
    email: str,
    username: str,
    account_id: str,
    status: str
) -> bool:
    """
    Send notification to user when their Account Management connection status changes.
    """
    subject = f"Account Management Update: {account_id} - {settings.APP_NAME}"

    html_content = render_template(
        "email/account_mgmt_status_update.html",
        username=username,
        account_id=account_id,
        status=status.upper(),
        dashboard_url=f"{settings.FRONTEND_URL}/dashboard"
    )

    text_content = f"""
    Account Management Update

    Hello {username},

    The status of your MT5 Account Management connection ({account_id}) has been updated to: {status.upper()}.

    You can check the progress in your dashboard:
    {settings.FRONTEND_URL}/dashboard
    """

    return await send_email(email, subject, html_content, text_content)


async def send_admin_account_mgmt_connection_notification(
    admin_email: str,
    username: str,
    user_email: str,
    account_id: str,
    capital: float,
    status: str
) -> bool:
    """
    Notify admin when an Account Management connection is created or updated.
    """
    subject = f"Account Management Connection: {account_id} ({status.upper()}) - {settings.APP_NAME}"

    html_content = render_template(
        "email/admin_account_mgmt_status_update.html",
        username=username,
        user_email=user_email,
        account_id=account_id,
        capital=capital,
        status=status.upper(),
        update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        admin_dashboard_url=f"{settings.FRONTEND_URL}/admin/account-management/connections"
    )

    text_content = f"""
    Account Management Connection Updated

    User: {username} ({user_email})
    Account ID: {account_id}
    Capital: ${capital}
    New Status: {status.upper()}
    """

    return await send_email(admin_email, subject, html_content, text_content)


async def send_copy_trading_status_update_email(
    email: str,
    username: str,
    account_id: str,
    status: str
) -> bool:
    """
    Send notification to user when their Copy Trading connection status changes.
    """
    subject = f"Copy Trading Update: {account_id} - {settings.APP_NAME}"

    html_content = render_template(
        "email/copy_trading_status_update.html",
        username=username,
        account_id=account_id,
        status=status.upper(),
        dashboard_url=f"{settings.FRONTEND_URL}/dashboard"
    )

    text_content = f"""
    Copy Trading Update

    Hello {username},

    The status of your MT5 Copy Trading connection ({account_id}) has been updated to: {status.upper()}.

    You can check the progress in your dashboard:
    {settings.FRONTEND_URL}/dashboard
    """

    return await send_email(email, subject, html_content, text_content)


async def send_admin_copy_trading_connection_notification(
    admin_email: str,
    username: str,
    user_email: str,
    account_id: str,
    status: str
) -> bool:
    """
    Notify admin when a Copy Trading connection is created or updated.
    """
    subject = f"Copy Trading Connection: {account_id} ({status.upper()}) - {settings.APP_NAME}"

    html_content = render_template(
        "email/admin_copy_trading_status_update.html",
        username=username,
        user_email=user_email,
        account_id=account_id,
        status=status.upper(),
        update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        admin_dashboard_url=f"{settings.FRONTEND_URL}/admin/copy-trading"
    )

    text_content = f"""
    Copy Trading Connection Updated

    User: {username} ({user_email})
    Account ID: {account_id}
    New Status: {status.upper()}
    """

    return await send_email(admin_email, subject, html_content, text_content)
