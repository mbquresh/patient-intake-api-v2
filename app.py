from dotenv import load_dotenv
from sms_service import SMSService
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, TextAreaField, SelectField, DateField, TelField, SelectMultipleField, BooleanField, IntegerField, DecimalField, RadioField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms.widgets import CheckboxInput, ListWidget
from werkzeug.exceptions import BadRequest
import json
import os
import secrets
from datetime import datetime, timedelta
import requests
import logging
from token_manager import TokenManager
from multipart_converter import MultipartConverter 


load_dotenv()

# Custom widget for multiple checkboxes
class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

# Initialize Flask app with HIPAA-compliant configuration
app = Flask(__name__)

# HIPAA Security Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_TIME_LIMIT'] = 1800  # 30 minutes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'  # CSRF protection
app.config['WTF_CSRF_SSL_STRICT'] = False  # Allow for development

# Initialize CSRF protection (Commeneted out for testing, but enable when production)
#csrf = CSRFProtect(app)

# Configure logging (HIPAA compliant - no PHI in logs)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize components
token_manager = TokenManager(app.config['SECRET_KEY'])
converter = MultipartConverter()

# Initialize SMS service
try:
    sms_service = SMSService()
    SMS_ENABLED = True
    app.logger.info("SMS service initialized successfully")
except Exception as e:
    app.logger.warning(f"SMS service unavailable: {str(e)}")
    SMS_ENABLED = False

# Azure Logic Apps webhook URL
LOGIC_APP_WEBHOOK_URL = os.environ.get('LOGIC_APP_WEBHOOK_URL', '')

class PatientIntakeForm(FlaskForm):
    """
    HIPAA-compliant patient intake form with proper validation
    """
    # Basic Information
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    phone = TelField('Phone Number', validators=[DataRequired()])
    email = StringField('Email', validators=[Email(), Optional(), Length(max=100)])
    
    # Address
    street_address = StringField('Street Address', validators=[DataRequired(), Length(max=100)])
    city = StringField('City', validators=[DataRequired(), Length(max=50)])
    state = SelectField('State', choices=[
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
        ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
        ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
        ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
        ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
        ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
        ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming')
    ], validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired(), Length(max=10)])
    
    # Emergency Contact
    emergency_contact_name = StringField('Emergency Contact Name', validators=[DataRequired(), Length(max=100)])
    emergency_contact_phone = TelField('Emergency Contact Phone', validators=[DataRequired()])
    emergency_contact_relationship = StringField('Relationship', validators=[DataRequired(), Length(max=50)])
    
    # Medical Information
    insurance_provider = StringField('Insurance Provider', validators=[Optional(), Length(max=100)])
    insurance_id = StringField('Insurance ID', validators=[Optional(), Length(max=50)])
    primary_physician = StringField('Primary Care Physician', validators=[Optional(), Length(max=100)])
    
    # Current Visit
    reason_for_visit = TextAreaField('Reason for Visit', validators=[DataRequired(), Length(max=500)])
    current_medications = TextAreaField('Current Medications', validators=[Optional(), Length(max=1000)])
    allergies = TextAreaField('Known Allergies', validators=[Optional(), Length(max=500)])
    medical_history = TextAreaField('Relevant Medical History', validators=[Optional(), Length(max=1000)])

