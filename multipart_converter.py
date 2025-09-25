from datetime import datetime
import json
import logging

class MultipartConverter:
    """
    Enhanced multipart form data to JSON converter for v2.0
    Built upon lessons learned from v1 with healthcare-specific improvements
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def convert_form_to_json(self, form_data, files=None):
        """
        Convert form data to structured JSON for healthcare intake
        
        Args:
            form_data: Dictionary of form fields
            files: Optional file uploads (for future enhancement)
        
        Returns:
            Dictionary with structured patient data
        """
        try:
            # Initialize structured output
            structured_data = {
                'personal_information': {},
                'contact_information': {},
                'address': {},
                'emergency_contact': {},
                'insurance_information': {},
                'medical_information': {},
                'visit_information': {}
            }
            
            # Process personal information
            personal_fields = ['first_name', 'last_name', 'date_of_birth']
            for field in personal_fields:
                if field in form_data and form_data[field]:
                    structured_data['personal_information'][field] = self._sanitize_field(form_data[field])
            
            # Process contact information
            contact_fields = ['phone', 'email']
            for field in contact_fields:
                if field in form_data and form_data[field]:
                    structured_data['contact_information'][field] = self._sanitize_field(form_data[field])
            
            # Process address
            address_fields = ['street_address', 'city', 'state', 'zip_code']
            for field in address_fields:
                if field in form_data and form_data[field]:
                    structured_data['address'][field] = self._sanitize_field(form_data[field])
            
            # Process emergency contact
            emergency_fields = ['emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship']
            for field in emergency_fields:
                if field in form_data and form_data[field]:
                    clean_field = field.replace('emergency_contact_', '')
                    structured_data['emergency_contact'][clean_field] = self._sanitize_field(form_data[field])
            
            # Process insurance information
            insurance_fields = ['insurance_provider', 'insurance_id', 'primary_physician']
            for field in insurance_fields:
                if field in form_data and form_data[field]:
                    structured_data['insurance_information'][field] = self._sanitize_field(form_data[field])
            
            # Process medical information
            medical_fields = ['current_medications', 'allergies', 'medical_history']
            for field in medical_fields:
                if field in form_data and form_data[field]:
                    structured_data['medical_information'][field] = self._sanitize_field(form_data[field])
            
            # Process visit information
            visit_fields = ['reason_for_visit']
            for field in visit_fields:
                if field in form_data and form_data[field]:
                    structured_data['visit_information'][field] = self._sanitize_field(form_data[field])
            
            # Handle file uploads (for future enhancement)
            if files:
                structured_data['uploaded_documents'] = self._process_files(files)
            
            # Add processing metadata
            structured_data['processing_info'] = {
                'processed_at': datetime.utcnow().isoformat(),
                'converter_version': '2.0',
                'total_fields': len([k for section in structured_data.values() 
                                   if isinstance(section, dict) for k in section.keys()]),
                'data_quality_score': self._calculate_completeness_score(structured_data)
            }
            
            # Remove empty sections
            cleaned_data = {k: v for k, v in structured_data.items() 
                          if v and (not isinstance(v, dict) or any(v.values()))}
            
            self.logger.info(f"Successfully converted form data with {len(cleaned_data)} sections")
            return cleaned_data
            
        except Exception as e:
            self.logger.error(f"Conversion error: {str(e)}")
            raise
    
    def _sanitize_field(self, value):
        """
        Sanitize and validate individual form fields
        """
        if not value:
            return None
        
        # Basic sanitization
        if isinstance(value, str):
            # Remove potential XSS attempts and extra whitespace
            sanitized = value.strip()
            # Remove null bytes and control characters
            sanitized = ''.join(char for char in sanitized if ord(char) >= 32)
            return sanitized if sanitized else None
        
        return value
    
    def _process_files(self, files):
        """
        Process uploaded files (placeholder for future file upload feature)
        """
        file_info = {}
        for field_name, file_obj in files.items():
            if file_obj and file_obj.filename:
                file_info[field_name] = {
                    'filename': file_obj.filename,
                    'content_type': file_obj.content_type,
                    'size': len(file_obj.read()) if hasattr(file_obj, 'read') else 0
                }
                # Reset file pointer if possible
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
        
        return file_info if file_info else None
    
    def _calculate_completeness_score(self, data):
        """
        Calculate data completeness score for quality assessment
        """
        try:
            total_fields = 0
            completed_fields = 0
            
            sections_to_check = ['personal_information', 'contact_information', 
                               'address', 'emergency_contact', 'visit_information']
            
            for section in sections_to_check:
                if section in data and isinstance(data[section], dict):
                    for field_name, field_value in data[section].items():
                        total_fields += 1
                        if field_value and str(field_value).strip():
                            completed_fields += 1
            
            if total_fields == 0:
                return 0
            
            score = (completed_fields / total_fields) * 100
            return round(score, 2)
            
        except Exception:
            return 0
    
    def validate_required_fields(self, data):
        """
        Validate that required fields are present and valid
        """
        required_fields = {
            'personal_information': ['first_name', 'last_name', 'date_of_birth'],
            'contact_information': ['phone'],
            'address': ['street_address', 'city', 'state', 'zip_code'],
            'emergency_contact': ['name', 'phone'],
            'visit_information': ['reason_for_visit']
        }
        
        missing_fields = []
        
        for section, fields in required_fields.items():
            if section not in data:
                missing_fields.extend([f"{section}.{field}" for field in fields])
            else:
                for field in fields:
                    if field not in data[section] or not data[section][field]:
                        missing_fields.append(f"{section}.{field}")
        
        return missing_fields
    
    def format_for_clinic_template(self, structured_data):
        """
        Format structured data to match clinic's specific template requirements
        This can be customized per clinic
        """
        # Flatten the structure for template population
        flattened = {}
        
        for section, fields in structured_data.items():
            if isinstance(fields, dict):
                for field_name, field_value in fields.items():
                    template_key = f"{section}_{field_name}".lower()
                    flattened[template_key] = field_value
            else:
                flattened[section] = fields
        
        return flattened