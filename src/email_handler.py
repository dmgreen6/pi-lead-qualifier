"""
Email handler for Pflug Law Lead Qualifier.
Handles Gmail API integration for notifications and referrals.
"""

import base64
import logging
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import EmailConfig
from .airtable_client import Lead
from .qualifier import QualificationResult, QualificationTier

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


@dataclass
class EmailMessage:
    """Represents an email to be sent."""
    to: str
    subject: str
    body_html: str
    body_text: str
    from_email: Optional[str] = None


class EmailHandler:
    """Gmail API email handler."""

    def __init__(self, config: EmailConfig):
        self.config = config
        self._service = None

    def _get_credentials(self) -> Optional[Credentials]:
        """Get or refresh Gmail API credentials."""
        creds = None
        token_path = Path(self.config.token_file)
        creds_path = Path(self.config.credentials_file)

        # Load existing token
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                if not creds_path.exists():
                    logger.error(f"Credentials file not found: {creds_path}")
                    return None
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Failed to get credentials: {e}")
                    return None

            # Save credentials
            if creds:
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

        return creds

    @property
    def service(self):
        """Get Gmail API service."""
        if self._service is None:
            creds = self._get_credentials()
            if creds:
                self._service = build('gmail', 'v1', credentials=creds)
        return self._service

    def send_email(self, message: EmailMessage) -> bool:
        """Send an email via Gmail API."""
        if not self.service:
            logger.error("Gmail service not available")
            return False

        try:
            # Create MIME message
            mime_msg = MIMEMultipart('alternative')
            mime_msg['To'] = message.to
            mime_msg['From'] = message.from_email or self.config.sender_email
            mime_msg['Subject'] = message.subject

            # Attach text and HTML parts
            part1 = MIMEText(message.body_text, 'plain')
            part2 = MIMEText(message.body_html, 'html')
            mime_msg.attach(part1)
            mime_msg.attach(part2)

            # Encode and send
            raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
            body = {'raw': raw}

            self.service.users().messages().send(
                userId='me', body=body
            ).execute()

            logger.info(f"Email sent to {message.to}: {message.subject}")
            return True

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_auto_accept_notification(self, lead: Lead, result: QualificationResult,
                                       clio_matter_url: Optional[str] = None) -> bool:
        """Send notification email for auto-accepted lead."""
        subject = f"AUTO-ACCEPTED: {lead.name} - {result.injury_type} - Score: {result.total_score}"

        body_text = f"""
AUTO-ACCEPTED LEAD

Name: {lead.name}
Phone: {lead.phone or 'N/A'}
Email: {lead.email or 'N/A'}
Score: {result.total_score} points

Injury Type: {result.injury_type}
Accident Location: {lead.accident_location or 'N/A'}
Accident Date: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'N/A'}

QUALIFICATION CRITERIA MET:
{chr(10).join('- ' + s for s in result.strengths)}

{f"Clio Matter: {clio_matter_url}" if clio_matter_url else "Clio matter creation pending"}

{f"AI ASSESSMENT:{chr(10)}{result.ai_analysis}" if result.ai_analysis else ""}

NEXT STEPS:
1. Schedule intake call within 24 hours
2. Gather police report
3. Send representation letter to insurance carrier

---
Pflug Law Lead Qualifier System
        """

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px;">
<h2 style="color: #28a745;">AUTO-ACCEPTED LEAD</h2>

<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Name:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.name}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Phone:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.phone or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Email:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.email or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Score:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong style="color: #28a745;">{result.total_score} points</strong></td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Injury Type:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{result.injury_type}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Location:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.accident_location or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Accident Date:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'N/A'}</td></tr>
</table>

<h3>Qualification Criteria Met:</h3>
<ul style="color: #28a745;">
{''.join(f'<li>{s}</li>' for s in result.strengths)}
</ul>

{f'<p><a href="{clio_matter_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Open Clio Matter</a></p>' if clio_matter_url else '<p><em>Clio matter creation pending</em></p>'}

{f'<h3>AI Assessment:</h3><p style="background: #f8f9fa; padding: 15px; border-radius: 5px;">{result.ai_analysis}</p>' if result.ai_analysis else ''}

<h3>Next Steps:</h3>
<ol>
<li>Schedule intake call within 24 hours</li>
<li>Gather police report</li>
<li>Send representation letter to insurance carrier</li>
</ol>

