from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from functools import wraps
import csv, os, json
from io import StringIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_onco_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///onco_records.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
RestrictedRoles = ['Admin', 'Physician']

def save_investigation_file(file_obj, submodule, test_name, date_str, reg_no):
    if file_obj and file_obj.filename:
        ext = os.path.splitext(file_obj.filename)[1]
        try: fmt_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d%b%y')
        except: fmt_date = datetime.now().strftime('%d%b%y')
        safe_test = "".join([c if c.isalnum() else "_" for c in test_name]).strip("_") or "Test"
        safe_filename = secure_filename(f"{submodule}_{safe_test}_{fmt_date}_{reg_no}{ext}")
        file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_filename))
        return safe_filename
    return ""

# ==========================================
# DATABASE MODELS (Patient is safely at the bottom!)
# ==========================================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    salutation, first_name, middle_name, last_name = db.Column(db.String(10)), db.Column(db.String(50), nullable=False), db.Column(db.String(50)), db.Column(db.String(50), nullable=False)
    role, mobile_number, email, username = db.Column(db.String(20), nullable=False), db.Column(db.String(15), unique=True, nullable=False), db.Column(db.String(120), unique=True, nullable=False), db.Column(db.String(50), unique=True, nullable=False)
    password_hash, is_approved, created_on = db.Column(db.String(256), nullable=False), db.Column(db.Boolean, default=False), db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class MedicalHistory(db.Model):
    id, patient_id = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False, unique=True)
    
    # Toggle flags for each section
    has_addiction, has_allergy = db.Column(db.String(5), default='No'), db.Column(db.String(5), default='No')
    has_family_history, has_past_medical, has_past_surgical = db.Column(db.String(5), default='No'), db.Column(db.String(5), default='No'), db.Column(db.String(5), default='No')
    
    # NEW: Text columns to store the multi-row tabular data as JSON arrays
    addiction_data, allergy_data = db.Column(db.Text), db.Column(db.Text)
    family_data, medical_data, surgical_data = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text)
    
    # Reproductive & Social History
    marital_status, has_children = db.Column(db.String(20)), db.Column(db.String(5), default='No')
    
    # NEW: Female-specific reproductive fields
    menopausal_status, lmp_date = db.Column(db.String(50)), db.Column(db.String(20))
    menstrual_history, reproductive_comment = db.Column(db.Text), db.Column(db.Text)
    
    updated_on = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DiseaseProgression(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    disease_diagnosis = db.Column(db.Integer, db.ForeignKey('disease_diagnosis.id'))
    date = db.Column(db.String(20))
    progression_type = db.Column(db.String(100))
    diagnosed_by = db.Column(db.String(100))
    radiological_scan = db.Column(db.String(200))
    treatment_line = db.Column(db.String(100))
    comment = db.Column(db.String(500))

class SurvivalFollowUp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    disease_diagnosis = db.Column(db.Integer, db.ForeignKey('disease_diagnosis.id'))
    follow_up_date = db.Column(db.String(20))
    status = db.Column(db.String(50))
    death_date = db.Column(db.String(20))
    death_reason = db.Column(db.String(200))
    
class OpdConsultation(db.Model):
    id, patient_id, visit_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    temperature, temp_unit, pulse, bp, respiratory_rate, ecog = db.Column(db.String(10)), db.Column(db.String(5), default='°C'), db.Column(db.String(10)), db.Column(db.String(20)), db.Column(db.String(10)), db.Column(db.String(5))
    height, weight, bsa = db.Column(db.Float), db.Column(db.Float), db.Column(db.Float)
    chief_complaints, physical_exam, treatment_plan, investigations = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text), db.Column(db.Text)
    provisional_diagnosis, primary_diagnosis, next_visit_date = db.Column(db.String(255)), db.Column(db.String(255)), db.Column(db.Date)
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class PathologyRecord(db.Model):
    id, patient_id, record_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    cytology_data, histopathology_data, biomarker_data = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text)
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class RadiologyRecord(db.Model):
    id, patient_id, record_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    radiology_data, created_by, created_on = db.Column(db.Text), db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class BiochemistryRecord(db.Model):
    id, patient_id, record_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    biochemistry_data, created_by, created_on = db.Column(db.Text), db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class MiscellaneousRecord(db.Model):
    id, patient_id, record_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    miscellaneous_data, created_by, created_on = db.Column(db.Text), db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class DiseaseDiagnosis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    # Convert core diagnosis to JSON text to allow multiple rows
    date_of_diagnosis = db.Column(db.Date, nullable=False, default=date.today)
    primary_site = db.Column(db.String(100))
    diagnosis_description = db.Column(db.Text)
    risk_stratification = db.Column(db.String(20))
    core_diagnosis_data = db.Column(db.Text) 
    metastasis = db.Column(db.String(10), default='Absent')
    metastasis_organs = db.Column(db.Text) 
    tumour_size_data = db.Column(db.Text)
    lymph_node_data = db.Column(db.Text)
    staging_data = db.Column(db.Text) 
    progression_data = db.Column(db.Text) # Storing as JSON
    survival_data = db.Column(db.Text)    # Storing as JSON
    created_by = db.Column(db.String(50))
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

class ChemoProtocol(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name, intent, num_cycles, days_between_cycles = db.Column(db.String(150), nullable=False), db.Column(db.String(50)), db.Column(db.Integer), db.Column(db.Integer)
    prerequisites, assign_days, edu_material = db.Column(db.Text), db.Column(db.Text), db.Column(db.String(255))
    discharge_instructions, take_home_meds = db.Column(db.Text), db.Column(db.Text)
    cycle_notes, day_drugs = db.Column(db.Text), db.Column(db.Text)
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class PatientProtocol(db.Model):
    id, patient_id, protocol_id = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Integer, db.ForeignKey('chemo_protocol.id'), nullable=False)
    start_date, status = db.Column(db.Date, nullable=False, default=date.today), db.Column(db.String(20), default="Active")
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)
    protocol = db.relationship('ChemoProtocol')
    records = db.relationship('DayCareRecord', backref='patient_protocol', lazy=True, order_by="DayCareRecord.cycle_number.asc(), DayCareRecord.day_number.asc()")

class DayCareRecord(db.Model):
    id, patient_id, patient_protocol_id = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Integer, db.ForeignKey('patient_protocol.id'), nullable=False)
    cycle_number, day_number = db.Column(db.Integer, nullable=False), db.Column(db.Integer, nullable=False)
    administered_at, planned_date, actual_date = db.Column(db.String(100), default='BB Precision Oncocare Centre'), db.Column(db.Date), db.Column(db.Date)
    is_delayed, delay_reason = db.Column(db.String(5)), db.Column(db.String(255))
    fitness_confirmed, consent_obtained = db.Column(db.String(5)), db.Column(db.String(5))
    weight, bsa = db.Column(db.Float), db.Column(db.Float)
    drug_plan_data, admin_data = db.Column(db.Text), db.Column(db.Text)
    post_vitals, post_exam, post_toxicity = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text)
    discharge_notes, discharge_meds = db.Column(db.Text), db.Column(db.Text)
    is_finalized, created_by, created_on = db.Column(db.Boolean, default=False), db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class TreatmentRecord(db.Model):
    id, patient_id, record_date = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    chemo_data, immuno_data, targeted_data, hormonal_data, other_med_data = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text), db.Column(db.Text), db.Column(db.Text)
    surgery_data, radiotherapy_data = db.Column(db.Text), db.Column(db.Text)
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class TumourBoardRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    board_date = db.Column(db.Date, nullable=False, default=date.today)
    members_data = db.Column(db.Text)
    discussion = db.Column(db.Text)
    next_steps = db.Column(db.Text)
    created_by = db.Column(db.String(50))
    created_on = db.Column(db.DateTime, default=datetime.utcnow)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    physician_name = db.Column(db.String(100))
    visit_date = db.Column(db.String(100))
    subtotal, discount_total, tax_total, grand_total = db.Column(db.Float, default=0.0), db.Column(db.Float, default=0.0), db.Column(db.Float, default=0.0), db.Column(db.Float, default=0.0)
    amount_paid = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Unpaid') # Unpaid, Partial, Paid
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('InvoiceItem', backref='invoice', cascade="all, delete-orphan", lazy=True)
    payments = db.relationship('Payment', backref='invoice', cascade="all, delete-orphan", lazy=True)

class InvoiceItem(db.Model):
    id, invoice_id = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    category, description = db.Column(db.String(100)), db.Column(db.String(255))
    quantity, unit_price = db.Column(db.Integer, default=1), db.Column(db.Float, default=0.0)
    discount, tax, total_amount = db.Column(db.Float, default=0.0), db.Column(db.Float, default=0.0), db.Column(db.Float, default=0.0)

class Payment(db.Model):
    id, invoice_id = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    payment_date, amount = db.Column(db.Date, nullable=False, default=date.today), db.Column(db.Float, nullable=False)
    mode, transaction_id = db.Column(db.String(50)), db.Column(db.String(100))
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    physician_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='Pending Confirmation') # Confirmed, Pending Confirmation, Cancelled, Completed
    notes = db.Column(db.Text)
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name, middle_name, last_name = db.Column(db.String(50), nullable=False), db.Column(db.String(50)), db.Column(db.String(50), nullable=False)
    dob, gender, blood_group, religion, education = db.Column(db.Date, nullable=False), db.Column(db.String(10), nullable=False), db.Column(db.String(5)), db.Column(db.String(50)), db.Column(db.String(50))
    mobile_number, alt_mobile_number, email = db.Column(db.String(15), nullable=False), db.Column(db.String(15)), db.Column(db.String(120))
    id_proof, id_proof_number = db.Column(db.String(50)), db.Column(db.String(50))
    emg_contact_name, emg_contact_mobile, emg_contact_email = db.Column(db.String(100)), db.Column(db.String(15)), db.Column(db.String(120))
    address_house, address_society, address_area, address_city, address_state, address_country, address_pincode = db.Column(db.String(100)), db.Column(db.String(100)), db.Column(db.String(100)), db.Column(db.String(50)), db.Column(db.String(50)), db.Column(db.String(50)), db.Column(db.String(20))
    ref_physician_name, ref_physician_contact = db.Column(db.String(100)), db.Column(db.String(15))
    primary_diagnosis, created_on = db.Column(db.String(200), default="Pending Evaluation"), db.Column(db.DateTime, default=datetime.utcnow)
    
    medical_history = db.relationship('MedicalHistory', backref='patient', uselist=False)
    opd_visits = db.relationship('OpdConsultation', backref='patient', lazy=True, order_by="OpdConsultation.visit_date.desc()")
    pathology_records = db.relationship('PathologyRecord', backref='patient', lazy=True, order_by="PathologyRecord.record_date.desc()")
    radiology_records = db.relationship('RadiologyRecord', backref='patient', lazy=True, order_by="RadiologyRecord.record_date.desc()")
    biochemistry_records = db.relationship('BiochemistryRecord', backref='patient', lazy=True, order_by="BiochemistryRecord.record_date.desc()")
    miscellaneous_records = db.relationship('MiscellaneousRecord', backref='patient', lazy=True, order_by="MiscellaneousRecord.record_date.desc()")
    disease_records = db.relationship('DiseaseDiagnosis', backref='patient', lazy=True, order_by="DiseaseDiagnosis.date_of_diagnosis.desc()")
    day_care_protocols = db.relationship('PatientProtocol', backref='patient', lazy=True, order_by="PatientProtocol.start_date.desc()")
    treatment_records = db.relationship('TreatmentRecord', backref='patient', lazy=True, order_by="TreatmentRecord.record_date.desc()")
    tumour_board_records = db.relationship('TumourBoardRecord', backref='patient', lazy=True, order_by="TumourBoardRecord.board_date.desc()")
    invoices = db.relationship('Invoice', backref='patient', lazy=True, order_by="Invoice.invoice_date.desc()")
    appointments = db.relationship('Appointment', backref='patient', lazy=True, order_by="Appointment.appointment_date.desc(), Appointment.appointment_time.desc()")

    @property
    def age(self):
        today = date.today()
        return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))

