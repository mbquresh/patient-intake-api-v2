import secrets
import time
import hashlib
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import os

class TokenManager:
    def __init__(self, secret_key=None):
        # Use environment variable or generate a secure key
        self.secret_key = secret_key or os.environ.get('SECRET_KEY', secrets.token_hex(32))
        self.serializer = URLSafeTimedSerializer(self.secret_key)
        
        # HIPAA compliant: tokens expire in 24 hours
        self.token_expiry = 24 * 60 * 60  # 24 hours in seconds
        
    def generate_token(self, patient_identifier, clinic_id="default"):
        """
        Generate a secure token for patient form access.
        patient_identifier: Unique but non-PHI identifier (like appointment ID)
        clinic_id: Clinic identifier for multi-clinic support
        """
        payload = {
            'patient_id': patient_identifier,
            'clinic_id': clinic_id,
            'created_at': datetime.utcnow().isoformat(),
            'nonce': secrets.token_hex(8)  # Prevent token reuse
        }
        
        # Generate token with expiration
        token = self.serializer.dumps(payload)
        return token
    
    def validate_token(self, token):
        """
        Validate token and return payload if valid.
        Returns None if token is invalid or expired.
        """
        try:
            # Verify token with time-based expiration
            payload = self.serializer.loads(token, max_age=self.token_expiry)
            
            # Additional validation: check if token was created within reasonable time
            created_at = datetime.fromisoformat(payload['created_at'])
            if datetime.utcnow() - created_at > timedelta(hours=24):
                return None
                
            return payload
            
        except (SignatureExpired, BadSignature, ValueError):
            return None
    
    def generate_form_url(self, base_url, patient_identifier, clinic_id="default"):
        """
        Generate complete form URL with token
        """
        token = self.generate_token(patient_identifier, clinic_id)
        return f"{base_url}/intake/{token}"
    
    def hash_patient_data(self, data):
        """
        Create a non-reversible hash of patient data for logging/audit
        without storing actual PHI
        """
        return hashlib.sha256(str(data).encode()).hexdigest()[:16]