<hr style="margin-top: 30px;">
<p style="color: #6c757d; font-size: 12px;">Pflug Law Lead Qualifier System</p>
</body>
</html>
        """

        message = EmailMessage(
            to=self.config.notification_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        return self.send_email(message)

    def send_review_notification(self, lead: Lead, result: QualificationResult) -> bool:
        """Send notification email for lead requiring review."""
        subject = f"REVIEW NEEDED: {lead.name} - {result.injury_type} - Score: {result.total_score}"

        # Build recommendation
        if result.total_score >= 9:
            recommendation = "LIKELY ACCEPT - Strong case with minor concerns"
        elif result.total_score >= 7:
            recommendation = "BORDERLINE - Gather more information before deciding"
        else:
            recommendation = "LIKELY DECLINE - Multiple concerns identified"

        body_text = f"""
REVIEW NEEDED

Name: {lead.name}
Phone: {lead.phone or 'N/A'}
Email: {lead.email or 'N/A'}
Score: {result.total_score} points

Injury Type: {result.injury_type}
Accident Location: {lead.accident_location or 'N/A'}
Accident Date: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'N/A'}

STRENGTHS:
{chr(10).join('+ ' + s for s in result.strengths) or 'None identified'}

CONCERNS:
{chr(10).join('- ' + c for c in result.concerns) or 'None identified'}

SAFETY FLAGS:
{chr(10).join('! ' + f.description for f in result.safety_flags) or 'None'}

MISSING INFORMATION:
{chr(10).join('? ' + m for m in result.missing_info) or 'None'}

RECOMMENDED QUESTIONS:
{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(result.recommended_questions)) or 'None'}

{f"AI ASSESSMENT:{chr(10)}{result.ai_analysis}" if result.ai_analysis else ""}

RECOMMENDATION: {recommendation}

---
Pflug Law Lead Qualifier System
        """

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px;">
<h2 style="color: #ffc107;">REVIEW NEEDED</h2>

<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Name:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.name}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Phone:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.phone or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Email:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.email or 'N/A'}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Score:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong style="color: #ffc107;">{result.total_score} points</strong></td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Injury Type:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{result.injury_type}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Location:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.accident_location or 'N/A'}</td></tr>
</table>

{f'<h3 style="color: #28a745;">Strengths:</h3><ul style="color: #28a745;">{"".join(f"<li>{s}</li>" for s in result.strengths)}</ul>' if result.strengths else ''}

{f'<h3 style="color: #dc3545;">Concerns:</h3><ul style="color: #dc3545;">{"".join(f"<li>{c}</li>" for c in result.concerns)}</ul>' if result.concerns else ''}

{f'<h3 style="color: #fd7e14;">Safety Flags:</h3><ul style="color: #fd7e14;">{"".join(f"<li>{f.description}</li>" for f in result.safety_flags)}</ul>' if result.safety_flags else ''}

{f'<h3>Missing Information:</h3><ul>{"".join(f"<li>{m}</li>" for m in result.missing_info)}</ul>' if result.missing_info else ''}

{f'<h3>Recommended Questions:</h3><ol>{"".join(f"<li>{q}</li>" for q in result.recommended_questions)}</ol>' if result.recommended_questions else ''}

{f'<h3>AI Assessment:</h3><p style="background: #f8f9fa; padding: 15px; border-radius: 5px;">{result.ai_analysis}</p>' if result.ai_analysis else ''}

<div style="background: #e9ecef; padding: 15px; border-radius: 5px; margin-top: 20px;">
<strong>RECOMMENDATION:</strong> {recommendation}
</div>

<hr style="margin-top: 30px;">
<p style="color: #6c757d; font-size: 12px;">Pflug Law Lead Qualifier System</p>
</body>
</html>
        """

        message = EmailMessage(
            to=self.config.notification_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        return self.send_email(message)

    def send_decline_notification(self, lead: Lead, result: QualificationResult) -> bool:
        """Send notification email for auto-declined lead."""
        primary_reason = result.concerns[0] if result.concerns else "Does not meet qualification criteria"

        subject = f"AUTO-DECLINED: {lead.name} - Reason: {primary_reason}"

        body_text = f"""
AUTO-DECLINED LEAD (For Your Records)

Name: {lead.name}
Phone: {lead.phone or 'N/A'}
Email: {lead.email or 'N/A'}
Score: {result.total_score} points

Injury Type: {result.injury_type}
Accident Location: {lead.accident_location or 'N/A'}
Accident Date: {lead.accident_date.strftime('%Y-%m-%d') if lead.accident_date else 'N/A'}

REASONS FOR DECLINE:
{chr(10).join('- ' + c for c in result.concerns)}
{chr(10).join('- ' + f.description for f in result.safety_flags) if result.safety_flags else ''}

A polite referral email has been sent to the lead.

---
Pflug Law Lead Qualifier System
        """

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px;">
<h2 style="color: #dc3545;">AUTO-DECLINED LEAD</h2>
<p style="color: #6c757d;">For your records only</p>

<table style="width: 100%; border-collapse: collapse;">
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Name:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.name}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Score:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong style="color: #dc3545;">{result.total_score} points</strong></td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Injury Type:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{result.injury_type}</td></tr>
<tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Location:</strong></td>
    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{lead.accident_location or 'N/A'}</td></tr>