# ==========================================
# AUTHENTICATION & CORE ROUTES
# ==========================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index(): return redirect(url_for('patient_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            # Check if the user account is Active (Approved)
            if not user.is_approved:
                flash("Your account has been deactivated. Please contact the Administrator.")
                return redirect(url_for('login'))
            if not user.is_approved: return redirect(url_for('login'))
            session['user_id'], session['username'], session['role'] = user.id, user.username, user.role
            return redirect(url_for('patient_dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = User(salutation=request.form['salutation'], first_name=request.form['first_name'], last_name=request.form['last_name'], role=request.form['role'], mobile_number=request.form['mobile_number'], email=request.form['email'], username=request.form['username'])
        new_user.set_password(request.form['password'])
        db.session.add(new_user); db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    q = request.args.get('search', '')
    pts = Patient.query.filter(db.or_(Patient.first_name.ilike(f'%{q}%'), Patient.registration_number.ilike(f'%{q}%'))).order_by(Patient.created_on.desc()).all() if q else Patient.query.order_by(Patient.created_on.desc()).all()
    return render_template('patient_dashboard.html', patients=pts, search_query=q, user=session)

@app.route('/patient_registration', methods=['GET', 'POST'])
@login_required
def patient_registration():
    if request.method == 'POST':
        last_patient = Patient.query.filter(Patient.registration_number.like(f"{datetime.now().strftime('%Y%m')}-%")).order_by(Patient.id.desc()).first()
        reg_number = f"{datetime.now().strftime('%Y%m')}-{int(last_patient.registration_number.split('-')[1]) + 1 if last_patient else 1:04d}"
        
        new_patient = Patient(
            registration_number=reg_number, 
            first_name=request.form.get('first_name'), 
            middle_name=request.form.get('middle_name'),
            last_name=request.form.get('last_name'), 
            dob=datetime.strptime(request.form['dob'], '%Y-%m-%d').date(), 
            gender=request.form.get('gender'), 
            blood_group=request.form.get('blood_group'),
            religion=request.form.get('religion'),
            education=request.form.get('education'),
            mobile_number=request.form.get('mobile_number'),
            alt_mobile_number=request.form.get('alt_mobile_number'),
            email=request.form.get('email'),
            id_proof=request.form.get('id_proof'),
            id_proof_number=request.form.get('id_proof_number'),
            emg_contact_name=request.form.get('emg_contact_name'),
            emg_contact_mobile=request.form.get('emg_contact_mobile'),
            emg_contact_email=request.form.get('emg_contact_email'),
            address_house=request.form.get('address_house'),
            address_society=request.form.get('address_society'),
            address_area=request.form.get('address_area'),
            address_city=request.form.get('address_city'),
            address_state=request.form.get('address_state'),
            address_country=request.form.get('address_country', 'India'),
            address_pincode=request.form.get('address_pincode'),
            ref_physician_name=request.form.get('ref_physician_name'),
            ref_physician_contact=request.form.get('ref_physician_contact')
        )
        db.session.add(new_patient)
        db.session.commit()
        flash(f"Patient {new_patient.first_name} registered successfully with Reg No: {reg_number}")
        return redirect(url_for('patient_dashboard'))
    return render_template('patient_registration.html', user=session)

@app.route('/patient/<int:patient_id>/overview')
@login_required
def patient_overview(patient_id):
    patient = Patient.query.get_or_404(patient_id)

    # 1. Medical History (Only 'Yes' conditions)
    med_hist = MedicalHistory.query.filter_by(patient_id=patient_id).first()
    active_history = {}
    if med_hist:
        if med_hist.has_addiction == 'Yes': active_history['Addiction'] = f"{med_hist.addiction_type} ({med_hist.addiction_years or '?'} yrs)"
        if med_hist.has_allergy == 'Yes': active_history['Allergies'] = med_hist.allergy_details
        if med_hist.has_family_history == 'Yes': active_history['Family History'] = f"{med_hist.family_condition} ({med_hist.family_member})"
        if med_hist.has_past_medical == 'Yes': active_history['Co-morbidities'] = med_hist.comorbidity
        if med_hist.has_past_surgical == 'Yes': active_history['Past Surgeries'] = f"{med_hist.surgery_name} ({med_hist.surgery_year or '?'})"

    # 2. OPD Complaints
    opd_visits = OpdConsultation.query.filter_by(patient_id=patient_id).order_by(OpdConsultation.visit_date.desc()).all()
    complaints = []
    for opd in opd_visits:
        if opd.chief_complaints:
            for c in json.loads(opd.chief_complaints):
                complaints.append({'date': opd.visit_date, 'complaint': c.get('complaint'), 'frequency': c.get('frequency'), 'start': c.get('start'), 'end': c.get('end')})

    # 3. Pathology
    path_records = PathologyRecord.query.filter_by(patient_id=patient_id).order_by(PathologyRecord.record_date.desc()).all()
    cyto, histo, bio = [], [], []
    for pr in path_records:
        if pr.cytology_data: cyto.extend(json.loads(pr.cytology_data))
        if pr.histopathology_data: histo.extend(json.loads(pr.histopathology_data))
        if pr.biomarker_data: bio.extend(json.loads(pr.biomarker_data))

    # 4. Radiology
    rad_records = RadiologyRecord.query.filter_by(patient_id=patient_id).order_by(RadiologyRecord.record_date.desc()).all()
    radiology = []
    for rr in rad_records:
        if rr.radiology_data: radiology.extend(json.loads(rr.radiology_data))

    # 5. Disease & Diagnosis
    disease = DiseaseDiagnosis.query.filter_by(patient_id=patient_id).order_by(DiseaseDiagnosis.date_of_diagnosis.desc()).first()
    disease_data = {}
    if disease:
        disease_data = {
            'date': disease.date_of_diagnosis, 'site': disease.primary_site, 'desc': disease.diagnosis_description,
            'meta_status': disease.metastasis, 'meta_organs': json.loads(disease.metastasis_organs) if disease.metastasis_organs else [],
            'staging': json.loads(disease.staging_data) if disease.staging_data else []
        }

    # 6. Treatments
    treatments = TreatmentRecord.query.filter_by(patient_id=patient_id).order_by(TreatmentRecord.record_date.desc()).all()
    med_therapies, surgeries, rt_list = [], [], []
    for tr in treatments:
        # Flatten medical therapies into one master list for the UI
        for t_type, data_col in [('Chemo', tr.chemo_data), ('Immuno', tr.immuno_data), ('Targeted', tr.targeted_data), ('Hormonal', tr.hormonal_data), ('Other', tr.other_med_data)]:
            if data_col:
                for item in json.loads(data_col):
                    item['category'] = t_type
                    med_therapies.append(item)
        if tr.surgery_data: surgeries.extend(json.loads(tr.surgery_data))
        if tr.radiotherapy_data: rt_list.extend(json.loads(tr.radiotherapy_data))

    return render_template('overview_dashboard.html', patient=patient, active_history=active_history, complaints=complaints, cyto=cyto, histo=histo, bio=bio, radiology=radiology, disease=disease_data, med_therapies=med_therapies, surgeries=surgeries, rt_list=rt_list, user=session)

# ==========================================
# DISEASE, HISTORY & OPD
# ==========================================
import json
from datetime import datetime

@app.route('/patient/<int:patient_id>/disease_diagnosis')
@login_required
def disease_diagnosis(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = []
    
    for r in patient.disease_records:
        # Fetch related relational records
        progressions = DiseaseProgression.query.filter_by(disease_diagnosis=patient.id).order_by(DiseaseProgression.date).all()
        survivals = SurvivalFollowUp.query.filter_by(disease_diagnosis=patient.id).all()
        
        prog_data = [{'date': p.date, 'line': getattr(p, 'treatment_line', ''), 'protocol': getattr(p, 'protocol', ''), 'type': p.progression_type, 'diagnosed_by': p.diagnosed_by, 'radiological_scan': p.radiological_scan, 'comment': p.comment} for p in progressions]
        surv_data = [{'date': s.follow_up_date, 'status': s.status, 'death_date': s.death_date, 'death_reason': s.death_reason} for s in survivals]
        
        # Core Diagnosis Logic (Checks for new JSON table, falls back to old columns if empty)
        core_data = getattr(r, 'core_diagnosis_data', None)
        if core_data:
            core_list = json.loads(core_data)
        else:
            core_list = [{"date": str(r.date_of_diagnosis), "site": r.primary_site, "desc": r.diagnosis_description, "risk": r.risk_stratification}]

        # ==========================================
        # Calculate OS and PFS for Dashboard
        # ==========================================
        outcomes = []
        death_date_str = next((s['death_date'] for s in surv_data if s['status'] == 'Died' and s['death_date']), None)
        death_date = datetime.strptime(death_date_str, '%Y-%m-%d') if death_date_str else None
        
        for p in prog_data:
            start_date_str = p['date']
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    # Find the next progression date after this one to mark the end of PFS
                    next_prog_str = next((nxt['date'] for nxt in prog_data if nxt['date'] and nxt['date'] > start_date_str), None)
                    
                    if next_prog_str:
                        end_pfs_date = datetime.strptime(next_prog_str, '%Y-%m-%d')
                    else:
                        end_pfs_date = death_date
                    
                    pfs_months = round((end_pfs_date - start_date).days / 30.44, 1) if end_pfs_date else "Ongoing"
                    os_months = round((death_date - start_date).days / 30.44, 1) if death_date else "Alive"
                    
                    outcomes.append({
                        'line': p['line'],
                        'protocol': p['protocol'],
                        'pfs': pfs_months,
                        'os': os_months
                    })
                except ValueError:
                    pass # Skip calculations if dates are missing or improperly formatted
        
        records.append({
            'id': r.id, 
            'core_diagnosis': core_list,
            'metastasis': r.metastasis, 
            'organs': json.loads(r.metastasis_organs) if r.metastasis_organs else [], 
            'tumour': json.loads(r.tumour_size_data) if r.tumour_size_data else [], 
            'lymph': json.loads(r.lymph_node_data) if r.lymph_node_data else [], 
            'staging': json.loads(r.staging_data) if r.staging_data else [], 
            'progression': prog_data,
            'survival': surv_data,
            'outcomes': outcomes,
            'created_by': r.created_by
        })
        
    return render_template('disease_dashboard.html', patient=patient, records=records, user=session)

@app.route('/patient/<int:patient_id>/disease_diagnosis/new', methods=['GET', 'POST'])
@login_required
def disease_diagnosis_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Fetch treatments to populate the Protocol Dropdown in Disease Progression
    treatments = getattr(patient, 'patient_protocols', []) 
    patient_protocols = [t.protocol.name for t in treatments if hasattr(t, 'protocol')]

    if request.method == 'POST':
        # 1. Core Diagnosis Extraction (SAFE)
        c_dates = request.form.getlist('c_date[]')
        c_sites = request.form.getlist('c_site[]')
        c_descs = request.form.getlist('c_desc[]')
        c_risks = request.form.getlist('c_risk[]')
        
        core_list = []
        for i in range(len(c_sites)):
            if c_sites[i].strip():
                core_list.append({
                    "date": c_dates[i] if i < len(c_dates) else '', 
                    "site": c_sites[i], 
                    "desc": c_descs[i] if i < len(c_descs) else '', 
                    "risk": c_risks[i] if i < len(c_risks) else ''
                })

        # 2. Metastasis
        meta_status = request.form.get('metastasis')
        meta_organs = request.form.getlist('meta_organs[]') if meta_status == 'Present' else []
        
        # 3. Tumour & Lymph (SAFE)
        tumour_list, lymph_list, staging_list = [], [], []
        ts_lens, ts_wids, ts_deps, ts_ts, ts_descs = request.form.getlist('ts_len[]'), request.form.getlist('ts_wid[]'), request.form.getlist('ts_dep[]'), request.form.getlist('ts_t[]'), request.form.getlist('ts_desc[]')
        for i in range(len(ts_lens)):
            if ts_lens[i].strip() or (i < len(ts_wids) and ts_wids[i].strip()): 
                tumour_list.append({
                    "length": ts_lens[i], 
                    "width": ts_wids[i] if i < len(ts_wids) else '', 
                    "depth": ts_deps[i] if i < len(ts_deps) else '', 
                    "t_stage": ts_ts[i] if i < len(ts_ts) else '', 
                    "desc": ts_descs[i] if i < len(ts_descs) else ''
                })
                
        ln_grps, ln_lens, ln_wids, ln_deps, ln_ns, ln_descs = request.form.getlist('ln_grp[]'), request.form.getlist('ln_len[]'), request.form.getlist('ln_wid[]'), request.form.getlist('ln_dep[]'), request.form.getlist('ln_n[]'), request.form.getlist('ln_desc[]')
        for i in range(len(ln_grps)):
            if ln_grps[i].strip() or (i < len(ln_ns) and ln_ns[i].strip()): 
                lymph_list.append({
                    "group": ln_grps[i], 
                    "length": ln_lens[i] if i < len(ln_lens) else '', 
                    "width": ln_wids[i] if i < len(ln_wids) else '', 
                    "depth": ln_deps[i] if i < len(ln_deps) else '', 
                    "n_stage": ln_ns[i] if i < len(ln_ns) else '', 
                    "desc": ln_descs[i] if i < len(ln_descs) else ''
                })
        
        # 4. Staging (SAFE)
        st_dates, st_types, st_ts, st_ns, st_ms, st_ds, st_stages, st_comms = request.form.getlist('st_date[]'), request.form.getlist('st_type[]'), request.form.getlist('st_t[]'), request.form.getlist('st_n[]'), request.form.getlist('st_m[]'), request.form.getlist('st_d[]'), request.form.getlist('st_stage[]'), request.form.getlist('st_comm[]')
        for i in range(len(st_dates)):
            if st_dates[i].strip() or (i < len(st_stages) and st_stages[i].strip()): 
                staging_list.append({
                    "date": st_dates[i], 
                    "type": st_types[i] if i < len(st_types) else '', 
                    "t": st_ts[i] if i < len(st_ts) else '', 
                    "n": st_ns[i] if i < len(st_ns) else '', 
                    "m": st_ms[i] if i < len(st_ms) else '', 
                    "d": st_ds[i] if i < len(st_ds) else '', 
                    "stage": st_stages[i] if i < len(st_stages) else '', 
                    "comment": st_comms[i] if i < len(st_comms) else ''
                })

        # Check if record exists for Editing, otherwise create new
        record = DiseaseDiagnosis.query.filter_by(patient_id=patient.id).first()
        if not record:
            record = DiseaseDiagnosis(patient_id=patient.id)
            db.session.add(record)

        # Apply basic fields (fallback for older structure)
        if len(c_dates) > 0 and c_dates[0]:
            try:
                record.date_of_diagnosis = datetime.strptime(c_dates[0], '%Y-%m-%d').date()
            except ValueError:
                pass
        record.primary_site = c_sites[0] if len(c_sites) > 0 else ''
        record.diagnosis_description = c_descs[0] if len(c_descs) > 0 else ''
        record.risk_stratification = c_risks[0] if len(c_risks) > 0 else ''
        
        # Apply JSON fields
        record.core_diagnosis_data = json.dumps(core_list)
        record.metastasis = meta_status
        record.metastasis_organs = json.dumps(meta_organs)
        record.tumour_size_data = json.dumps(tumour_list)
        record.lymph_node_data = json.dumps(lymph_list)
        record.staging_data = json.dumps(staging_list)
        record.created_by = session.get('username')

        # ==========================================
        # Capture Disease Progression Arrays
        # ==========================================
        DiseaseProgression.query.filter_by(disease_diagnosis=patient.id).delete()
        
        dp_dates = request.form.getlist('dp_date[]')
        dp_types = request.form.getlist('dp_type[]')
        dp_diags = request.form.getlist('dp_diagnosed_by[]')
        dp_rads = request.form.getlist('dp_rad_scan[]')
        dp_lines = request.form.getlist('dp_line[]')
        dp_protos = request.form.getlist('dp_protocol[]')
        dp_comms = request.form.getlist('dp_comm[]')

        for i in range(len(dp_dates)):
            if dp_dates[i].strip() or (i < len(dp_types) and dp_types[i].strip()):
                new_progression = DiseaseProgression(
                    disease_diagnosis=patient.id,
                    date=dp_dates[i],
                    progression_type=dp_types[i] if i < len(dp_types) else '',
                    diagnosed_by=dp_diags[i] if i < len(dp_diags) else '',
                    radiological_scan=dp_rads[i] if i < len(dp_rads) and i < len(dp_diags) and dp_diags[i] == 'Radiological scan' else None,
                    treatment_line=dp_lines[i] if i < len(dp_lines) else '',
                    protocol=dp_protos[i] if i < len(dp_protos) else '', 
                    comment=dp_comms[i] if i < len(dp_comms) else ''
                )
                db.session.add(new_progression)

        # ==========================================
        # Capture Survival Follow-up Arrays
        # ==========================================
        SurvivalFollowUp.query.filter_by(disease_diagnosis=patient.id).delete()
        
        sf_dates = request.form.getlist('sf_date[]')
        sf_statuses = request.form.getlist('sf_status[]')
        sf_death_dates = request.form.getlist('sf_death_date[]')
        sf_death_reasons = request.form.getlist('sf_death_reason[]')

        for i in range(len(sf_dates)):
            if sf_dates[i].strip() or (i < len(sf_statuses) and sf_statuses[i].strip()):
                is_dead = (i < len(sf_statuses) and sf_statuses[i] == 'Died')
                new_survival = SurvivalFollowUp(
                    disease_diagnosis=patient.id,
                    follow_up_date=sf_dates[i],
                    status=sf_statuses[i] if i < len(sf_statuses) else '',
                    death_date=sf_death_dates[i] if is_dead and i < len(sf_death_dates) else None,
                    death_reason=sf_death_reasons[i] if is_dead and i < len(sf_death_reasons) else None
                )
                db.session.add(new_survival)

        db.session.commit()
        flash('Diagnosis record saved successfully!')
        return redirect(url_for('disease_diagnosis', patient_id=patient.id))

    # --- GET LOGIC (Pre-fill Data for form) ---
    record = DiseaseDiagnosis.query.filter_by(patient_id=patient.id).first()
    parsed_record = None
    if record:
        progressions = DiseaseProgression.query.filter_by(disease_diagnosis=patient.id).all()
        survivals = SurvivalFollowUp.query.filter_by(disease_diagnosis=patient.id).all()
        
        core_data = getattr(record, 'core_diagnosis_data', None)
        if core_data:
            core_list = json.loads(core_data)
        else:
            core_list = [{"date": str(record.date_of_diagnosis), "site": record.primary_site, "desc": record.diagnosis_description, "risk": record.risk_stratification}]

        parsed_record = {
            'core_diagnosis': core_list,
            'metastasis': record.metastasis,
            'organs': json.loads(record.metastasis_organs) if record.metastasis_organs else [],
            'tumour': json.loads(record.tumour_size_data) if record.tumour_size_data else [],
            'lymph': json.loads(record.lymph_node_data) if record.lymph_node_data else [],
            'staging': json.loads(record.staging_data) if record.staging_data else [],
            'progression': [{'date': p.date, 'line': getattr(p, 'treatment_line', ''), 'protocol': getattr(p, 'protocol', ''), 'type': p.progression_type, 'diagnosed_by': p.diagnosed_by, 'radiological_scan': p.radiological_scan, 'comment': p.comment} for p in progressions],
            'survival': [{'date': s.follow_up_date, 'status': s.status, 'death_date': s.death_date, 'death_reason': s.death_reason} for s in survivals]
        }

    path_records = [{'date': pr.record_date, 'cyto': json.loads(pr.cytology_data) if pr.cytology_data else [], 'histo': json.loads(pr.histopathology_data) if pr.histopathology_data else [], 'bio': json.loads(pr.biomarker_data) if pr.biomarker_data else []} for pr in patient.pathology_records]
    rad_records = [{'date': rr.record_date, 'data': json.loads(rr.radiology_data) if rr.radiology_data else []} for rr in patient.radiology_records]
    
    return render_template('disease_form.html', patient=patient, record=parsed_record, path_records=path_records, rad_records=rad_records, patient_protocols=patient_protocols, user=session)

import json

@app.route('/patient/<int:patient_id>/medical_history', methods=['GET', 'POST'])
@login_required
def medical_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    history = MedicalHistory.query.filter_by(patient_id=patient.id).first()

    if request.method == 'POST':
        if not history:
            history = MedicalHistory(patient_id=patient.id)
            db.session.add(history)

        history.has_addiction = request.form.get('has_addiction')
        history.has_allergy = request.form.get('has_allergy')
        history.has_family_history = request.form.get('has_family_history')
        history.has_past_medical = request.form.get('has_past_medical')
        history.has_past_surgical = request.form.get('has_past_surgical')
        history.marital_status = request.form.get('marital_status')
        history.has_children = request.form.get('has_children')
        
        # Female Reproductive Fields
        history.menopausal_status = request.form.get('menopausal_status')
        history.lmp_date = request.form.get('lmp_date')
        history.menstrual_history = request.form.get('menstrual_history')
        history.reproductive_comment = request.form.get('reproductive_comment')

        # Extract Tables into JSON
        # 1. Addiction
        a_types, a_years, a_comms = request.form.getlist('add_type[]'), request.form.getlist('add_years[]'), request.form.getlist('add_comm[]')
        history.addiction_data = json.dumps([{"type": a_types[i], "years": a_years[i] if i < len(a_years) else '', "comment": a_comms[i] if i < len(a_comms) else ''} for i in range(len(a_types)) if a_types[i].strip()])

        # 2. Allergy
        al_types, al_years, al_comms = request.form.getlist('all_type[]'), request.form.getlist('all_years[]'), request.form.getlist('all_comm[]')
        history.allergy_data = json.dumps([{"type": al_types[i], "years": al_years[i] if i < len(al_years) else '', "comment": al_comms[i] if i < len(al_comms) else ''} for i in range(len(al_types)) if al_types[i].strip()])

        # 3. Family
        f_conds, f_mems, f_comms = request.form.getlist('fam_cond[]'), request.form.getlist('fam_mem[]'), request.form.getlist('fam_comm[]')
        history.family_data = json.dumps([{"condition": f_conds[i], "member": f_mems[i] if i < len(f_mems) else '', "comment": f_comms[i] if i < len(f_comms) else ''} for i in range(len(f_conds)) if f_conds[i].strip()])

        # 4. Medical
        m_conds, m_stats, m_drugs, m_comms = request.form.getlist('med_cond[]'), request.form.getlist('med_stat[]'), request.form.getlist('med_drugs[]'), request.form.getlist('med_comm[]')
        history.medical_data = json.dumps([{"condition": m_conds[i], "status": m_stats[i] if i < len(m_stats) else '', "drugs": m_drugs[i] if i < len(m_drugs) else '', "comment": m_comms[i] if i < len(m_comms) else ''} for i in range(len(m_conds)) if m_conds[i].strip()])

        # 5. Surgical
        s_names, s_years, s_inds, s_comms = request.form.getlist('surg_name[]'), request.form.getlist('surg_year[]'), request.form.getlist('surg_ind[]'), request.form.getlist('surg_comm[]')
        history.surgical_data = json.dumps([{"name": s_names[i], "year": s_years[i] if i < len(s_years) else '', "indication": s_inds[i] if i < len(s_inds) else '', "comment": s_comms[i] if i < len(s_comms) else ''} for i in range(len(s_names)) if s_names[i].strip()])

        db.session.commit()
        flash('Medical history saved successfully!')
        return redirect(url_for('medical_history', patient_id=patient.id))

    # Parse data for GET rendering
    record_data = None
    if history:
        record_data = {
            'addiction': json.loads(history.addiction_data) if getattr(history, 'addiction_data', None) else [],
            'allergy': json.loads(history.allergy_data) if getattr(history, 'allergy_data', None) else [],
            'family': json.loads(history.family_data) if getattr(history, 'family_data', None) else [],
            'medical': json.loads(history.medical_data) if getattr(history, 'medical_data', None) else [],
            'surgical': json.loads(history.surgical_data) if getattr(history, 'surgical_data', None) else []
        }

    return render_template('medical_history.html', patient=patient, history=history, record_data=record_data, user=session)

@app.route('/patient/<int:patient_id>/opd_consultations')
@login_required
def opd_consultations(patient_id): return render_template('opd_dashboard.html', patient=Patient.query.get_or_404(patient_id), visits=Patient.query.get_or_404(patient_id).opd_visits, user=session)

@app.route('/patient/<int:patient_id>/opd/new', methods=['GET', 'POST'])
@login_required
def opd_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        db.session.add(OpdConsultation(patient_id=patient.id, visit_date=datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date(), created_by=session.get('username')))
        db.session.commit()
        return redirect(url_for('opd_consultations', patient_id=patient.id))
    return render_template('opd_form.html', patient=patient, user=session)

# ==========================================
# INVESTIGATIONS
# ==========================================
@app.route('/patient/<int:patient_id>/investigations/pathology')
@login_required
def inv_pathology(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    parsed_records = [{'id': r.id, 'date': r.record_date, 'cytology': json.loads(r.cytology_data) if r.cytology_data else [], 'histopathology': json.loads(r.histopathology_data) if r.histopathology_data else [], 'biomarker': json.loads(r.biomarker_data) if r.biomarker_data else [], 'author': r.created_by} for r in patient.pathology_records]
    return render_template('inv_pathology_dashboard.html', patient=patient, records=parsed_records, user=session)

@app.route('/patient/<int:patient_id>/investigations/pathology/new', methods=['GET', 'POST'])
@login_required
def inv_pathology_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        reg_no = patient.registration_number; cyto_list, histo_list, bio_list = [], [], []
        c_dates, c_specs, c_reasons, c_micro, c_interp, c_comm = request.form.getlist('c_date[]'), request.form.getlist('c_specimen[]'), request.form.getlist('c_reason[]'), request.form.getlist('c_micro[]'), request.form.getlist('c_interp[]'), request.form.getlist('c_comm[]')
        for i in range(len(c_dates)):
            if c_dates[i].strip() or c_specs[i].strip(): cyto_list.append({"date": c_dates[i], "specimen": c_specs[i], "reason": c_reasons[i], "microscopic": c_micro[i], "interpretation": c_interp[i], "comment": c_comm[i], "file": save_investigation_file(request.files.get(f'c_file_{i}'), 'Cytology', c_specs[i], c_dates[i], reg_no)})
        h_dates, h_types, h_sites, h_stage, h_grade, h_interp, h_comm = request.form.getlist('h_date[]'), request.form.getlist('h_type[]'), request.form.getlist('h_site[]'), request.form.getlist('h_stage[]'), request.form.getlist('h_grade[]'), request.form.getlist('h_interp[]'), request.form.getlist('h_comm[]')
        for i in range(len(h_dates)):
            if h_dates[i].strip() or h_types[i].strip(): histo_list.append({"date": h_dates[i], "type": h_types[i], "site": h_sites[i], "staging": h_stage[i], "grading": h_grade[i], "interpretation": h_interp[i], "comment": h_comm[i], "file": save_investigation_file(request.files.get(f'h_file_{i}'), 'Histopathology', h_types[i], h_dates[i], reg_no)})
        b_dates, b_marks, b_stats, b_sub, b_vaf, b_comm = request.form.getlist('b_date[]'), request.form.getlist('b_marker[]'), request.form.getlist('b_status[]'), request.form.getlist('b_sub[]'), request.form.getlist('b_vaf[]'), request.form.getlist('b_comm[]')
        for i in range(len(b_dates)):
            if b_dates[i].strip() or b_marks[i].strip(): bio_list.append({"date": b_dates[i], "biomarker": b_marks[i], "status": b_stats[i], "sub_biomarker": b_sub[i], "vaf": b_vaf[i], "comment": b_comm[i], "file": save_investigation_file(request.files.get(f'b_file_{i}'), 'Biomarker', b_marks[i], b_dates[i], reg_no)})
        if cyto_list or histo_list or bio_list: db.session.add(PathologyRecord(patient_id=patient.id, cytology_data=json.dumps(cyto_list), histopathology_data=json.dumps(histo_list), biomarker_data=json.dumps(bio_list), created_by=session.get('username'))); db.session.commit()
        return redirect(url_for('inv_pathology', patient_id=patient.id))
    return render_template('inv_pathology_form.html', patient=patient, user=session)

import json

@app.route('/patient/<int:patient_id>/investigations/pathology/edit/<int:record_id>', methods=['GET', 'POST'])
@login_required
def inv_pathology_edit(patient_id, record_id):
    patient = Patient.query.get_or_404(patient_id)
    record = PathologyRecord.query.get_or_404(record_id)
    
    if request.method == 'POST':
        reg_no = patient.registration_number
        cyto_list, histo_list, bio_list = [], [], []
        
        # Load existing data so we can preserve old file paths if no new file is uploaded
        old_cyto = json.loads(record.cytology_data) if record.cytology_data else []
        old_histo = json.loads(record.histopathology_data) if record.histopathology_data else []
        old_bio = json.loads(record.biomarker_data) if record.biomarker_data else []

        # 1. Cytology Update
        c_dates, c_specs, c_reasons, c_micro, c_interp, c_comm = request.form.getlist('c_date[]'), request.form.getlist('c_specimen[]'), request.form.getlist('c_reason[]'), request.form.getlist('c_micro[]'), request.form.getlist('c_interp[]'), request.form.getlist('c_comm[]')
        for i in range(len(c_dates)):
            if c_dates[i].strip() or c_specs[i].strip():
                # Keep old file path by default, unless a new file is uploaded
                f_path = old_cyto[i].get('file') if i < len(old_cyto) else None
                file_obj = request.files.get(f'c_file_{i}')
                if file_obj and file_obj.filename != '':
                    f_path = save_investigation_file(file_obj, 'Cytology', c_specs[i], c_dates[i], reg_no)
                
                cyto_list.append({"date": c_dates[i], "specimen": c_specs[i], "reason": c_reasons[i], "microscopic": c_micro[i], "interpretation": c_interp[i], "comment": c_comm[i], "file": f_path})

        # 2. Histopathology Update
        h_dates, h_types, h_sites, h_stage, h_grade, h_interp, h_comm = request.form.getlist('h_date[]'), request.form.getlist('h_type[]'), request.form.getlist('h_site[]'), request.form.getlist('h_stage[]'), request.form.getlist('h_grade[]'), request.form.getlist('h_interp[]'), request.form.getlist('h_comm[]')
        for i in range(len(h_dates)):
            if h_dates[i].strip() or h_types[i].strip():
                f_path = old_histo[i].get('file') if i < len(old_histo) else None
                file_obj = request.files.get(f'h_file_{i}')
                if file_obj and file_obj.filename != '':
                    f_path = save_investigation_file(file_obj, 'Histopathology', h_types[i], h_dates[i], reg_no)
                    
                histo_list.append({"date": h_dates[i], "type": h_types[i], "site": h_sites[i], "staging": h_stage[i], "grading": h_grade[i], "interpretation": h_interp[i], "comment": h_comm[i], "file": f_path})

        # 3. Biomarker Update
        b_dates, b_marks, b_stats, b_sub, b_vaf, b_comm = request.form.getlist('b_date[]'), request.form.getlist('b_marker[]'), request.form.getlist('b_status[]'), request.form.getlist('b_sub[]'), request.form.getlist('b_vaf[]'), request.form.getlist('b_comm[]')
        for i in range(len(b_dates)):
            if b_dates[i].strip() or b_marks[i].strip():
                f_path = old_bio[i].get('file') if i < len(old_bio) else None
                file_obj = request.files.get(f'b_file_{i}')
                if file_obj and file_obj.filename != '':
                    f_path = save_investigation_file(file_obj, 'Biomarker', b_marks[i], b_dates[i], reg_no)
                    
                bio_list.append({"date": b_dates[i], "biomarker": b_marks[i], "status": b_stats[i], "sub_biomarker": b_sub[i], "vaf": b_vaf[i], "comment": b_comm[i], "file": f_path})

        # Override the old JSON data with the newly updated lists
        record.cytology_data = json.dumps(cyto_list)
        record.histopathology_data = json.dumps(histo_list)
        record.biomarker_data = json.dumps(bio_list)
        
        db.session.commit()
        flash('Pathology record updated successfully!')
        return redirect(url_for('inv_pathology', patient_id=patient.id))

    # Parse JSON string back into dictionaries so the HTML template can read them easily
    parsed_record = {
        'id': record.id,
        'cytology': json.loads(record.cytology_data) if record.cytology_data else [],
        'histopathology': json.loads(record.histopathology_data) if record.histopathology_data else [],
        'biomarker': json.loads(record.biomarker_data) if record.biomarker_data else []
    }
    
    # Ensure any mismatched variable names (like 'micro' vs 'microscopic') are handled safely for the template
    for c in parsed_record['cytology']:
        c['micro'] = c.get('microscopic', '')

    return render_template('inv_pathology_form.html', patient=patient, record=parsed_record, user=session)

@app.route('/patient/<int:patient_id>/investigations/radiology')
@login_required
def inv_radiology(patient_id):
    return render_template('inv_radiology_dashboard.html', patient=Patient.query.get_or_404(patient_id), records=[{'id': r.id, 'date': r.record_date, 'data': json.loads(r.radiology_data) if r.radiology_data else [], 'author': r.created_by} for r in Patient.query.get_or_404(patient_id).radiology_records], user=session)

@app.route('/patient/<int:patient_id>/investigations/radiology/new', methods=['GET', 'POST'])
@login_required
def inv_radiology_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        data_list = []
        dates, tests, organs, results, comms = request.form.getlist('r_date[]'), request.form.getlist('r_test[]'), request.form.getlist('r_organ[]'), request.form.getlist('r_result[]'), request.form.getlist('r_comm[]')
        for i in range(len(dates)):
            if dates[i].strip() or tests[i].strip(): data_list.append({"date": dates[i], "test": tests[i], "organ": organs[i], "result": results[i], "comment": comms[i], "file": save_investigation_file(request.files.get(f'r_file_{i}'), 'Radiology', tests[i], dates[i], patient.registration_number)})
        if data_list: db.session.add(RadiologyRecord(patient_id=patient.id, radiology_data=json.dumps(data_list), created_by=session.get('username'))); db.session.commit()
        return redirect(url_for('inv_radiology', patient_id=patient.id))
    return render_template('inv_radiology_form.html', patient=patient, user=session)

@app.route('/patient/<int:patient_id>/investigations/biochemistry')
@login_required
def inv_biochemistry(patient_id):
    return render_template('inv_biochemistry_dashboard.html', patient=Patient.query.get_or_404(patient_id), records=[{'id': r.id, 'date': r.record_date, 'data': json.loads(r.biochemistry_data) if r.biochemistry_data else [], 'author': r.created_by} for r in Patient.query.get_or_404(patient_id).biochemistry_records], user=session)

@app.route('/patient/<int:patient_id>/investigations/biochemistry/new', methods=['GET', 'POST'])
@login_required
def inv_biochemistry_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        data_list = []
        dates, tests, results, comms = request.form.getlist('b_date[]'), request.form.getlist('b_test[]'), request.form.getlist('b_result[]'), request.form.getlist('b_comm[]')
        for i in range(len(dates)):
            if dates[i].strip() or tests[i].strip(): data_list.append({"date": dates[i], "test": tests[i], "result": results[i], "comment": comms[i], "file": save_investigation_file(request.files.get(f'b_file_{i}'), 'Biochemistry', tests[i], dates[i], patient.registration_number)})
        if data_list: db.session.add(BiochemistryRecord(patient_id=patient.id, biochemistry_data=json.dumps(data_list), created_by=session.get('username'))); db.session.commit()
        return redirect(url_for('inv_biochemistry', patient_id=patient.id))
    return render_template('inv_biochemistry_form.html', patient=patient, user=session)

@app.route('/patient/<int:patient_id>/investigations/miscellaneous')
@login_required
def inv_miscellaneous(patient_id):
    return render_template('inv_miscellaneous_dashboard.html', patient=Patient.query.get_or_404(patient_id), records=[{'id': r.id, 'date': r.record_date, 'data': json.loads(r.miscellaneous_data) if r.miscellaneous_data else [], 'author': r.created_by} for r in Patient.query.get_or_404(patient_id).miscellaneous_records], user=session)

@app.route('/patient/<int:patient_id>/investigations/miscellaneous/new', methods=['GET', 'POST'])
@login_required
def inv_miscellaneous_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        data_list = []
        dates, tests, results, comms = request.form.getlist('m_date[]'), request.form.getlist('m_test[]'), request.form.getlist('m_result[]'), request.form.getlist('m_comm[]')
        for i in range(len(dates)):
            if dates[i].strip() or tests[i].strip(): data_list.append({"date": dates[i], "test": tests[i], "result": results[i], "comment": comms[i], "file": save_investigation_file(request.files.get(f'm_file_{i}'), 'Miscellaneous', tests[i], dates[i], patient.registration_number)})
        if data_list: db.session.add(MiscellaneousRecord(patient_id=patient.id, miscellaneous_data=json.dumps(data_list), created_by=session.get('username'))); db.session.commit()
        return redirect(url_for('inv_miscellaneous', patient_id=patient.id))
    return render_template('inv_miscellaneous_form.html', patient=patient, user=session)

# ==========================================
# APPOINTMENTS SCHEDULER
# ==========================================
@app.route('/appointments')
@login_required
def appointments_dashboard():
    # Modern Feature: Date Navigation
    target_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    prev_date = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Fetch today's appointments ordered chronologically
    daily_appts = Appointment.query.filter_by(appointment_date=target_date).order_by(Appointment.appointment_time.asc()).all()
    
    return render_template('appointments_dashboard.html', appointments=daily_appts, current_date=target_date, prev_date=prev_date, next_date=next_date, user=session)

@app.route('/api/patient/<int:patient_id>/basic_info')
@login_required
def api_patient_basic_info(patient_id):
    # API to auto-fetch demographic/diagnosis data for the Appointment Form
    patient = Patient.query.get_or_404(patient_id)
    return {"age": patient.age, "gender": patient.gender, "diagnosis": patient.primary_diagnosis}

@app.route('/appointments/new', methods=['GET', 'POST'])
@login_required
def appointment_new():
    if request.method == 'POST':
        new_app = Appointment(
            patient_id=request.form.get('patient_id'),
            appointment_date=datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date(),
            appointment_time=datetime.strptime(request.form['appointment_time'], '%H:%M').time(),
            physician_name=request.form.get('physician_name'),
            status=request.form.get('status'),
            notes=request.form.get('notes'),
            created_by=session.get('username')
        )
        db.session.add(new_app)
        db.session.commit()
        return redirect(url_for('appointments_dashboard', date=request.form['appointment_date']))
        
    patients = Patient.query.all()
    physicians = User.query.filter_by(is_approved=True).all()
    selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    return render_template('appointment_form.html', patients=patients, physicians=physicians, default_date=selected_date, user=session)

@app.route('/appointments/update_status/<int:app_id>', methods=['POST'])
@login_required
def update_appointment_status(app_id):
    # Modern Feature: Quick inline status updates from the dashboard
    appt = Appointment.query.get_or_404(app_id)
    appt.status = request.form.get('status')
    db.session.commit()
    return redirect(url_for('appointments_dashboard', date=appt.appointment_date.strftime('%Y-%m-%d')))

# ==========================================
# PROTOCOLS MASTER
# ==========================================
@app.route('/protocols')
@login_required
def protocols_master(): return render_template('protocols_dashboard.html', protocols=ChemoProtocol.query.order_by(ChemoProtocol.created_on.desc()).all(), user=session)

@app.route('/protocols/new', methods=['GET', 'POST'])
@login_required
def protocols_new():
    if request.method == 'POST':
        edu_file = ""
        if 'edu_material' in request.files and request.files['edu_material'].filename:
            f = request.files['edu_material']; safe_name = secure_filename(f"Protocol_{request.form.get('name')}_{datetime.now().strftime('%Y%m%d%H%M%S')}{os.path.splitext(f.filename)[1]}"); f.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name)); edu_file = safe_name

        thm_list = []
        thm_forms, thm_drugs, thm_doses, thm_routes, thm_freqs, thm_days = request.form.getlist('thm_form[]'), request.form.getlist('thm_drug[]'), request.form.getlist('thm_dose[]'), request.form.getlist('thm_route[]'), request.form.getlist('thm_freq[]'), request.form.getlist('thm_days[]')
        for i in range(len(thm_drugs)):
            if thm_drugs[i].strip(): thm_list.append({ "form": thm_forms[i], "drug": thm_drugs[i], "dose": thm_doses[i], "route": thm_routes[i], "frequency": thm_freqs[i], "days": thm_days[i] })

        assign_days = request.form.getlist('assign_days')
        day_drugs_dict = {}
        for day in assign_days:
            day_list = []
            d_types, d_forms, d_names, d_doses, d_routes, d_dils, d_maxs, d_infs, d_notes = request.form.getlist(f'd_type_{day}[]'), request.form.getlist(f'd_form_{day}[]'), request.form.getlist(f'd_name_{day}[]'), request.form.getlist(f'd_dose_{day}[]'), request.form.getlist(f'd_route_{day}[]'), request.form.getlist(f'd_diluent_{day}[]'), request.form.getlist(f'd_max_{day}[]'), request.form.getlist(f'd_infusion_{day}[]'), request.form.getlist(f'd_note_{day}[]')
            for i in range(len(d_names)):
                if d_names[i].strip(): day_list.append({ "type": d_types[i], "form": d_forms[i], "name": d_names[i], "dose": d_doses[i], "route": d_routes[i], "diluent": d_dils[i], "max_dose": d_maxs[i], "infusion": d_infs[i], "note": d_notes[i] })
            day_drugs_dict[day] = day_list

        db.session.add(ChemoProtocol(name=request.form.get('name'), intent=request.form.get('intent'), num_cycles=request.form.get('num_cycles'), days_between_cycles=request.form.get('days_between_cycles'), prerequisites=request.form.get('prerequisites'), assign_days=json.dumps(assign_days), edu_material=edu_file, discharge_instructions=request.form.get('discharge_instructions'), take_home_meds=json.dumps(thm_list), cycle_notes=request.form.get('cycle_notes'), day_drugs=json.dumps(day_drugs_dict), created_by=session.get('username')))
        db.session.commit()
        return redirect(url_for('protocols_master'))
    return render_template('protocols_form.html', proto=None, user=session)

@app.route('/protocols/edit/<int:proto_id>', methods=['GET', 'POST'])
@login_required
def protocols_edit(proto_id):
    if session.get('role') not in ['Admin', 'Physician']: abort(403)
    proto = ChemoProtocol.query.get_or_404(proto_id)
    if request.method == 'POST':
        proto.name, proto.intent, proto.num_cycles, proto.days_between_cycles = request.form.get('name'), request.form.get('intent'), request.form.get('num_cycles'), request.form.get('days_between_cycles')
        proto.prerequisites, proto.discharge_instructions, proto.cycle_notes = request.form.get('prerequisites'), request.form.get('discharge_instructions'), request.form.get('cycle_notes')
        if 'edu_material' in request.files and request.files['edu_material'].filename:
            f = request.files['edu_material']; safe_name = secure_filename(f"Protocol_{proto.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{os.path.splitext(f.filename)[1]}"); f.save(os.path.join(app.config['UPLOAD_FOLDER'], safe_name)); proto.edu_material = safe_name
        thm_list = []
        thm_forms, thm_drugs, thm_doses, thm_routes, thm_freqs, thm_days = request.form.getlist('thm_form[]'), request.form.getlist('thm_drug[]'), request.form.getlist('thm_dose[]'), request.form.getlist('thm_route[]'), request.form.getlist('thm_freq[]'), request.form.getlist('thm_days[]')
        for i in range(len(thm_drugs)):
            if thm_drugs[i].strip(): thm_list.append({ "form": thm_forms[i], "drug": thm_drugs[i], "dose": thm_doses[i], "route": thm_routes[i], "frequency": thm_freqs[i], "days": thm_days[i] })
        proto.take_home_meds = json.dumps(thm_list)
        assign_days = request.form.getlist('assign_days'); proto.assign_days = json.dumps(assign_days)
        
        day_drugs_dict = {}
        for day in assign_days:
            day_list = []
            d_types, d_forms, d_names, d_multipliers, d_aucs, d_doses, d_routes, d_dils, d_maxs, d_infs, d_notes = request.form.getlist(f'd_type_{day}[]'), request.form.getlist(f'd_form_{day}[]'), request.form.getlist(f'd_name_{day}[]'), request.form.getlist(f'd_multiplier_{day}[]'), request.form.getlist(f'd_auc_{day}[]'), request.form.getlist(f'd_dose_{day}[]'), request.form.getlist(f'd_route_{day}[]'), request.form.getlist(f'd_diluent_{day}[]'), request.form.getlist(f'd_max_{day}[]'), request.form.getlist(f'd_infusion_{day}[]'), request.form.getlist(f'd_note_{day}[]')
            for i in range(len(d_names)):
                if d_names[i].strip(): 
                    day_list.append({ 
                        "type": d_types[i] if i < len(d_types) else '', 
                        "form": d_forms[i] if i < len(d_forms) else '', 
                        "name": d_names[i], 
                        "multiplier": d_multipliers[i] if i < len(d_multipliers) else 'BSA', 
                        "auc": d_aucs[i] if i < len(d_aucs) else '0', 
                        "dose": d_doses[i] if i < len(d_doses) else '', 
                        "route": d_routes[i] if i < len(d_routes) else '', 
                        "diluent": d_dils[i] if i < len(d_dils) else '', 
                        "max_dose": d_maxs[i] if i < len(d_maxs) else '', 
                        "infusion": d_infs[i] if i < len(d_infs) else '', 
                        "note": d_notes[i] if i < len(d_notes) else '' 
                    })
            day_drugs_dict[day] = day_list
            
        proto.day_drugs = json.dumps(day_drugs_dict); db.session.commit()
        return redirect(url_for('protocols_master'))
    return render_template('protocols_form.html', proto=proto, user=session)

@app.route('/protocols/delete/<int:proto_id>')
@login_required
def protocols_delete(proto_id):
    if session.get('role') != 'Admin': abort(403)
    db.session.delete(ChemoProtocol.query.get_or_404(proto_id)); db.session.commit(); return redirect(url_for('protocols_master'))

@app.route('/patient/<int:patient_id>/terminate_protocol/<int:assignment_id>', methods=['POST'])
@login_required
def terminate_protocol(patient_id, assignment_id):
    # Using your actual model name: PatientProtocol
    assignment = PatientProtocol.query.get_or_404(assignment_id)
    
    assignment.status = 'Terminated'
    assignment.termination_reason = request.form.get('termination_reason')
    db.session.commit()
    
    flash('Protocol has been successfully terminated.')
    return redirect(url_for('day_care', patient_id=patient_id))

# ==========================================
# DAY CARE
# ==========================================
@app.route('/patient/<int:patient_id>/day_care', methods=['GET', 'POST'])
@login_required
def day_care(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST' and 'assign_protocol' in request.form:
        proto_id = request.form.get('protocol_id')
        if proto_id:
            active = PatientProtocol.query.filter_by(patient_id=patient.id, status='Active').first()
            if active: active.status = "Completed"; db.session.commit()
            db.session.add(PatientProtocol(patient_id=patient.id, protocol_id=proto_id, created_by=session.get('username')))
            db.session.commit()
            return redirect(url_for('day_care', patient_id=patient.id))

    active_protocol = PatientProtocol.query.filter_by(patient_id=patient.id, status='Active').first()
    all_protocols = ChemoProtocol.query.all()
    next_cycle, next_day = 1, None
    if active_protocol:
        proto = active_protocol.protocol
        assign_days = sorted([int(d) for d in json.loads(proto.assign_days)]) if json.loads(proto.assign_days) else []
        if assign_days:
            last_record = DayCareRecord.query.filter_by(patient_protocol_id=active_protocol.id).order_by(DayCareRecord.cycle_number.desc(), DayCareRecord.day_number.desc()).first()
            if not last_record:
                next_cycle, next_day = 1, assign_days[0]
            else:
                current_idx = assign_days.index(last_record.day_number)
                if current_idx + 1 < len(assign_days): next_cycle, next_day = last_record.cycle_number, assign_days[current_idx + 1]
                else:
                    next_cycle, next_day = last_record.cycle_number + 1, assign_days[0]
                    if next_cycle > proto.num_cycles: next_cycle, next_day = None, None

    # Fetch all previous protocols that are either Completed or Terminated
    historical_protocols = PatientProtocol.query.filter(
        PatientProtocol.patient_id == patient.id,
        PatientProtocol.status.in_(['Completed', 'Terminated'])
    ).order_by(PatientProtocol.id.desc()).all()

    return render_template('day_care_dashboard.html', patient=patient, active_protocol=active_protocol, all_protocols=all_protocols, next_cycle=next_cycle, next_day=next_day, historical_protocols=historical_protocols, user=session)

@app.route('/patient/<int:patient_id>/day_care/session/<int:proto_id>/<int:cycle>/<int:day>', methods=['GET', 'POST'])
@login_required
def day_care_session(patient_id, proto_id, cycle, day):
    patient, p_proto = Patient.query.get_or_404(patient_id), PatientProtocol.query.get_or_404(proto_id)
    c_proto = p_proto.protocol
    
    if request.method == 'POST':
        # 1. Update Protocol Status (Termination / Completion)
        protocol_action = request.form.get('protocol_action')
        if protocol_action == 'Completed':
            p_proto.status = 'Completed'
        elif protocol_action == 'Terminated':
            p_proto.status = 'Terminated'
            p_proto.termination_reason = request.form.get('termination_reason')
            p_proto.termination_comments = request.form.get('termination_comments')

        administered_at = request.form.get('administered_at', 'BB Precision Oncocare Centre')

        # 2. Extract Data (Captures optional data even if Administered At Other Centre)
        dp_names, dp_calc, dp_pct, dp_final, dp_mod = request.form.getlist('dp_name[]'), request.form.getlist('dp_calc[]'), request.form.getlist('dp_pct[]'), request.form.getlist('dp_final[]'), request.form.getlist('dp_mod[]')
        drug_plan = [{"name": dp_names[i], "calc": dp_calc[i], "pct": dp_pct[i], "final": dp_final[i], "mod": dp_mod[i]} for i in range(len(dp_names))]
        
        ad_names, ad_start, ad_end, ad_lot, ad_exp, ad_comm = request.form.getlist('ad_name[]'), request.form.getlist('ad_start[]'), request.form.getlist('ad_end[]'), request.form.getlist('ad_lot[]'), request.form.getlist('ad_exp[]'), request.form.getlist('ad_comm[]')
        admin_data = [{"name": ad_names[i], "start": ad_start[i], "end": ad_end[i], "lot": ad_lot[i], "exp": ad_exp[i], "comm": ad_comm[i]} for i in range(len(ad_names))]
        
        vitals = {"temp": request.form.get('post_temp'), "pulse": request.form.get('post_pulse'), "bp": request.form.get('post_bp'), "rr": request.form.get('post_rr'), "spo2": request.form.get('post_spo2')}
        exam_sys, exam_find, exam_comm = request.form.getlist('pe_sys[]'), request.form.getlist('pe_find[]'), request.form.getlist('pe_comm[]')
        exams = [{"system": exam_sys[i], "finding": exam_find[i], "comment": exam_comm[i]} for i in range(len(exam_sys)) if exam_sys[i].strip()]
        tox_names, tox_grades = request.form.getlist('tx_name[]'), request.form.getlist('tx_grade[]')
        toxicities = [{"name": tox_names[i], "grade": tox_grades[i]} for i in range(len(tox_names)) if tox_names[i].strip()]
        
        # 3. Save Record (Safely parses dates only if they exist)
        db.session.add(DayCareRecord(
            patient_id=patient.id, patient_protocol_id=p_proto.id, cycle_number=cycle, day_number=day, administered_at=administered_at,
            planned_date=datetime.strptime(request.form['planned_date'], '%Y-%m-%d').date() if request.form.get('planned_date') else None,
            actual_date=datetime.strptime(request.form['actual_date'], '%Y-%m-%d').date() if request.form.get('actual_date') else None,
            is_delayed=request.form.get('is_delayed'), delay_reason=request.form.get('delay_reason'),
            fitness_confirmed=request.form.get('fitness_confirmed'), consent_obtained=request.form.get('consent_obtained'),
            weight=request.form.get('weight'), bsa=request.form.get('bsa'),
            drug_plan_data=json.dumps(drug_plan), admin_data=json.dumps(admin_data),
            post_vitals=json.dumps(vitals), post_exam=json.dumps(exams), post_toxicity=json.dumps(toxicities),
            discharge_notes=request.form.get('discharge_notes'), discharge_meds=request.form.get('discharge_meds'),
            is_finalized=True, created_by=session.get('username')
        ))
        
        db.session.commit()
        return redirect(url_for('day_care', patient_id=patient.id))

    planned_date = date.today()
    if cycle != 1 or day != 1:
        first_rec = DayCareRecord.query.filter_by(patient_protocol_id=p_proto.id, cycle_number=1, day_number=1).first()
        if first_rec and first_rec.actual_date: planned_date = first_rec.actual_date + timedelta(days=((cycle - 1) * c_proto.days_between_cycles) + (day - 1))

    recent_biochem = BiochemistryRecord.query.filter(BiochemistryRecord.patient_id == patient.id, BiochemistryRecord.record_date >= date.today() - timedelta(days=15)).all()
    parsed_biochem = [{"date": rec.record_date, "test": item.get('test'), "result": item.get('result')} for rec in recent_biochem for item in json.loads(rec.biochemistry_data)]
    latest_opd = OpdConsultation.query.filter_by(patient_id=patient.id).order_by(OpdConsultation.visit_date.desc()).first()

    return render_template('day_care_form.html', patient=patient, p_proto=p_proto, c_proto=c_proto, cycle=cycle, day=day, planned_date=planned_date, biochem=parsed_biochem, height=latest_opd.height if latest_opd and latest_opd.height else 0, protocol_drugs=json.loads(c_proto.day_drugs).get(str(day), []), user=session)

@app.route('/patient/<int:patient_id>/day_care/summary/<int:record_id>')
@login_required
def day_care_summary(patient_id, record_id):
    patient, record = Patient.query.get_or_404(patient_id), DayCareRecord.query.get_or_404(record_id)
    return render_template('day_care_summary.html', patient=patient, record=record, drug_plan=json.loads(record.drug_plan_data) if record.drug_plan_data else [], admin=json.loads(record.admin_data) if record.admin_data else [], vitals=json.loads(record.post_vitals) if record.post_vitals else {}, exams=json.loads(record.post_exam) if record.post_exam else [], tox=json.loads(record.post_toxicity) if record.post_toxicity else [], meds=json.loads(record.discharge_meds) if record.discharge_meds else [], user=session)

# ==========================================
# TREATMENTS
# ==========================================
@app.route('/patient/<int:patient_id>/treatments')
@login_required
def treatments(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = [{'id': r.id, 'date': r.record_date, 'author': r.created_by, 'chemo': json.loads(r.chemo_data) if r.chemo_data else [], 'immuno': json.loads(r.immuno_data) if r.immuno_data else [], 'targeted': json.loads(r.targeted_data) if r.targeted_data else [], 'hormonal': json.loads(r.hormonal_data) if r.hormonal_data else [], 'other': json.loads(r.other_med_data) if r.other_med_data else [], 'surgery': json.loads(r.surgery_data) if r.surgery_data else [], 'radiotherapy': json.loads(r.radiotherapy_data) if r.radiotherapy_data else []} for r in patient.treatment_records]
    return render_template('treatments_dashboard.html', patient=patient, records=records, user=session)

import json

@app.route('/patient/<int:patient_id>/treatments/new', methods=['GET', 'POST'])
@login_required
def treatments_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        reg_no = patient.registration_number
        
        # 1. Updated Helper Function for Medical Therapies
        def parse_med_table(prefix):
            lst = []
            if request.form.get(f'has_{prefix}') == 'Yes':
                names = request.form.getlist(f'{prefix}_name[]')
                protocols = request.form.getlist(f'{prefix}_protocol[]') # Extracted Protocol
                doses = request.form.getlist(f'{prefix}_dose[]')
                cycles = request.form.getlist(f'{prefix}_cycles[]')
                starts = request.form.getlist(f'{prefix}_start[]')
                ends = request.form.getlist(f'{prefix}_end[]')
                sets = request.form.getlist(f'{prefix}_setting[]')
                lines = request.form.getlist(f'{prefix}_line[]')
                resps = request.form.getlist(f'{prefix}_resp[]')
                disc_reasons = request.form.getlist(f'{prefix}_disc_reason[]') # Extracted Disc Reason
                comms = request.form.getlist(f'{prefix}_comm[]')
                
                for i in range(len(names)):
                    if names[i].strip(): 
                        lst.append({
                            "drug": names[i], 
                            "protocol": protocols[i] if i < len(protocols) else "",
                            "dose": doses[i] if i < len(doses) else "", 
                            "cycles": cycles[i] if i < len(cycles) else "", 
                            "start_date": starts[i] if i < len(starts) else "", 
                            "end_date": ends[i] if i < len(ends) else "", 
                            "setting": sets[i] if i < len(sets) else "", 
                            "line": lines[i] if i < len(lines) else "", 
                            "response": resps[i] if i < len(resps) else "", 
                            "disc_reason": disc_reasons[i] if i < len(disc_reasons) else "",
                            "comment": comms[i] if i < len(comms) else ""
                        })
            return lst

        # 2. Surgery Data Extraction
        surg_list = []
        if request.form.get('has_surgery') == 'Yes':
            s_dates, s_names, s_ints, s_apps, s_convs, s_durs, s_margs, s_ebls, s_nodes, s_lvis, s_pnis, s_grads, s_dets = request.form.getlist('s_date[]'), request.form.getlist('s_name[]'), request.form.getlist('s_int[]'), request.form.getlist('s_app[]'), request.form.getlist('s_conv[]'), request.form.getlist('s_dur[]'), request.form.getlist('s_marg[]'), request.form.getlist('s_ebl[]'), request.form.getlist('s_node[]'), request.form.getlist('s_lvi[]'), request.form.getlist('s_pni[]'), request.form.getlist('s_grad[]'), request.form.getlist('s_det[]')
            for i in range(len(s_names)):
                if s_names[i].strip():
                    f_path = save_investigation_file(request.files.get(f's_file_{i}'), 'Surgery', s_names[i], s_dates[i], reg_no)
                    surg_list.append({"date": s_dates[i], "name": s_names[i], "intent": s_ints[i], "approach": s_apps[i], "conversion": s_convs[i], "duration": s_durs[i], "margin": s_margs[i], "ebl": s_ebls[i], "nodes": s_nodes[i], "lvi": s_lvis[i], "pni": s_pnis[i], "grade": s_grads[i], "details": s_dets[i], "file": f_path})

        # 3. Radiotherapy Data Extraction
        rad_list = []
        if request.form.get('has_rt') == 'Yes':
            r_dates, r_ints, r_techs, r_orgs, r_plancycs, r_totdoses, r_fracs, r_numfracs, r_totsess, r_dosefracs, r_comms = request.form.getlist('r_date[]'), request.form.getlist('r_int[]'), request.form.getlist('r_tech[]'), request.form.getlist('r_org[]'), request.form.getlist('r_plancyc[]'), request.form.getlist('r_totdose[]'), request.form.getlist('r_frac[]'), request.form.getlist('r_numfrac[]'), request.form.getlist('r_totsess[]'), request.form.getlist('r_dosefrac[]'), request.form.getlist('r_comm[]')
            for i in range(len(r_techs)):
                if r_techs[i].strip() or r_orgs[i].strip():
                    f_path = save_investigation_file(request.files.get(f'r_file_{i}'), 'Radiotherapy', r_techs[i], r_dates[i], reg_no)
                    rad_list.append({"date": r_dates[i], "intent": r_ints[i], "tech": r_techs[i], "organs": r_orgs[i], "plan_cyc": r_plancycs[i], "tot_dose": r_totdoses[i], "frac": r_fracs[i], "num_frac": r_numfracs[i], "tot_sess": r_totsess[i], "dose_frac": r_dosefracs[i], "comment": r_comms[i], "file": f_path})

        # 4. Save to Database
        db.session.add(TreatmentRecord(
            patient_id=patient.id, 
            chemo_data=json.dumps(parse_med_table('ch')), 
            immuno_data=json.dumps(parse_med_table('im')), 
            targeted_data=json.dumps(parse_med_table('tg')), 
            hormonal_data=json.dumps(parse_med_table('ho')), 
            other_med_data=json.dumps(parse_med_table('ot')), 
            surgery_data=json.dumps(surg_list), 
            radiotherapy_data=json.dumps(rad_list), 
            created_by=session.get('username')
        ))
        
        db.session.commit()
        return redirect(url_for('treatments', patient_id=patient.id))
        
    # Fetch the user from the database using the active session
    # (Make sure 'User' matches your actual database model name)
    active_user = User.query.filter_by(username=session.get('username')).first()
    
    return render_template('treatments_form.html', patient=patient, user=active_user)

    dc_summary = []
    for pp in PatientProtocol.query.filter_by(patient_id=patient.id).all():
        latest_rec = DayCareRecord.query.filter_by(patient_protocol_id=pp.id, is_finalized=True).order_by(DayCareRecord.cycle_number.desc()).first()
        dc_summary.append({"regimen": pp.protocol.name, "cycles": latest_rec.cycle_number if latest_rec else 0})

    opd_meds = []
    for opd in OpdConsultation.query.filter_by(patient_id=patient.id).order_by(OpdConsultation.visit_date.desc()).limit(3).all():
        if opd.treatment_plan:
            for drug in json.loads(opd.treatment_plan): opd_meds.append({"date": opd.visit_date, "drug": drug.get("drug"), "duration": drug.get("duration")})

    return render_template('treatments_form.html', patient=patient, dc_summary=dc_summary, opd_meds=opd_meds, user=session)

@app.route('/patient/<int:patient_id>/tumour_board')
@login_required
def tumour_board(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = [{'id': r.id, 'date': r.board_date, 'members': json.loads(r.members_data) if r.members_data else [], 'discussion': r.discussion, 'next_steps': r.next_steps, 'author': r.created_by} for r in patient.tumour_board_records]
    return render_template('tumour_board_dashboard.html', patient=patient, records=records, user=session)

@app.route('/patient/<int:patient_id>/tumour_board/new', methods=['GET', 'POST'])
@login_required
def tumour_board_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        members_list = []
        names, specialties = request.form.getlist('tb_name[]'), request.form.getlist('tb_spec[]')
        for i in range(len(names)):
            if names[i].strip() or specialties[i].strip():
                members_list.append({"name": names[i], "specialty": specialties[i]})
                
        db.session.add(TumourBoardRecord(
            patient_id=patient.id, board_date=datetime.strptime(request.form['board_date'], '%Y-%m-%d').date(),
            members_data=json.dumps(members_list), discussion=request.form.get('discussion'),
            next_steps=request.form.get('next_steps'), created_by=session.get('username')
        ))
        db.session.commit()
        flash("Tumour Board details saved successfully.")
        return redirect(url_for('tumour_board', patient_id=patient.id))

    # --- FETCH OVERVIEW DATA FOR LEFT SPLIT SCREEN ---
    med_hist = MedicalHistory.query.filter_by(patient_id=patient.id).first()
    active_history = {}
    if med_hist:
        if med_hist.has_addiction == 'Yes': active_history['Addiction'] = f"{med_hist.addiction_type} ({med_hist.addiction_years or '?'} yrs)"
        if med_hist.has_allergy == 'Yes': active_history['Allergies'] = med_hist.allergy_details
        if med_hist.has_family_history == 'Yes': active_history['Family History'] = f"{med_hist.family_condition} ({med_hist.family_member})"
        if med_hist.has_past_medical == 'Yes': active_history['Co-morbidities'] = med_hist.comorbidity
        if med_hist.has_past_surgical == 'Yes': active_history['Past Surgeries'] = f"{med_hist.surgery_name} ({med_hist.surgery_year or '?'})"

    complaints = [{'date': opd.visit_date, 'complaint': c.get('complaint'), 'frequency': c.get('frequency'), 'start': c.get('start'), 'end': c.get('end')} for opd in patient.opd_visits for c in (json.loads(opd.chief_complaints) if opd.chief_complaints else [])]
    
    cyto, histo, bio = [], [], []
    for pr in patient.pathology_records:
        if pr.cytology_data: cyto.extend(json.loads(pr.cytology_data))
        if pr.histopathology_data: histo.extend(json.loads(pr.histopathology_data))
        if pr.biomarker_data: bio.extend(json.loads(pr.biomarker_data))
    
    radiology = [item for rr in patient.radiology_records for item in (json.loads(rr.radiology_data) if rr.radiology_data else [])]

    disease = patient.disease_records[0] if patient.disease_records else None
    disease_data = {'date': disease.date_of_diagnosis, 'site': disease.primary_site, 'desc': disease.diagnosis_description, 'meta_status': disease.metastasis, 'meta_organs': json.loads(disease.metastasis_organs) if disease.metastasis_organs else [], 'staging': json.loads(disease.staging_data) if disease.staging_data else []} if disease else {}

    med_therapies, surgeries, rt_list = [], [], []
    for tr in patient.treatment_records:
        for t_type, data_col in [('Chemo', tr.chemo_data), ('Immuno', tr.immuno_data), ('Targeted', tr.targeted_data), ('Hormonal', tr.hormonal_data), ('Other', tr.other_med_data)]:
            if data_col:
                for item in json.loads(data_col): item['category'] = t_type; med_therapies.append(item)
        if tr.surgery_data: surgeries.extend(json.loads(tr.surgery_data))
        if tr.radiotherapy_data: rt_list.extend(json.loads(tr.radiotherapy_data))

    return render_template('tumour_board_form.html', patient=patient, active_history=active_history, complaints=complaints, cyto=cyto, histo=histo, bio=bio, radiology=radiology, disease=disease_data, med_therapies=med_therapies, surgeries=surgeries, rt_list=rt_list, user=session)

# ==========================================
# ADMINISTRATIVE ROUTES
# ==========================================
@app.route('/billing')
@login_required
def billing():
    invoices = Invoice.query.order_by(Invoice.created_on.desc()).all()
    return render_template('billing_dashboard.html', invoices=invoices, user=session)

@app.route('/api/patient/<int:patient_id>/billing_info')
@login_required
def api_patient_billing_info(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    visits = []
    # Pull OPD Visits
    for opd in patient.opd_visits: visits.append(f"OPD: {opd.visit_date.strftime('%d-%b-%Y')}")
    # Pull Day Care Visits
    for pp in patient.day_care_protocols:
        for rec in pp.records:
            if rec.is_finalized and rec.actual_date:
                visits.append(f"Day Care: {rec.actual_date.strftime('%d-%b-%Y')} (Cycle {rec.cycle_number} Day {rec.day_number})")
    
    return {"reg_no": patient.registration_number, "age": patient.age, "gender": patient.gender, "visits": visits}

@app.route('/billing/new', methods=['GET', 'POST'])
@login_required
def billing_new():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id')
        
        # Generate Invoice Number (e.g. INV-202604-0001)
        prefix = f"INV-{datetime.now().strftime('%Y%m')}"
        last_inv = Invoice.query.filter(Invoice.invoice_number.like(f"{prefix}-%")).order_by(Invoice.id.desc()).first()
        new_serial = int(last_inv.invoice_number.split('-')[2]) + 1 if last_inv else 1
        inv_number = f"{prefix}-{new_serial:04d}"
        
        new_invoice = Invoice(
            patient_id=patient_id, invoice_number=inv_number,
            invoice_date=datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date(),
            physician_name=request.form.get('physician_name'), visit_date=request.form.get('visit_date'),
            subtotal=float(request.form.get('subtotal', 0)), discount_total=float(request.form.get('discount_total', 0)),
            tax_total=float(request.form.get('tax_total', 0)), grand_total=float(request.form.get('grand_total', 0)),
            created_by=session.get('username')
        )
        db.session.add(new_invoice); db.session.flush() # Flush to get ID for items
        
        # Parse dynamic line items
        cats, descs, qtys = request.form.getlist('cat[]'), request.form.getlist('desc[]'), request.form.getlist('qty[]')
        prices, discs, taxes, totals = request.form.getlist('price[]'), request.form.getlist('disc[]'), request.form.getlist('tax[]'), request.form.getlist('total[]')
        
        for i in range(len(cats)):
            if cats[i].strip() or descs[i].strip():
                item = InvoiceItem(
                    invoice_id=new_invoice.id, category=cats[i], description=descs[i],
                    quantity=int(qtys[i] or 1), unit_price=float(prices[i] or 0), discount=float(discs[i] or 0),
                    tax=float(taxes[i] or 0), total_amount=float(totals[i] or 0)
                )
                db.session.add(item)
                
        db.session.commit()
        flash("Invoice generated successfully.")
        return redirect(url_for('billing_view', invoice_id=new_invoice.id))
        
    patients = Patient.query.all()
    physicians = User.query.filter(User.is_approved==True).all() # Fetch all approved staff
    return render_template('billing_form.html', patients=patients, physicians=physicians, user=session)

@app.route('/billing/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def billing_view(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if request.method == 'POST':
        # Add Payment Logic
        amount = float(request.form.get('pay_amount', 0))
        if amount > 0:
            payment = Payment(
                invoice_id=invoice.id, payment_date=datetime.strptime(request.form['pay_date'], '%Y-%m-%d').date(),
                amount=amount, mode=request.form.get('pay_mode'), transaction_id=request.form.get('pay_txn'),
                created_by=session.get('username')
            )
            db.session.add(payment)
            
            # Recalculate Invoice Status
            invoice.amount_paid += amount
            if invoice.amount_paid >= invoice.grand_total: invoice.status = 'Paid'
            elif invoice.amount_paid > 0: invoice.status = 'Partial'
            
            db.session.commit()
            flash("Payment recorded successfully.")
            return redirect(url_for('billing_view', invoice_id=invoice.id))
            
    return render_template('billing_view.html', invoice=invoice, user=session)

@app.route('/billing/delete/<int:invoice_id>')
@login_required
def billing_delete(invoice_id):
    if session.get('role') != 'Admin': abort(403)
    db.session.delete(Invoice.query.get_or_404(invoice_id))
    db.session.commit()
    flash("Invoice deleted successfully.")
    return redirect(url_for('billing'))

@app.route('/reports')
@login_required
def reports(): return render_template('module_placeholder.html', module_name="Administrative Reports", user=session)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard(): return render_template('admin_dashboard.html', users=User.query.all(), user=session)

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    if session.get('role') != 'Admin': abort(403)
    
    target_user = User.query.get_or_404(user_id)
    
    # Security check: Prevent the admin from accidentally deactivating themselves
    if target_user.username == session.get('username'):
        flash("Action denied: You cannot deactivate your own Admin account.")
    else:
        target_user.is_approved = not target_user.is_approved
        db.session.commit()
        status_msg = "Activated" if target_user.is_approved else "Deactivated"
        flash(f"Account for {target_user.first_name} {target_user.last_name} has been {status_msg}.")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/view_user/<int:user_id>')
@login_required
def admin_view_user(user_id): return render_template('admin_view_user.html', target_user=User.query.get_or_404(user_id), user=session)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id); user.is_approved = True; db.session.commit(); return redirect(url_for('admin_dashboard'))

# ==========================================
# EXPORTS
# ==========================================
@app.route('/export/treatments')
@login_required
def export_treatments():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, TreatmentRecord).join(TreatmentRecord).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Record Date', 'Had Chemo', 'Had Immuno', 'Had Targeted', 'Had Surgery', 'Had RT', 'Physician'])
    for pat, rec in records:
        cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", rec.record_date, 'Yes' if rec.chemo_data and rec.chemo_data != '[]' else 'No', 'Yes' if rec.immuno_data and rec.immuno_data != '[]' else 'No', 'Yes' if rec.targeted_data and rec.targeted_data != '[]' else 'No', 'Yes' if rec.surgery_data and rec.surgery_data != '[]' else 'No', 'Yes' if rec.radiotherapy_data and rec.radiotherapy_data != '[]' else 'No', rec.created_by])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=treatments.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/disease')
@login_required
def export_disease():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, DiseaseDiagnosis).join(DiseaseDiagnosis).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Date of Diagnosis', 'Primary Site', 'Risk Stratification', 'Metastasis', 'Physician'])
    for pat, rec in records:
        cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", rec.date_of_diagnosis, rec.primary_site, rec.risk_stratification, rec.metastasis, rec.created_by])
    out = make_response(si.getvalue())
    out.headers["Content-Disposition"] = "attachment; filename=disease_diagnosis.csv"
    out.headers["Content-type"] = "text/csv"
    return out

@app.route('/export/patients')
@login_required
def export_patients():
    if session.get('role') != 'Admin': abort(403)
    patients = Patient.query.all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Name', 'DOB', 'Gender', 'Mobile', 'Diagnosis'])
    for p in patients: cw.writerow([p.registration_number, f"{p.first_name} {p.last_name}", p.dob, p.gender, p.mobile_number, p.primary_diagnosis])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=patients.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/medical_history')
@login_required
def export_medical_history():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, MedicalHistory).outerjoin(MedicalHistory).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Name', 'Addictions', 'Allergies', 'FamilyHist'])
    for pat, hist in records:
        if hist: cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", hist.addiction_type, hist.allergy_details, hist.family_condition])
        else: cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", 'No Record', '', ''])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=medical_history.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/opd')
@login_required
def export_opd():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, OpdConsultation).join(OpdConsultation).order_by(OpdConsultation.visit_date.desc()).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Visit Date', 'Primary Diagnosis', 'ECOG', 'Weight(kg)', 'BSA', 'Next Visit', 'Physician'])
    for pat, opd in records: cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", opd.visit_date, opd.primary_diagnosis, opd.ecog, opd.weight, opd.bsa, opd.next_visit_date, opd.created_by])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=opd_consultations.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/radiology')
@login_required
def export_radiology():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, RadiologyRecord).join(RadiologyRecord).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Record Date', 'Test Name', 'Organ', 'Result', 'Physician'])
    for pat, rec in records:
        for item in json.loads(rec.radiology_data): cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", rec.record_date, item.get('test'), item.get('organ'), item.get('result'), rec.created_by])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=radiology.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/biochemistry')
@login_required
def export_biochemistry():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, BiochemistryRecord).join(BiochemistryRecord).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Record Date', 'Test Name', 'Result', 'Physician'])
    for pat, rec in records:
        for item in json.loads(rec.biochemistry_data): cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", rec.record_date, item.get('test'), item.get('result'), rec.created_by])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=biochemistry.csv"; out.headers["Content-type"] = "text/csv"; return out