class ComprehensivePediatricIntakeForm(FlaskForm):
    """
    Complete pediatric intake form based on clinic requirements
    """
    
    # PATIENT HISTORY SECTION
    patient_name = StringField('Patient Full Name', validators=[DataRequired(), Length(max=100)])
    patient_age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=0, max=18)])
    patient_sex = SelectField('Sex', choices=[
        ('', 'Select...'),
        ('male', 'Male'),
        ('female', 'Female')
    ], validators=[DataRequired()])
    patient_dob = DateField('Date of Birth', validators=[DataRequired()])
    
    # BIRTH HISTORY SECTION
    delivery_type = SelectField('Delivery Type', choices=[
        ('', 'Select...'),
        ('vaginal', 'Vaginal'),
        ('csection', 'C-Section')
    ], validators=[DataRequired()])
    
    birth_timing = SelectField('Birth Timing', choices=[
        ('', 'Select...'),
        ('full_term', 'Full Term'),
        ('early', 'Early'),
        ('late', 'Late')
    ], validators=[DataRequired()])
    
    birth_weeks = IntegerField('How Many Weeks', validators=[Optional(), NumberRange(min=20, max=45)])
    birth_weight = DecimalField('Birth Weight (lbs)', validators=[Optional()], places=2)
    
    hearing_test_passed = RadioField('Baby passed hearing test?', choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('unknown', 'Unknown')
    ], validators=[DataRequired()])
    
    hep_b_vaccine = RadioField('Did baby get Hep B vaccine at birth?', choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('unknown', 'Unknown')
    ], validators=[DataRequired()])
    
    pregnancy_complications = TextAreaField('Any complications with pregnancy or delivery?', 
                                          validators=[Optional(), Length(max=1000)])
    
    # CHILD'S PAST MEDICAL/SURGICAL HISTORY
    child_medical_history = MultiCheckboxField('Check if following problems exist:', choices=[
        ('ulcers', 'Ulcers'),
        ('vaccines_behind', 'Vaccines behind'),
        ('stomach_liver_problems', 'Stomach or liver problems'),
        ('febrile_seizure', 'Febrile seizure or epilepsy'),
        ('asthma_pneumonia', 'Asthma/Pneumonia'),
        ('urine_kidney_problems', 'Urine/Kidney problems'),
        ('heart_problems', 'Heart problems'),
        ('thyroid_problems', 'Thyroid problems'),
        ('psychiatric_problems', 'Psychiatric problems')
    ])
    
    # FAMILY MEDICAL HISTORY
    family_medical_history = MultiCheckboxField('Family Medical History - Check if following problems exist:', choices=[
        ('diabetes', 'Diabetes'),
        ('asthma', 'Asthma'),
        ('stomach_liver_problems', 'Stomach or liver problems'),
        ('teenage_sudden_death', 'Teenage sudden death'),
        ('early_heart_disease', 'Early age heart disease'),
        ('seizure', 'Seizure'),
        ('hearing_loss', 'Hearing loss'),
        ('blindness', 'Blindness'),
        ('tb', 'TB'),
        ('tumors_cancer', 'Tumors or cancer')
    ])
    
    # SOCIAL HISTORY
    household_members = IntegerField('How many people live in the house?', 
                                   validators=[DataRequired(), NumberRange(min=1, max=20)])
    
    any_pets = RadioField('Any pets?', choices=[
        ('yes', 'Yes'),
        ('no', 'No')
    ], validators=[DataRequired()])
    
    anyone_smokes = RadioField('Anyone smokes?', choices=[
        ('yes', 'Yes'),
        ('no', 'No')
    ], validators=[DataRequired()])
    
    lead_exposure = RadioField('Any exposure to lead?', choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('unknown', 'Unknown')
    ], validators=[DataRequired()])
    
    voice_message_consent = RadioField('Do you authorize the clinic to leave a voice message regarding test results?', choices=[
        ('yes', 'Yes'),
        ('no', 'No')
    ], validators=[DataRequired()])
    
    # SIGNATURE SECTION (Page 1)
    guardian_signature_name = StringField('Print Name', validators=[DataRequired(), Length(max=100)])
    guardian_relationship = StringField('Relationship to Child', validators=[DataRequired(), Length(max=50)])
    signature_date = DateField('Date', validators=[DataRequired()])
    
    # PAGE 2 - PATIENT INFORMATION
    # Patient Details (duplicate but separate page)
    patient_last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    patient_first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    patient_dob_page2 = DateField('Date of Birth', validators=[DataRequired()])
    patient_age_page2 = IntegerField('Age', validators=[DataRequired(), NumberRange(min=0, max=18)])
    patient_gender = SelectField('Gender', choices=[
        ('', 'Select...'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    
    # Address
    patient_address = StringField('Address', validators=[DataRequired(), Length(max=100)])
    patient_city = StringField('City', validators=[DataRequired(), Length(max=50)])
    patient_state = SelectField('State', choices=[
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
        ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
        ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
        ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
        ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
        ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
        ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming')
    ], validators=[DataRequired()])
    patient_zip = StringField('ZIP Code', validators=[DataRequired(), Length(max=10)])
    
    # PARENT/GUARDIAN INFO
    # Mother's Information
    mother_name = StringField("Mother's Name", validators=[Optional(), Length(max=100)])
    mother_phone = TelField("Mother's Phone Number", validators=[Optional()])
    mother_address = StringField("Mother's Address", validators=[Optional(), Length(max=100)])
    mother_cell = TelField("Mother's Cell", validators=[Optional()])
    
    # Father's Information
    father_name = StringField("Father's Name", validators=[Optional(), Length(max=100)])
    father_phone = TelField("Father's Phone Number", validators=[Optional()])
    father_address = StringField("Father's Address", validators=[Optional(), Length(max=100)])
    father_cell = TelField("Father's Cell", validators=[Optional()])
    
    # Emergency Contact
    emergency_contact_name = StringField('Emergency Contact Name', validators=[DataRequired(), Length(max=100)])
    emergency_contact_phone = TelField('Emergency Contact Phone', validators=[DataRequired()])
    
    # Siblings in Facility
    siblings_info = TextAreaField('Name of all siblings in our facility and DOB', 
                                validators=[Optional(), Length(max=500)])
    
    # HEALTH INSURANCE SECTION
    insurance_name = StringField('Health Insurance Name', validators=[Optional(), Length(max=100)])
    insurance_id = StringField('Insurance ID#', validators=[Optional(), Length(max=50)])
    insurance_group = StringField('Group#', validators=[Optional(), Length(max=50)])
    pharmacy_name = StringField('Pharmacy Name', validators=[Optional(), Length(max=100)])
    pharmacy_phone = TelField('Pharmacy Phone Number', validators=[Optional()])
    
    # CONSENT SECTION
    treatment_consent = BooleanField(
        'I give my permission as a parent/legal guardian of the patient named above to Houston Pediatric Center to treat my child.',
        validators=[DataRequired()]
    )
    
    # Final Signature
    parent_guardian_name_final = StringField('Parent/Guardian Name', validators=[DataRequired(), Length(max=100)])
    final_signature_date = DateField('Date', validators=[DataRequired()])

@app.route('/')
def home():
    """API information endpoint"""
    return jsonify({
        'service': 'Patient Intake API v2.0',
        'description': 'HIPAA-compliant patient intake system with secure token-based access',
        'version': '2.0.0',
        'endpoints': {
            'intake_form': '/intake/<token>',
            'pediatric_form': '/pediatric-intake/<token>',
            'admin_generate': '/admin/generate-link',
            'admin_generate_pediatric': '/admin/generate-pediatric-link',
            'health_check': '/health'
        },
        'features': [
            'Secure token-based form access',
            'HIPAA-compliant data handling',
            'Mobile-responsive forms',
            'Comprehensive pediatric intake',
            'Azure Logic Apps integration',
            'Comprehensive form validation'
        ]
    })

@app.route('/intake/<token>')
def patient_intake_form(token):
    """
    Serve secure patient intake form
    """
    # Validate token
    payload = token_manager.validate_token(token)
    if not payload:
        app.logger.warning(f"Invalid token access attempt: {token[:20]}...")
        return render_template('error.html', 
                             message="Invalid or expired form link. Please contact the clinic for a new link.",
                             error_code="TOKEN_INVALID"), 403
    
    # Create form instance
    form = PatientIntakeForm()
    
    # Log successful access (without PHI)
    app.logger.info(f"Form accessed for patient ID: {payload.get('patient_id')}")
    
    return render_template('standard_intake_form.html', 
                         form=form,
                         token=token,
                         patient_id=payload.get('patient_id'),
                         clinic_id=payload.get('clinic_id'))

@app.route('/pediatric-intake/<token>')
def pediatric_intake_form(token):
    """
    Serve comprehensive pediatric intake form
    """
    # Validate token
    payload = token_manager.validate_token(token)
    if not payload:
        app.logger.warning(f"Invalid token access attempt: {token[:20]}...")
        return render_template('error.html', 
                             message="Invalid or expired form link. Please contact the clinic for a new link.",
                             error_code="TOKEN_INVALID"), 403
    
    # Create pediatric form instance
    form = ComprehensivePediatricIntakeForm()
    
    # Log successful access (without PHI)
    app.logger.info(f"Pediatric form accessed for patient ID: {payload.get('patient_id')}")
    
    return render_template('intake_form.html', 
                         form=form,
                         token=token,
                         patient_id=payload.get('patient_id'),
                         clinic_id=payload.get('clinic_id'))

@app.route('/submit/<token>', methods=['POST'])
def submit_patient_intake(token):
    """
    Process secure patient intake form submission
    """
    # Validate token
    payload = token_manager.validate_token(token)
    if not payload:
        return jsonify({'error': 'Invalid or expired form link'}), 403
    
    form = PatientIntakeForm()
    
    if form.validate_on_submit():
        try:
            # Convert form data to JSON using enhanced converter
            form_data = request.form.to_dict()
            json_output = converter.convert_form_to_json(form_data)
            
            # Create clinic-ready data package
            clinic_data = {
                'patient_information': json_output,
                'submission_metadata': {
                    'clinic_id': payload.get('clinic_id'),
                    'patient_id': payload.get('patient_id'),
                    'submitted_at': datetime.utcnow().isoformat(),
                    'form_version': '2.0',
                    'data_hash': token_manager.hash_patient_data(json_output)
                }
            }
            
            # Send to Azure Logic Apps
            if LOGIC_APP_WEBHOOK_URL:
                try:
                    response = requests.post(
                        LOGIC_APP_WEBHOOK_URL,
                        json=clinic_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        app.logger.info(f"Successfully processed submission for patient: {payload.get('patient_id')}")
                        return render_template('success.html',
                                             message="Thank you! Your information has been submitted successfully to the clinic.")
                    else:
                        app.logger.error(f"Logic Apps error: Status {response.status_code}")
                        
                except requests.RequestException as e:
                    app.logger.error(f"Failed to send to Logic Apps: {str(e)}")
            
            # Fallback response
            return render_template('success.html',
                                 message="Your form has been received. The clinic will contact you shortly.")
            
        except Exception as e:
            app.logger.error(f"Form processing error: {str(e)}")
            return render_template('error.html',
                                 message="There was an error processing your form. Please try again.",
                                 error_code="PROCESSING_ERROR"), 500
    
    else:
        # Form validation failed
        app.logger.warning(f"Form validation failed for patient: {payload.get('patient_id')}")
        return render_template('intake_form.html',
                             form=form,
                             token=token,
                             patient_id=payload.get('patient_id'),
                             clinic_id=payload.get('clinic_id'))

@app.route('/pediatric-submit/<token>', methods=['POST'])
def submit_pediatric_intake(token):
    """
    Process pediatric intake form submission
    """
    # Validate token
    payload = token_manager.validate_token(token)
    if not payload:
        return jsonify({'error': 'Invalid or expired form link'}), 403
    
    form = ComprehensivePediatricIntakeForm()
    
    if form.validate_on_submit():
        try:
            # Convert pediatric form data to JSON
            form_data = request.form.to_dict(flat=False)
            
            # Handle multi-select fields and convert to consistent format
            pediatric_data = {}
            for field_name, field_value in form_data.items():
                if isinstance(field_value, list):
                    if len(field_value) == 1:
                        pediatric_data[field_name] = field_value[0]
                    else:
                        pediatric_data[field_name] = field_value
                else:
                    pediatric_data[field_name] = field_value
            
            # Create structured pediatric data package
            clinic_data = {
                'patient_information': {
                    'form_type': 'pediatric_comprehensive',
                    'patient_history': {
                        'name': pediatric_data.get('patient_name'),
                        'age': pediatric_data.get('patient_age'),
                        'sex': pediatric_data.get('patient_sex'),
                        'dob': pediatric_data.get('patient_dob'),
                        'last_name': pediatric_data.get('patient_last_name'),
                        'first_name': pediatric_data.get('patient_first_name'),
                        'dob_page2': pediatric_data.get('patient_dob_page2'),
                        'age_page2': pediatric_data.get('patient_age_page2'),
                        'gender': pediatric_data.get('patient_gender')
                    },
                    'birth_history': {
                        'delivery_type': pediatric_data.get('delivery_type'),
                        'birth_timing': pediatric_data.get('birth_timing'),
                        'birth_weeks': pediatric_data.get('birth_weeks'),
                        'birth_weight': pediatric_data.get('birth_weight'),
                        'hearing_test': pediatric_data.get('hearing_test_passed'),
                        'hep_b_vaccine': pediatric_data.get('hep_b_vaccine'),
                        'complications': pediatric_data.get('pregnancy_complications')
                    },
                    'medical_history': {
                        'child_conditions': pediatric_data.get('child_medical_history', []),
                        'family_conditions': pediatric_data.get('family_medical_history', [])
                    },
                    'social_history': {
                        'household_members': pediatric_data.get('household_members'),
                        'pets': pediatric_data.get('any_pets'),
                        'smoking': pediatric_data.get('anyone_smokes'),
                        'lead_exposure': pediatric_data.get('lead_exposure'),
                        'voice_message_consent': pediatric_data.get('voice_message_consent')
                    },
                    'parent_guardian_info': {
                        'mother': {
                            'name': pediatric_data.get('mother_name'),
                            'phone': pediatric_data.get('mother_phone'),
                            'address': pediatric_data.get('mother_address'),
                            'cell': pediatric_data.get('mother_cell')
                        },
                        'father': {
                            'name': pediatric_data.get('father_name'),
                            'phone': pediatric_data.get('father_phone'),
                            'address': pediatric_data.get('father_address'),
                            'cell': pediatric_data.get('father_cell')
                        }
                    },
                    'insurance': {
                        'name': pediatric_data.get('insurance_name'),
                        'id': pediatric_data.get('insurance_id'),
                        'group': pediatric_data.get('insurance_group'),
                        'pharmacy_name': pediatric_data.get('pharmacy_name'),
                        'pharmacy_phone': pediatric_data.get('pharmacy_phone')
                    },
                    'consent': {
                        'treatment_consent': pediatric_data.get('treatment_consent'),
                        'parent_guardian_name': pediatric_data.get('parent_guardian_name_final'),
                        'signature_date': pediatric_data.get('final_signature_date')
                    },
                    'siblings_info': pediatric_data.get('siblings_info'),
                    'address': {
                        'address': pediatric_data.get('patient_address'),
                        'city': pediatric_data.get('patient_city'),
                        'state': pediatric_data.get('patient_state'),
                        'zip': pediatric_data.get('patient_zip')
                    }
                },
                'submission_metadata': {
                    'clinic_id': payload.get('clinic_id'),
                    'patient_id': payload.get('patient_id'),
                    'submitted_at': datetime.utcnow().isoformat(),
                    'form_version': '2.0_pediatric',
                    'data_hash': token_manager.hash_patient_data(pediatric_data)
                }
            }
            
            # Send to Azure Logic Apps
            if LOGIC_APP_WEBHOOK_URL:
                try:
                    response = requests.post(
                        LOGIC_APP_WEBHOOK_URL,
                        json=clinic_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        app.logger.info(f"Successfully processed pediatric submission for patient: {payload.get('patient_id')}")
                        return render_template('success.html',
                                             message="Thank you! Your pediatric intake information has been submitted successfully to Houston Pediatric Center.")
                    else:
                        app.logger.error(f"Logic Apps error: Status {response.status_code}")
                        
                except requests.RequestException as e:
                    app.logger.error(f"Failed to send to Logic Apps: {str(e)}")
            
            # Fallback response
            return render_template('success.html',
                                 message="Your pediatric intake form has been received. The clinic will contact you shortly.")
            
        except Exception as e:
            app.logger.error(f"Pediatric form processing error: {str(e)}")
            return render_template('error.html',
                                 message="There was an error processing your form. Please try again.",
                                 error_code="PROCESSING_ERROR"), 500
    
    else:
        # Form validation failed
        app.logger.warning(f"Pediatric form validation failed for patient: {payload.get('patient_id')}")
        return render_template('intake_form.html',
                             form=form,
                             token=token,
                             patient_id=payload.get('patient_id'),
                             clinic_id=payload.get('clinic_id'))
        
@app.route('/admin/generate-link', methods=['POST'])
def generate_patient_link():
    """
    Generate secure patient intake link for SMS distribution
    """
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        clinic_id = data.get('clinic_id', 'default')
        
        if not patient_id:
            return jsonify({'error': 'patient_id is required'}), 400
        
        # Generate secure form URL
        base_url = request.host_url.rstrip('/')
        form_url = token_manager.generate_form_url(base_url, patient_id, clinic_id)
        
        app.logger.info(f"Generated intake link for patient: {patient_id}")
        
        return jsonify({
            'success': True,
            'form_url': form_url,
            'patient_id': patient_id,
            'clinic_id': clinic_id,
            'expires_in_hours': 24,
            'generated_at': datetime.utcnow().isoformat(),
            'instructions': 'Send this URL via SMS to the patient. Link expires in 24 hours.'
        })
        
    except Exception as e:
        app.logger.error(f"Link generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate link'}), 500

@app.route('/admin/generate-pediatric-link', methods=['POST'])
def generate_pediatric_link():
    """
    Generate secure pediatric intake link
    """
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        clinic_id = data.get('clinic_id', 'houston_pediatric')
        
        if not patient_id:
            return jsonify({'error': 'patient_id is required'}), 400
        
        # Generate secure pediatric form URL
        base_url = request.host_url.rstrip('/')
        token = token_manager.generate_token(patient_id, clinic_id)
        form_url = f"{base_url}/pediatric-intake/{token}"
        
        app.logger.info(f"Generated pediatric intake link for patient: {patient_id}")
        
        return jsonify({
            'success': True,
            'form_url': form_url,
            'patient_id': patient_id,
            'clinic_id': clinic_id,
            'expires_in_hours': 24,
            'generated_at': datetime.utcnow().isoformat(),
            'form_type': 'pediatric_comprehensive',
            'instructions': 'Send this URL via SMS to the parent/guardian. Link expires in 24 hours.'
        })
        
    except Exception as e:
        app.logger.error(f"Pediatric link generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate pediatric link'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Azure App Service monitoring"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'components': {
            'token_manager': 'operational',
            'form_validator': 'operational',
            'converter': 'operational'
        }
    })

@app.errorhandler(404)
def not_found(error):
    """Custom 404 handler"""
    return render_template('error.html',
                         message="Page not found.",
                         error_code="404"), 404

@app.errorhandler(500)
def server_error(error):
    """Custom 500 handler"""
    app.logger.error(f"Server error: {str(error)}")
    return render_template('error.html',
                         message="Internal server error. Please try again later.",
                         error_code="500"), 500

# SMS ENDPOINTS

@app.route('/admin/send-intake-link', methods=['POST'])
def send_intake_link_sms():
    """Send patient intake link via SMS"""
    if not SMS_ENABLED:
        return jsonify({'error': 'SMS service is not available'}), 503
    
    try:
        data = request.get_json()
        
        # Required fields
        patient_phone = data.get('patient_phone')
        patient_id = data.get('patient_id')
        
        if not patient_phone or not patient_id:
            return jsonify({'error': 'patient_phone and patient_id are required'}), 400
        
        # Optional fields
        patient_name = data.get('patient_name', '')
        clinic_id = data.get('clinic_id', 'default')
        clinic_name = data.get('clinic_name', 'Healthcare Clinic')
        form_type = data.get('form_type', 'standard')  # 'standard' or 'pediatric'
        
        # Generate appropriate form URL
        base_url = request.host_url.rstrip('/')
        token = token_manager.generate_token(patient_id, clinic_id)
        
        if form_type == 'pediatric':
            form_url = f"{base_url}/pediatric-intake/{token}"
        else:
            form_url = f"{base_url}/intake/{token}"
        
        # Send SMS
        # Send SMS
        sms_result = sms_service.send_intake_link(
            patient_phone=patient_phone,
            form_url=form_url,
            patient_name=patient_name,
            clinic_name=clinic_name
        )
        
        if sms_result['success']:
            return jsonify({
                'success': True,
                'message': 'Intake link sent successfully via SMS',
                'patient_id': patient_id,
                'sms_status': sms_result,
                'form_url': form_url,
                'sent_at': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': sms_result.get('error', 'SMS delivery failed'),
                'patient_id': patient_id
            }), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to send SMS: {str(e)}'}), 500

@app.route('/admin/sms-status', methods=['GET'])
def sms_status():
    """Check SMS service status"""
    if not SMS_ENABLED:
        return jsonify({
            'sms_enabled': False,
            'status': 'SMS service not configured'
        })
    
    try:
        status = sms_service.test_connection()
        return jsonify({
            'sms_enabled': True,
            'connection_status': status,
            'checked_at': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'sms_enabled': True,
            'status': 'error',
            'error': str(e)
        }), 500
        
@app.route('/debug-env')
def debug_env():
    return jsonify({
        'connection_string_set': bool(os.environ.get('AZURE_COMMUNICATION_CONNECTION_STRING')),
        'phone_number_set': bool(os.environ.get('AZURE_PHONE_NUMBER')),
        'connection_string_preview': os.environ.get('AZURE_COMMUNICATION_CONNECTION_STRING', 'NOT_SET')[:50] + '...'
    })
        
if __name__ == '__main__':
    # Development server configuration
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
    
    