</table>

<h3 style="color: #dc3545;">Reasons for Decline:</h3>
<ul style="color: #dc3545;">
{''.join(f'<li>{c}</li>' for c in result.concerns)}
{''.join(f'<li>{f.description}</li>' for f in result.safety_flags)}
</ul>

<p><em>A polite referral email has been sent to the lead.</em></p>

<hr style="margin-top: 30px;">
<p style="color: #6c757d; font-size: 12px;">Pflug Law Lead Qualifier System</p>
</body>
</html>
        """

        message = EmailMessage(
            to=self.config.notification_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        return self.send_email(message)

    def send_referral_email(self, lead: Lead) -> bool:
        """Send polite referral email to declined lead."""
        if not lead.email:
            logger.warning(f"Cannot send referral email - no email for {lead.name}")
            return False

        subject = "Thank You for Contacting Pflug Law"

        body_text = f"""
Dear {lead.name.split()[0] if lead.name else 'Friend'},

Thank you for contacting Pflug Law regarding your potential legal matter.

After careful review, we have determined that your case falls outside our current practice focus. We understand this may be disappointing, and we want to ensure you receive the help you need.

We recommend contacting the South Carolina Bar Lawyer Referral Service:
- Phone: (803) 799-7100
- Website: www.scbar.org/public/lawyer-referral-service/

They can connect you with an attorney who may be better suited to assist with your specific situation.

We wish you the best in finding the right representation for your case.

Sincerely,
Pflug Law
        """

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; line-height: 1.6;">
<p>Dear {lead.name.split()[0] if lead.name else 'Friend'},</p>

<p>Thank you for contacting Pflug Law regarding your potential legal matter.</p>

<p>After careful review, we have determined that your case falls outside our current practice focus. We understand this may be disappointing, and we want to ensure you receive the help you need.</p>

<p>We recommend contacting the <strong>South Carolina Bar Lawyer Referral Service</strong>:</p>
<ul>
<li>Phone: <a href="tel:8037997100">(803) 799-7100</a></li>
<li>Website: <a href="https://www.scbar.org/public/lawyer-referral-service/">www.scbar.org/public/lawyer-referral-service/</a></li>
</ul>

<p>They can connect you with an attorney who may be better suited to assist with your specific situation.</p>

<p>We wish you the best in finding the right representation for your case.</p>

<p>Sincerely,<br>
<strong>Pflug Law</strong></p>
</body>
</html>
        """

        message = EmailMessage(
            to=lead.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            from_email=self.config.intake_email,
        )

        return self.send_email(message)

    def send_error_notification(self, error_message: str, lead: Optional[Lead] = None) -> bool:
        """Send error notification to attorney."""
        subject = "SYSTEM ERROR: Pflug Lead Qualifier"

        lead_info = ""
        if lead:
            lead_info = f"""
Lead Information:
- Name: {lead.name}
- Record ID: {lead.record_id}
- Phone: {lead.phone or 'N/A'}
"""

        body_text = f"""
SYSTEM ERROR ALERT

The Pflug Lead Qualifier encountered an error:

{error_message}

{lead_info}

Please check the system logs for more details.

---
Pflug Law Lead Qualifier System
        """

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px;">
<h2 style="color: #dc3545;">SYSTEM ERROR ALERT</h2>

<p>The Pflug Lead Qualifier encountered an error:</p>

<pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">
{error_message}
</pre>

{f'''
<h3>Lead Information:</h3>
<ul>
<li>Name: {lead.name}</li>
<li>Record ID: {lead.record_id}</li>
<li>Phone: {lead.phone or 'N/A'}</li>
</ul>
''' if lead else ''}

<p>Please check the system logs for more details.</p>

<hr style="margin-top: 30px;">
<p style="color: #6c757d; font-size: 12px;">Pflug Law Lead Qualifier System</p>
</body>
</html>
        """

        message = EmailMessage(
            to=self.config.notification_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        return self.send_email(message)

    def test_connection(self) -> bool:
        """Test Gmail API connection."""
        try:
            if self.service:
                # Try to get user profile
                profile = self.service.users().getProfile(userId='me').execute()
                logger.info(f"Gmail connection test successful. Email: {profile.get('emailAddress')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Gmail connection test failed: {e}")
            return False
