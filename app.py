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
    has_addiction, addiction_type, addiction_years, addiction_comments = db.Column(db.String(5), default='No'), db.Column(db.String(100)), db.Column(db.Integer), db.Column(db.Text)
    has_allergy, allergy_details, allergy_years, allergy_comments = db.Column(db.String(5), default='No'), db.Column(db.String(100)), db.Column(db.Integer), db.Column(db.Text)
    has_family_history, family_condition, family_member, family_comments = db.Column(db.String(5), default='No'), db.Column(db.String(100)), db.Column(db.String(50)), db.Column(db.Text)
    has_past_medical, comorbidity, medicine_names, is_controlled, medical_comments = db.Column(db.String(5), default='No'), db.Column(db.String(200)), db.Column(db.String(200)), db.Column(db.String(20)), db.Column(db.Text)
    has_past_surgical, surgery_name, surgery_year, surgery_indication, surgical_comments = db.Column(db.String(5), default='No'), db.Column(db.String(100)), db.Column(db.Integer), db.Column(db.String(200)), db.Column(db.Text)
    marital_status, has_children, updated_on = db.Column(db.String(20)), db.Column(db.String(5), default='No'), db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    id, patient_id, date_of_diagnosis = db.Column(db.Integer, primary_key=True), db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False), db.Column(db.Date, nullable=False, default=date.today)
    primary_site, diagnosis_description, risk_stratification = db.Column(db.String(100)), db.Column(db.Text), db.Column(db.String(20))
    metastasis, metastasis_organs = db.Column(db.String(10), default='Absent'), db.Column(db.Text) 
    tumour_size_data, lymph_node_data, staging_data = db.Column(db.Text), db.Column(db.Text), db.Column(db.Text) 
    created_by, created_on = db.Column(db.String(50)), db.Column(db.DateTime, default=datetime.utcnow)

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
@app.route('/patient/<int:patient_id>/disease_diagnosis')
@login_required
def disease_diagnosis(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    records = [{'id': r.id, 'date': r.date_of_diagnosis, 'site': r.primary_site, 'desc': r.diagnosis_description, 'risk': r.risk_stratification, 'metastasis': r.metastasis, 'organs': json.loads(r.metastasis_organs) if r.metastasis_organs else [], 'tumour': json.loads(r.tumour_size_data) if r.tumour_size_data else [], 'lymph': json.loads(r.lymph_node_data) if r.lymph_node_data else [], 'staging': json.loads(r.staging_data) if r.staging_data else [], 'author': r.created_by} for r in patient.disease_records]
    return render_template('disease_dashboard.html', patient=patient, records=records, user=session)

@app.route('/patient/<int:patient_id>/disease_diagnosis/new', methods=['GET', 'POST'])
@login_required
def disease_diagnosis_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        meta_status = request.form.get('metastasis')
        meta_organs = request.form.getlist('meta_organs[]') if meta_status == 'Present' else []
        tumour_list, lymph_list, staging_list = [], [], []
        ts_lens, ts_wids, ts_deps, ts_ts, ts_descs = request.form.getlist('ts_len[]'), request.form.getlist('ts_wid[]'), request.form.getlist('ts_dep[]'), request.form.getlist('ts_t[]'), request.form.getlist('ts_desc[]')
        for i in range(len(ts_lens)):
            if ts_lens[i].strip() or ts_wids[i].strip(): tumour_list.append({"length": ts_lens[i], "width": ts_wids[i], "depth": ts_deps[i], "t_stage": ts_ts[i], "desc": ts_descs[i]})
        ln_grps, ln_lens, ln_wids, ln_deps, ln_ns, ln_descs = request.form.getlist('ln_grp[]'), request.form.getlist('ln_len[]'), request.form.getlist('ln_wid[]'), request.form.getlist('ln_dep[]'), request.form.getlist('ln_n[]'), request.form.getlist('ln_desc[]')
        for i in range(len(ln_grps)):
            if ln_grps[i].strip() or ln_ns[i].strip(): lymph_list.append({"group": ln_grps[i], "length": ln_lens[i], "width": ln_wids[i], "depth": ln_deps[i], "n_stage": ln_ns[i], "desc": ln_descs[i]})
        st_dates, st_types, st_ts, st_ns, st_ms, st_stages, st_comms = request.form.getlist('st_date[]'), request.form.getlist('st_type[]'), request.form.getlist('st_t[]'), request.form.getlist('st_n[]'), request.form.getlist('st_m[]'), request.form.getlist('st_stage[]'), request.form.getlist('st_comm[]')
        for i in range(len(st_dates)):
            if st_dates[i].strip() or st_stages[i].strip(): staging_list.append({"date": st_dates[i], "type": st_types[i], "t": st_ts[i], "n": st_ns[i], "m": st_ms[i], "stage": st_stages[i], "comment": st_comms[i]})
        db.session.add(DiseaseDiagnosis(patient_id=patient.id, date_of_diagnosis=datetime.strptime(request.form['date_of_diagnosis'], '%Y-%m-%d').date(), primary_site=request.form.get('primary_site'), diagnosis_description=request.form.get('diagnosis_description'), risk_stratification=request.form.get('risk_stratification'), metastasis=meta_status, metastasis_organs=json.dumps(meta_organs), tumour_size_data=json.dumps(tumour_list), lymph_node_data=json.dumps(lymph_list), staging_data=json.dumps(staging_list), created_by=session.get('username')))
        db.session.commit()
        return redirect(url_for('disease_diagnosis', patient_id=patient.id))
    path_records = [{'date': pr.record_date, 'cyto': json.loads(pr.cytology_data) if pr.cytology_data else [], 'histo': json.loads(pr.histopathology_data) if pr.histopathology_data else [], 'bio': json.loads(pr.biomarker_data) if pr.biomarker_data else []} for pr in patient.pathology_records]
    rad_records = [{'date': rr.record_date, 'data': json.loads(rr.radiology_data) if rr.radiology_data else []} for rr in patient.radiology_records]
    return render_template('disease_form.html', patient=patient, path_records=path_records, rad_records=rad_records, user=session)

@app.route('/patient/<int:patient_id>/medical_history', methods=['GET', 'POST'])
@login_required
def medical_history(patient_id):
    patient, history = Patient.query.get_or_404(patient_id), MedicalHistory.query.filter_by(patient_id=patient_id).first()
    if request.method == 'POST':
        if not history: history = MedicalHistory(patient_id=patient.id); db.session.add(history)
        history.has_addiction = request.form.get('has_addiction'); history.addiction_type = request.form.get('addiction_type')
        db.session.commit()
        return redirect(url_for('medical_history', patient_id=patient.id))
    return render_template('medical_history.html', patient=patient, history=history, user=session)

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
            d_types, d_forms, d_names, d_doses, d_routes, d_dils, d_maxs, d_infs, d_notes = request.form.getlist(f'd_type_{day}[]'), request.form.getlist(f'd_form_{day}[]'), request.form.getlist(f'd_name_{day}[]'), request.form.getlist(f'd_dose_{day}[]'), request.form.getlist(f'd_route_{day}[]'), request.form.getlist(f'd_diluent_{day}[]'), request.form.getlist(f'd_max_{day}[]'), request.form.getlist(f'd_infusion_{day}[]'), request.form.getlist(f'd_note_{day}[]')
            for i in range(len(d_names)):
                if d_names[i].strip(): day_list.append({ "type": d_types[i], "form": d_forms[i], "name": d_names[i], "dose": d_doses[i], "route": d_routes[i], "diluent": d_dils[i], "max_dose": d_maxs[i], "infusion": d_infs[i], "note": d_notes[i] })
            day_drugs_dict[day] = day_list
        proto.day_drugs = json.dumps(day_drugs_dict); db.session.commit()
        return redirect(url_for('protocols_master'))
    return render_template('protocols_form.html', proto=proto, user=session)

@app.route('/protocols/delete/<int:proto_id>')
@login_required
def protocols_delete(proto_id):
    if session.get('role') != 'Admin': abort(403)
    db.session.delete(ChemoProtocol.query.get_or_404(proto_id)); db.session.commit(); return redirect(url_for('protocols_master'))

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

    return render_template('day_care_dashboard.html', patient=patient, active_protocol=active_protocol, all_protocols=all_protocols, next_cycle=next_cycle, next_day=next_day, user=session)

@app.route('/patient/<int:patient_id>/day_care/session/<int:proto_id>/<int:cycle>/<int:day>', methods=['GET', 'POST'])
@login_required
def day_care_session(patient_id, proto_id, cycle, day):
    patient, p_proto = Patient.query.get_or_404(patient_id), PatientProtocol.query.get_or_404(proto_id)
    c_proto = p_proto.protocol
    if request.method == 'POST':
        administered_at = request.form.get('administered_at', 'BB Precision Oncocare Centre')
        if administered_at == 'At other centre':
            db.session.add(DayCareRecord(patient_id=patient.id, patient_protocol_id=p_proto.id, cycle_number=cycle, day_number=day, administered_at=administered_at, is_finalized=True, created_by=session.get('username')))
            db.session.commit()
            return redirect(url_for('day_care', patient_id=patient.id))

        dp_names, dp_calc, dp_pct, dp_final, dp_mod = request.form.getlist('dp_name[]'), request.form.getlist('dp_calc[]'), request.form.getlist('dp_pct[]'), request.form.getlist('dp_final[]'), request.form.getlist('dp_mod[]')
        drug_plan = [{"name": dp_names[i], "calc": dp_calc[i], "pct": dp_pct[i], "final": dp_final[i], "mod": dp_mod[i]} for i in range(len(dp_names))]
        
        ad_names, ad_start, ad_end, ad_lot, ad_exp, ad_comm = request.form.getlist('ad_name[]'), request.form.getlist('ad_start[]'), request.form.getlist('ad_end[]'), request.form.getlist('ad_lot[]'), request.form.getlist('ad_exp[]'), request.form.getlist('ad_comm[]')
        admin_data = [{"name": ad_names[i], "start": ad_start[i], "end": ad_end[i], "lot": ad_lot[i], "exp": ad_exp[i], "comm": ad_comm[i]} for i in range(len(ad_names))]
        
        vitals = {"temp": request.form.get('post_temp'), "pulse": request.form.get('post_pulse'), "bp": request.form.get('post_bp'), "rr": request.form.get('post_rr'), "spo2": request.form.get('post_spo2')}
        exam_sys, exam_find, exam_comm = request.form.getlist('pe_sys[]'), request.form.getlist('pe_find[]'), request.form.getlist('pe_comm[]')
        exams = [{"system": exam_sys[i], "finding": exam_find[i], "comment": exam_comm[i]} for i in range(len(exam_sys)) if exam_sys[i].strip()]
        tox_names, tox_grades = request.form.getlist('tx_name[]'), request.form.getlist('tx_grade[]')
        toxicities = [{"name": tox_names[i], "grade": tox_grades[i]} for i in range(len(tox_names)) if tox_names[i].strip()]
        
        db.session.add(DayCareRecord(
            patient_id=patient.id, patient_protocol_id=p_proto.id, cycle_number=cycle, day_number=day, administered_at=administered_at,
            planned_date=datetime.strptime(request.form['planned_date'], '%Y-%m-%d').date() if request.form.get('planned_date') else None,
            actual_date=datetime.strptime(request.form['actual_date'], '%Y-%m-%d').date(),
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

@app.route('/patient/<int:patient_id>/treatments/new', methods=['GET', 'POST'])
@login_required
def treatments_new(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        reg_no = patient.registration_number
        def parse_med_table(prefix):
            lst = []
            if request.form.get(f'has_{prefix}') == 'Yes':
                names, doses, cycles, starts, ends, sets, lines, resps, comms = request.form.getlist(f'{prefix}_name[]'), request.form.getlist(f'{prefix}_dose[]'), request.form.getlist(f'{prefix}_cycles[]'), request.form.getlist(f'{prefix}_start[]'), request.form.getlist(f'{prefix}_end[]'), request.form.getlist(f'{prefix}_setting[]'), request.form.getlist(f'{prefix}_line[]'), request.form.getlist(f'{prefix}_resp[]'), request.form.getlist(f'{prefix}_comm[]')
                for i in range(len(names)):
                    if names[i].strip(): lst.append({"drug": names[i], "dose": doses[i], "cycles": cycles[i], "start": starts[i], "end": ends[i], "setting": sets[i], "line": lines[i], "response": resps[i], "comment": comms[i]})
            return lst

        surg_list = []
        if request.form.get('has_surgery') == 'Yes':
            s_dates, s_names, s_ints, s_apps, s_convs, s_durs, s_margs, s_ebls, s_nodes, s_lvis, s_pnis, s_grads, s_dets = request.form.getlist('s_date[]'), request.form.getlist('s_name[]'), request.form.getlist('s_int[]'), request.form.getlist('s_app[]'), request.form.getlist('s_conv[]'), request.form.getlist('s_dur[]'), request.form.getlist('s_marg[]'), request.form.getlist('s_ebl[]'), request.form.getlist('s_node[]'), request.form.getlist('s_lvi[]'), request.form.getlist('s_pni[]'), request.form.getlist('s_grad[]'), request.form.getlist('s_det[]')
            for i in range(len(s_names)):
                if s_names[i].strip():
                    f_path = save_investigation_file(request.files.get(f's_file_{i}'), 'Surgery', s_names[i], s_dates[i], reg_no)
                    surg_list.append({"date": s_dates[i], "name": s_names[i], "intent": s_ints[i], "approach": s_apps[i], "conversion": s_convs[i], "duration": s_durs[i], "margin": s_margs[i], "ebl": s_ebls[i], "nodes": s_nodes[i], "lvi": s_lvis[i], "pni": s_pnis[i], "grade": s_grads[i], "details": s_dets[i], "file": f_path})

        rad_list = []
        if request.form.get('has_rt') == 'Yes':
            r_dates, r_ints, r_techs, r_orgs, r_plancycs, r_totdoses, r_fracs, r_numfracs, r_totsess, r_dosefracs, r_comms = request.form.getlist('r_date[]'), request.form.getlist('r_int[]'), request.form.getlist('r_tech[]'), request.form.getlist('r_org[]'), request.form.getlist('r_plancyc[]'), request.form.getlist('r_totdose[]'), request.form.getlist('r_frac[]'), request.form.getlist('r_numfrac[]'), request.form.getlist('r_totsess[]'), request.form.getlist('r_dosefrac[]'), request.form.getlist('r_comm[]')
            for i in range(len(r_techs)):
                if r_techs[i].strip() or r_orgs[i].strip():
                    f_path = save_investigation_file(request.files.get(f'r_file_{i}'), 'Radiotherapy', r_techs[i], r_dates[i], reg_no)
                    rad_list.append({"date": r_dates[i], "intent": r_ints[i], "tech": r_techs[i], "organs": r_orgs[i], "plan_cyc": r_plancycs[i], "tot_dose": r_totdoses[i], "frac": r_fracs[i], "num_frac": r_numfracs[i], "tot_sess": r_totsess[i], "dose_frac": r_dosefracs[i], "comment": r_comms[i], "file": f_path})

        db.session.add(TreatmentRecord(patient_id=patient.id, chemo_data=json.dumps(parse_med_table('ch')), immuno_data=json.dumps(parse_med_table('im')), targeted_data=json.dumps(parse_med_table('tg')), hormonal_data=json.dumps(parse_med_table('ho')), other_med_data=json.dumps(parse_med_table('ot')), surgery_data=json.dumps(surg_list), radiotherapy_data=json.dumps(rad_list), created_by=session.get('username')))
        db.session.commit()
        return redirect(url_for('treatments', patient_id=patient.id))

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