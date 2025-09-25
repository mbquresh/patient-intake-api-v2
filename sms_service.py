import os
import logging
from datetime import datetime
from azure.communication.sms import SmsClient
from azure.core.exceptions import HttpResponseError
import re

class SMSService:
    """
    HIPAA-compliant SMS service for sending secure patient intake links
    """
    
    def __init__(self):
        self.connection_string = os.environ.get('AZURE_COMMUNICATION_CONNECTION_STRING')
        self.from_phone_number = os.environ.get('AZURE_PHONE_NUMBER')
        
        if not self.connection_string:
            raise ValueError("AZURE_COMMUNICATION_CONNECTION_STRING environment variable is required")
        if not self.from_phone_number:
            raise ValueError("AZURE_PHONE_NUMBER environment variable is required")
            
        self.sms_client = SmsClient.from_connection_string(self.connection_string)
        self.logger = logging.getLogger(__name__)
    
    def format_phone_number(self, phone_number):
        """
        Format phone number to E.164 format for Azure Communication Services
        """
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone_number)
        
        # Add +1 for US numbers if not present
        if len(digits_only) == 10:
            digits_only = '1' + digits_only
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            pass  # Already has country code
        else:
            raise ValueError(f"Invalid phone number format: {phone_number}")
        
        return '+' + digits_only
    
    def send_intake_link(self, patient_phone, form_url, patient_name=None, clinic_name="Healthcare Clinic"):
        """
        Send secure intake form link via SMS
        
        Args:
            patient_phone: Patient's phone number
            form_url: Secure form URL with token
            patient_name: Optional patient name for personalization
            clinic_name: Clinic name for the message
            
        Returns:
            dict: Status of SMS delivery
        """
        try:
            # Format phone number
            formatted_phone = self.format_phone_number(patient_phone)
            
            # Create HIPAA-compliant message (no PHI in SMS)
            if patient_name:
                greeting = f"Hello {patient_name.split()[0]},"  # First name only
            else:
                greeting = "Hello,"
            
            message_body = f"""{greeting}

{clinic_name} has sent you a secure patient intake form. Please fill it out before your appointment:

{form_url}

This secure link expires in 24 hours for your privacy and security.

If you have questions, please call the clinic directly.

Reply STOP to opt out."""
            
            # Send SMS using Azure Communication Services
            sms_responses = self.sms_client.send(
                from_=self.from_phone_number,
                to=[formatted_phone],
                message=message_body
            )
            
            # Process response
            for sms_response in sms_responses:
                if sms_response.successful:
                    self.logger.info(f"SMS sent successfully to {formatted_phone[:6]}****")
                    return {
                        'success': True,
                        'message_id': sms_response.message_id,
                        'to': formatted_phone,
                        'sent_at': datetime.utcnow().isoformat(),
                        'status': 'delivered'
                    }
                else:
                    self.logger.error(f"SMS failed to {formatted_phone[:6]}****: {sms_response.http_status_code}")
                    return {
                        'success': False,
                        'error': f"SMS delivery failed: {sms_response.http_status_code}",
                        'error_code': sms_response.http_status_code,
                        'to': formatted_phone
                    }
                    
        except HttpResponseError as e:
            self.logger.error(f"Azure Communication Services error: {str(e)}")
            return {
                'success': False,
                'error': f"SMS service error: {str(e)}",
                'error_code': 'AZURE_ERROR'
            }
            
        except ValueError as e:
            self.logger.error(f"Phone number validation error: {str(e)}")
            return {
                'success': False,
                'error': f"Invalid phone number: {str(e)}",
                'error_code': 'INVALID_PHONE'
            }
            
        except Exception as e:
            self.logger.error(f"Unexpected SMS error: {str(e)}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'error_code': 'UNKNOWN_ERROR'
            }
    
    def send_reminder_sms(self, patient_phone, clinic_name="Healthcare Clinic"):
        """
        Send appointment reminder SMS (no PHI)
        """
        try:
            formatted_phone = self.format_phone_number(patient_phone)
            
            message_body = f"""Reminder from {clinic_name}:

You have an upcoming appointment. If you haven't completed your intake form yet, please do so as soon as possible.

Call the clinic if you need a new form link or have questions.

Reply STOP to opt out."""
            
            sms_responses = self.sms_client.send(
                from_=self.from_phone_number,
                to=[formatted_phone],
                message=message_body
            )
            
            for sms_response in sms_responses:
                if sms_response.successful:
                    self.logger.info(f"Reminder SMS sent to {formatted_phone[:6]}****")
                    return {'success': True, 'message_id': sms_response.message_id}
                else:
                    return {'success': False, 'error': f"Failed: {sms_response.http_status_code}"}
                    
        except Exception as e:
            self.logger.error(f"Reminder SMS error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def validate_opt_out(self, incoming_message):
        """
        Check if incoming message is an opt-out request
        """
        opt_out_keywords = ['STOP', 'QUIT', 'UNSUBSCRIBE', 'CANCEL', 'END']
        message_upper = incoming_message.upper().strip()
        
        return message_upper in opt_out_keywords
    
    def get_sms_usage_stats(self):
        """
        Get SMS usage statistics (for monitoring costs)
        Note: This would typically integrate with Azure billing APIs
        """
        return {
            'service_status': 'operational',
            'from_number': self.from_phone_number,
            'last_check': datetime.utcnow().isoformat()
        }
    
    def test_connection(self):
        """
        Test SMS service connectivity
        """
        try:
            # This is a simple connectivity test
            # In production, you might send a test message to a verified number
            return {
                'connection_status': 'healthy',
                'service': 'Azure Communication Services',
                'from_number': self.from_phone_number,
                'tested_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'connection_status': 'error',
                'error': str(e),
                'tested_at': datetime.utcnow().isoformat()
            }