@app.route('/export/miscellaneous')
@login_required
def export_miscellaneous():
    if session.get('role') != 'Admin': abort(403)
    records = db.session.query(Patient, MiscellaneousRecord).join(MiscellaneousRecord).all()
    si = StringIO(); cw = csv.writer(si)
    cw.writerow(['RegNo', 'Patient Name', 'Record Date', 'Test Name', 'Result', 'Physician'])
    for pat, rec in records:
        for item in json.loads(rec.miscellaneous_data): cw.writerow([pat.registration_number, f"{pat.first_name} {pat.last_name}", rec.record_date, item.get('test'), item.get('result'), rec.created_by])
    out = make_response(si.getvalue()); out.headers["Content-Disposition"] = "attachment; filename=miscellaneous.csv"; out.headers["Content-type"] = "text/csv"; return out

# ==========================================
# INITIALIZATION & SERVER START
# ==========================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            default_admin = User(
                salutation='System', 
                first_name='Super', 
                last_name='Admin', 
                role='Admin', 
                mobile_number='0000000000', 
                email='admin@bbprecision.local', 
                username='admin', 
                is_approved=True
            )
            default_admin.set_password('admin123')
            db.session.add(default_admin)
            db.session.commit()
            
    app.run(debug=True, use_reloader=False)
