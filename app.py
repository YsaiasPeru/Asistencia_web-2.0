from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json, os, sys, io
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = 'asistencia_secret_2026_xK9#mP'

# Use /data directory on Render (persistent disk), fallback to local for dev
import sys
_DATA_DIR = '/data' if os.path.isdir('/data') else '.'
DATA_FILE  = os.path.join(_DATA_DIR, 'data.json')
USERS_FILE = os.path.join(_DATA_DIR, 'users.json')

# ── DATA ──────────────────────────────────────────────────────────────────────

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"grades": [], "attendance": {}, "notes": {}, "subjects": {}}
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        d = json.load(f)
    for k in ('notes', 'subjects', 'attendance'):
        if k not in d: d[k] = {}
    return d

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {'users': []}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def is_first_run():
    """True if no users exist yet."""
    return len(load_users()['users']) == 0

def save_users(data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

_uid_counter = 0
def uid():
    global _uid_counter
    _uid_counter += 1
    return datetime.now().strftime('%f%S%M') + str(_uid_counter)

# ── AUTH HELPERS ──────────────────────────────────────────────────────────────

def get_current_user():
    uid_val = session.get('user_id')
    if not uid_val:
        return None
    users = load_users()
    return next((u for u in users['users'] if u['id'] == uid_val), None)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            return jsonify({'error': 'No autorizado', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        u = get_current_user()
        if not u:
            return jsonify({'error': 'No autorizado'}), 401
        if u['role'] != 'admin':
            return jsonify({'error': 'Solo el administrador puede hacer esto'}), 403
        return f(*args, **kwargs)
    return decorated

def can_access_grade(grade_id):
    """Check if current user can access given grade."""
    u = get_current_user()
    if not u: return False
    if u['role'] == 'admin': return True
    return u.get('grade_id') == grade_id

# ── AUTH ROUTES ───────────────────────────────────────────────────────────────

@app.route('/setup')
def setup_page():
    if not is_first_run():
        return redirect('/login')
    return render_template('setup.html')

@app.route('/api/setup', methods=['POST'])
def do_setup():
    if not is_first_run():
        return jsonify({'error': 'El sistema ya fue configurado'}), 403
    body = request.json
    username = body.get('username','').strip().lower()
    password = body.get('password','')
    name = body.get('name','').strip()
    if not username or not password or not name:
        return jsonify({'error': 'Completa todos los campos'}), 400
    if len(password) < 4:
        return jsonify({'error': 'La contraseña debe tener al menos 4 caracteres'}), 400
    new_user = {
        'id': 'u_' + uid(),
        'username': username,
        'password': generate_password_hash(password),
        'role': 'admin',
        'name': name,
        'grade_id': None
    }
    save_users({'users': [new_user]})
    session['user_id'] = new_user['id']
    return jsonify({'ok': True, 'name': name})

@app.route('/login')
def login_page():
    if is_first_run():
        return redirect('/setup')
    if get_current_user():
        return redirect('/')
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def do_login():
    body = request.json
    username = body.get('username', '').strip().lower()
    password = body.get('password', '')
    users = load_users()
    user = next((u for u in users['users'] if u['username'].lower() == username), None)
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
    session.permanent = True
    session['user_id'] = user['id']
    return jsonify({'ok': True, 'role': user['role'], 'name': user['name']})

@app.route('/api/logout', methods=['POST'])
def do_logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me', methods=['GET'])
def me():
    u = get_current_user()
    if not u:
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify({'id': u['id'], 'username': u['username'], 'name': u['name'],
                    'role': u['role'], 'grade_id': u.get('grade_id')})

# ── USER MANAGEMENT (admin only) ──────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    users = load_users()
    # Don't send passwords
    safe = [{'id':u['id'],'username':u['username'],'name':u['name'],
              'role':u['role'],'grade_id':u.get('grade_id')} for u in users['users']]
    return jsonify(safe)

@app.route('/api/users', methods=['POST'])
@admin_required
def add_user():
    body = request.json
    users = load_users()
    username = body.get('username','').strip().lower()
    if not username or not body.get('password'):
        return jsonify({'error': 'Faltan datos'}), 400
    if any(u['username'].lower() == username for u in users['users']):
        return jsonify({'error': 'El usuario ya existe'}), 400
    new_user = {
        'id': 'u_' + uid(),
        'username': username,
        'password': generate_password_hash(body['password']),
        'role': body.get('role', 'teacher'),
        'name': body.get('name', username),
        'grade_id': body.get('grade_id') or None
    }
    users['users'].append(new_user)
    save_users(users)
    safe = {k: new_user[k] for k in ('id','username','name','role','grade_id')}
    return jsonify(safe)

@app.route('/api/users/<uid_val>', methods=['PUT'])
@admin_required
def update_user(uid_val):
    body = request.json
    users = load_users()
    for u in users['users']:
        if u['id'] == uid_val:
            if 'name' in body:     u['name']     = body['name']
            if 'role' in body:     u['role']     = body['role']
            if 'grade_id' in body: u['grade_id'] = body['grade_id'] or None
            if body.get('password'):
                u['password'] = generate_password_hash(body['password'])
            if 'username' in body:
                new_uname = body['username'].strip().lower()
                clash = any(x['username'].lower()==new_uname and x['id']!=uid_val for x in users['users'])
                if clash:
                    return jsonify({'error': 'Nombre de usuario ya en uso'}), 400
                u['username'] = new_uname
            save_users(users)
            return jsonify({k: u[k] for k in ('id','username','name','role','grade_id')})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/users/<uid_val>', methods=['DELETE'])
@admin_required
def delete_user(uid_val):
    u = get_current_user()
    if u and u['id'] == uid_val:
        return jsonify({'error': 'No puedes eliminarte a ti mismo'}), 403
    # Prevent deleting the last admin
    users_data = load_users()
    target = next((x for x in users_data['users'] if x['id'] == uid_val), None)
    if target and target['role'] == 'admin':
        admins = [x for x in users_data['users'] if x['role'] == 'admin']
        if len(admins) <= 1:
            return jsonify({'error': 'No puedes eliminar el único administrador'}), 403
    users = load_users()
    users['users'] = [x for x in users['users'] if x['id'] != uid_val]
    save_users(users)
    return jsonify({'ok': True})

# ── MAIN PAGE ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if is_first_run():
        return redirect('/setup')
    if not get_current_user():
        return redirect('/login')
    return render_template('index.html')

# ── GRADES ────────────────────────────────────────────────────────────────────

@app.route('/api/grades', methods=['GET'])
@login_required
def get_grades():
    u = get_current_user()
    data = load_data()
    if u['role'] == 'admin':
        return jsonify(data['grades'])
    # Teacher: only their assigned grade
    gid = u.get('grade_id')
    return jsonify([g for g in data['grades'] if g['id'] == gid])

@app.route('/api/grades', methods=['POST'])
@admin_required
def add_grade():
    data = load_data()
    body = request.json
    grade = {
        'id': 'g_' + uid(),
        'name': body['name'],
        'section': body['section'],
        'teacher': body.get('teacher', ''),
        'students': []
    }
    data['grades'].append(grade)
    save_data(data)
    return jsonify(grade)

@app.route('/api/grades/<gid>', methods=['PUT'])
@login_required
def update_grade(gid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    body = request.json
    u = get_current_user()
    for g in data['grades']:
        if g['id'] == gid:
            # Teachers can only update teacher name, not name/section
            if u['role'] == 'admin':
                g['name']    = body.get('name',    g['name'])
                g['section'] = body.get('section', g['section'])
            g['teacher'] = body.get('teacher', g.get('teacher',''))
            save_data(data)
            return jsonify(g)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/grades/<gid>', methods=['DELETE'])
@admin_required
def delete_grade(gid):
    data = load_data()
    data['grades'] = [g for g in data['grades'] if g['id'] != gid]
    data['subjects'].pop(gid, None)
    data['notes'].pop(gid, None)
    for date_entry in data.get('attendance', {}).values():
        date_entry.pop(gid, None)
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/grades/<gid>/students', methods=['POST'])
@login_required
def add_students(gid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    body = request.json
    for g in data['grades']:
        if g['id'] == gid:
            added = []
            for name in body.get('names', []):
                name = name.strip()
                if name:
                    s = {'id': 's_' + uid(), 'name': name}
                    g['students'].append(s)
                    added.append(s)
            save_data(data)
            return jsonify(added)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/grades/<gid>/students/<sid>', methods=['PUT'])
@login_required
def update_student(gid, sid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    body = request.json
    for g in data['grades']:
        if g['id'] == gid:
            for s in g['students']:
                if s['id'] == sid:
                    s['name'] = body.get('name', s['name'])
                    save_data(data)
                    return jsonify(s)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/grades/<gid>/students/<sid>', methods=['DELETE'])
@login_required
def delete_student(gid, sid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for g in data['grades']:
        if g['id'] == gid:
            g['students'] = [s for s in g['students'] if s['id'] != sid]
            for per in data.get('notes', {}).get(gid, {}).values():
                per.pop(sid, None)
            save_data(data)
            return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ── SUBJECTS ──────────────────────────────────────────────────────────────────

@app.route('/api/subjects/<gid>', methods=['GET'])
@login_required
def get_subjects(gid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    return jsonify(data['subjects'].get(gid, []))

@app.route('/api/subjects/<gid>', methods=['POST'])
@login_required
def add_subject(gid):
    if not can_access_grade(gid):
        return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    body = request.json
    subj = {'id': 'sub_' + uid(), 'name': body['name'], 'competencias': []}
    if gid not in data['subjects']:
        data['subjects'][gid] = []
    data['subjects'][gid].append(subj)
    save_data(data)
    return jsonify(subj)

@app.route('/api/subjects/<gid>/<subid>', methods=['PUT'])
@login_required
def update_subject(gid, subid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            s['name'] = request.json.get('name', s['name'])
            save_data(data)
            return jsonify(s)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>', methods=['DELETE'])
@login_required
def delete_subject(gid, subid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    if gid in data['subjects']:
        data['subjects'][gid] = [s for s in data['subjects'][gid] if s['id'] != subid]
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/subjects/<gid>/<subid>/competencias', methods=['POST'])
@login_required
def add_competencia(gid, subid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            comp = {'id': 'comp_' + uid(), 'name': request.json['name'], 'capacidades': []}
            s['competencias'].append(comp)
            save_data(data)
            return jsonify(comp)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>/competencias/<compid>', methods=['PUT'])
@login_required
def update_competencia(gid, subid, compid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            for c in s['competencias']:
                if c['id'] == compid:
                    c['name'] = request.json.get('name', c['name'])
                    save_data(data)
                    return jsonify(c)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>/competencias/<compid>', methods=['DELETE'])
@login_required
def delete_competencia(gid, subid, compid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            s['competencias'] = [c for c in s['competencias'] if c['id'] != compid]
            save_data(data)
            return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>/competencias/<compid>/capacidades', methods=['POST'])
@login_required
def add_capacidad(gid, subid, compid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            for c in s['competencias']:
                if c['id'] == compid:
                    cap = {'id': 'cap_' + uid(), 'name': request.json['name']}
                    c['capacidades'].append(cap)
                    save_data(data)
                    return jsonify(cap)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>/competencias/<compid>/capacidades/<capid>', methods=['PUT'])
@login_required
def update_capacidad(gid, subid, compid, capid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            for c in s['competencias']:
                if c['id'] == compid:
                    for cap in c['capacidades']:
                        if cap['id'] == capid:
                            cap['name'] = request.json.get('name', cap['name'])
                            save_data(data)
                            return jsonify(cap)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/subjects/<gid>/<subid>/competencias/<compid>/capacidades/<capid>', methods=['DELETE'])
@login_required
def delete_capacidad(gid, subid, compid, capid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for s in data['subjects'].get(gid, []):
        if s['id'] == subid:
            for c in s['competencias']:
                if c['id'] == compid:
                    c['capacidades'] = [cap for cap in c['capacidades'] if cap['id'] != capid]
                    save_data(data)
                    return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ── PERIODOS ──────────────────────────────────────────────────────────────────

@app.route('/api/periodos/<gid>', methods=['GET'])
@login_required
def get_periodos(gid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    grade = next((g for g in data['grades'] if g['id'] == gid), None)
    return jsonify(grade.get('periodos', []) if grade else [])

@app.route('/api/periodos/<gid>', methods=['POST'])
@login_required
def add_periodo(gid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for g in data['grades']:
        if g['id'] == gid:
            if 'periodos' not in g: g['periodos'] = []
            p = {'id': 'per_' + uid(), 'name': request.json['name']}
            g['periodos'].append(p)
            save_data(data)
            return jsonify(p)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/periodos/<gid>/<pid>', methods=['PUT'])
@login_required
def update_periodo(gid, pid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for g in data['grades']:
        if g['id'] == gid:
            for p in g.get('periodos', []):
                if p['id'] == pid:
                    p['name'] = request.json.get('name', p['name'])
                    save_data(data)
                    return jsonify(p)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/periodos/<gid>/<pid>', methods=['DELETE'])
@login_required
def delete_periodo(gid, pid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    for g in data['grades']:
        if g['id'] == gid:
            g['periodos'] = [p for p in g.get('periodos', []) if p['id'] != pid]
            data['notes'].get(gid, {}).pop(pid, None)
            save_data(data)
            return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ── NOTES ─────────────────────────────────────────────────────────────────────

@app.route('/api/notes/<gid>/<perid>', methods=['GET'])
@login_required
def get_notes(gid, perid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    return jsonify(data['notes'].get(gid, {}).get(perid, {}))

@app.route('/api/notes/<gid>/<perid>', methods=['POST'])
@login_required
def save_notes(gid, perid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    if gid not in data['notes']: data['notes'][gid] = {}
    data['notes'][gid][perid] = request.json
    save_data(data)
    return jsonify({'ok': True})

# ── ATTENDANCE ────────────────────────────────────────────────────────────────

@app.route('/api/attendance', methods=['POST'])
@login_required
def save_attendance():
    data = load_data()
    body = request.json
    date, gid, records = body['date'], body['grade_id'], body['records']
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    if 'attendance' not in data: data['attendance'] = {}
    if date not in data['attendance']: data['attendance'][date] = {}
    data['attendance'][date][gid] = records
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/attendance/<date>/<gid>', methods=['GET'])
@login_required
def get_attendance(date, gid):
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    return jsonify(data.get('attendance', {}).get(date, {}).get(gid, {}))

# ── PDF ASISTENCIA ────────────────────────────────────────────────────────────

@app.route('/api/report/pdf', methods=['POST'])
@login_required
def generate_pdf():
    body = request.json
    date, gid = body['date'], body['grade_id']
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403
    data = load_data()
    grade = next((g for g in data['grades'] if g['id'] == gid), None)
    if not grade: return jsonify({'error': 'Grado no encontrado'}), 404

    att = data.get('attendance', {}).get(date, {}).get(gid, {})
    present = [s for s in grade['students'] if att.get(s['id']) == True]
    absent  = [s for s in grade['students'] if att.get(s['id']) != True]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story  = []

    title_s = ParagraphStyle('CT', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#1a365d'), spaceAfter=4)
    sub_s   = ParagraphStyle('CS', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#2d3748'), spaceAfter=3)
    sec_s   = ParagraphStyle('SE', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#2b6cb0'), spaceBefore=12, spaceAfter=5)

    story.append(Paragraph("REPORTE DE ASISTENCIA", title_s))
    story.append(Spacer(1, 4))
    try: df = datetime.strptime(date,'%Y-%m-%d').strftime('%d de %B de %Y')
    except: df = date
    story.append(Paragraph(f"<b>Fecha:</b> {df}", sub_s))
    story.append(Paragraph(f"<b>Grado:</b> {grade['name']} — Sección: {grade['section']}", sub_s))
    story.append(Paragraph(f"<b>Profesor(a):</b> {grade.get('teacher','N/A')}", sub_s))
    story.append(Paragraph(f"<b>Total:</b> {len(grade['students'])}  |  <b>Presentes:</b> {len(present)}  |  <b>Ausentes:</b> {len(absent)}", sub_s))
    story.append(Spacer(1, 12))

    def mk_table(rows, hc, rcs, gc):
        t = Table(rows, colWidths=[0.45*inch, 4.8*inch, 1.0*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor(hc)),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,0),10),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor(c) for c in rcs]),
            ('FONTSIZE',(0,1),(-1,-1),9),
            ('GRID',(0,0),(-1,-1),0.4,colors.HexColor(gc)),
            ('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(2,0),(2,-1),'CENTER'),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),7),
        ]))
        return t

    story.append(Paragraph(f"✓ ALUMNOS PRESENTES ({len(present)})", sec_s))
    if present:
        rows = [['#','Nombre del Alumno','Estado']] + [[str(i),s['name'],'Presente'] for i,s in enumerate(sorted(present,key=lambda x:x['name']),1)]
        story.append(mk_table(rows,'#2b6cb0',['#ebf8ff','#ffffff'],'#bee3f8'))
    else:
        story.append(Paragraph("Ningún alumno presente.", styles['Normal']))

    story.append(Spacer(1, 12))
    story.append(Paragraph(f"✗ ALUMNOS AUSENTES ({len(absent)})", sec_s))
    if absent:
        rows = [['#','Nombre del Alumno','Estado']] + [[str(i),s['name'],'Ausente'] for i,s in enumerate(sorted(absent,key=lambda x:x['name']),1)]
        story.append(mk_table(rows,'#c53030',['#fff5f5','#ffffff'],'#fed7d7'))
    else:
        story.append(Paragraph("Todos los alumnos estuvieron presentes.", styles['Normal']))

    story.append(Spacer(1, 28))
    story.append(Paragraph("_"*38+"        "+"_"*38, styles['Normal']))
    story.append(Paragraph("      Firma del Profesor(a)                              Sello / V°B°", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    fn = f"asistencia_{grade['name']}_{grade['section']}_{date}.pdf".replace(' ','_')
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=fn)

# ── PDF NOTAS ─────────────────────────────────────────────────────────────────

@app.route('/api/report/notes/pdf', methods=['POST'])
@login_required
def generate_notes_pdf():
    body   = request.json
    gid    = body['grade_id']
    perid  = body['period_id']
    subid  = body.get('subject_id')
    if not can_access_grade(gid): return jsonify({'error': 'Sin permiso'}), 403

    data    = load_data()
    grade   = next((g for g in data['grades'] if g['id'] == gid), None)
    period  = next((p for p in grade.get('periodos',[]) if p['id'] == perid), None) if grade else None
    subjects = data['subjects'].get(gid, [])
    if subid: subjects = [s for s in subjects if s['id'] == subid]

    if not grade or not period: return jsonify({'error': 'Datos no encontrados'}), 404

    def score_val(v): return {'AD':4,'A':3,'B':2,'C':1}.get(v,0)
    def score_label(avg):
        if avg>=3.5: return 'AD'
        if avg>=2.5: return 'A'
        if avg>=1.5: return 'B'
        return 'C'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=0.6*inch, leftMargin=0.6*inch,
                            topMargin=0.7*inch, bottomMargin=0.7*inch)
    styles = getSampleStyleSheet()
    story  = []

    hdr_s  = ParagraphStyle('H',parent=styles['Title'],  fontSize=17,textColor=colors.HexColor('#1a365d'),spaceAfter=3)
    sub_s  = ParagraphStyle('S',parent=styles['Normal'], fontSize=10,textColor=colors.HexColor('#2d3748'),spaceAfter=2)
    sec_s  = ParagraphStyle('SE',parent=styles['Heading2'],fontSize=12,textColor=colors.HexColor('#2b6cb0'),spaceBefore=10,spaceAfter=4)
    tiny_s = ParagraphStyle('T',parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#4a5568'))
    bold_s = ParagraphStyle('B',parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')

    story.append(Paragraph("REPORTE DE NOTAS", hdr_s))
    story.append(Paragraph(f"<b>Grado:</b> {grade['name']} — Sección: {grade['section']}  |  <b>Profesor(a):</b> {grade.get('teacher','N/A')}  |  <b>Periodo:</b> {period['name']}", sub_s))
    story.append(Paragraph(f"<b>Total alumnos:</b> {len(grade['students'])}", sub_s))
    story.append(Spacer(1, 10))

    legend_data = [['Escala:','AD = Logro Destacado','A = Logro Esperado','B = En Proceso','C = En Inicio']]
    lt = Table(legend_data, colWidths=[0.7*inch,1.5*inch,1.5*inch,1.3*inch,1.2*inch])
    lt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,0),colors.HexColor('#e2e8f0')),
        ('BACKGROUND',(1,0),(1,0),colors.HexColor('#f0fff4')),
        ('BACKGROUND',(2,0),(2,0),colors.HexColor('#ebf8ff')),
        ('BACKGROUND',(3,0),(3,0),colors.HexColor('#fffbeb')),
        ('BACKGROUND',(4,0),(4,0),colors.HexColor('#fff5f5')),
        ('FONTSIZE',(0,0),(-1,-1),8),('FONTNAME',(0,0),(0,0),'Helvetica-Bold'),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#cbd5e0')),
        ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#e2e8f0')),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    story.append(lt)
    story.append(Spacer(1, 12))

    for subj in subjects:
        comps = subj.get('competencias', [])
        if not comps: continue
        story.append(Paragraph(f"📚 {subj['name']}", sec_s))

        comp_indices = [(comp, comp.get('capacidades',[])) for comp in comps]
        name_w, cap_w, prom_w, final_w = 1.8*inch, 0.55*inch, 0.65*inch, 0.7*inch
        col_defs = [name_w]
        for comp, caps in comp_indices:
            col_defs.extend([cap_w]*len(caps))
            col_defs.append(prom_w)
        col_defs.append(final_w)

        row0 = [Paragraph('<b>Alumno</b>', bold_s)]
        row1 = [Paragraph('', tiny_s)]
        span_cmds = []
        ci2 = 1
        for comp, caps in comp_indices:
            row0.append(Paragraph(f'<b>{comp["name"]}</b>', bold_s))
            for _ in range(len(caps)-1): row0.append('')
            row0.append('')
            for cap in caps: row1.append(Paragraph(cap['name'][:18], tiny_s))
            row1.append(Paragraph('<b>Prom.</b>', tiny_s))
            if len(caps) > 0:
                span_cmds.append(('SPAN',(ci2,0),(ci2+len(caps),0)))
            ci2 += len(caps)+1
        row0.append(Paragraph('<b>PROM.\nFINAL</b>', bold_s))
        row1.append(Paragraph('', tiny_s))

        table_rows = [row0, row1]
        student_promedios = {}
        for student in grade['students']:
            sid = student['id']
            sub_notes = data['notes'].get(gid,{}).get(perid,{}).get(sid,{}).get(subj['id'],{})
            row = [Paragraph(student['name'], tiny_s)]
            final_vals = []
            for comp, caps in comp_indices:
                comp_vals = []
                for cap in caps:
                    val = sub_notes.get(comp['id'],{}).get(cap['id'],'')
                    comp_vals.append(score_val(val))
                    row.append(Paragraph(val if val else '–', tiny_s))
                if comp_vals:
                    avg = sum(comp_vals)/len(comp_vals)
                    lbl = score_label(avg)
                    final_vals.append(avg)
                    row.append(Paragraph(f'<b>{lbl}</b>', tiny_s))
                else:
                    row.append(Paragraph('–', tiny_s))
            if final_vals:
                favg = sum(final_vals)/len(final_vals)
                flbl = score_label(favg)
                student_promedios[sid] = flbl
                row.append(Paragraph(f'<b>{flbl}</b>', bold_s))
            else:
                student_promedios[sid] = '–'
                row.append(Paragraph('–', bold_s))
            table_rows.append(row)

        tbl = Table(table_rows, colWidths=col_defs, repeatRows=2)
        ts = TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2b6cb0')),
            ('BACKGROUND',(0,1),(-1,1),colors.HexColor('#4a7fc1')),
            ('TEXTCOLOR',(0,0),(-1,1),colors.white),
            ('FONTNAME',(0,0),(-1,1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,1),8),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ROWBACKGROUNDS',(0,2),(-1,-1),[colors.HexColor('#f7faff'),colors.white]),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#bee3f8')),
            ('FONTSIZE',(0,2),(-1,-1),8),
            ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
            ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ])
        for cmd in span_cmds: ts.add(*cmd)
        tbl.setStyle(ts)
        story.append(tbl)
        story.append(Spacer(1, 10))

        counts = {'AD':0,'A':0,'B':0,'C':0}
        for v in student_promedios.values():
            if v in counts: counts[v] += 1
        total = len(grade['students'])
        aprobados = counts['AD']+counts['A']+counts['B']
        stat_row = [[
            Paragraph(f"<b>AD:</b> {counts['AD']}  <b>A:</b> {counts['A']}  <b>B:</b> {counts['B']}  <b>C:</b> {counts['C']}", tiny_s),
            Paragraph(f"<b>Aprobados:</b> {aprobados}/{total} ({int(aprobados/total*100) if total else 0}%)", tiny_s),
            Paragraph(f"<b>Desaprobados (C):</b> {counts['C']}/{total}", tiny_s),
        ]]
        st = Table(stat_row, colWidths=[2.5*inch,2.5*inch,2.5*inch])
        st.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f0f4ff')),
            ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#c3d3f0')),
            ('INNERGRID',(0,0),(-1,-1),0.3,colors.HexColor('#c3d3f0')),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('FONTSIZE',(0,0),(-1,-1),9),
        ]))
        story.append(st)
        story.append(Spacer(1, 16))

    story.append(Spacer(1, 20))
    story.append(Paragraph("_"*40+"        "+"_"*40, styles['Normal']))
    story.append(Paragraph("      Firma del Profesor(a)                                    Sello / V°B°", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    fn = f"notas_{grade['name']}_{grade['section']}_{period['name']}.pdf".replace(' ','_')
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=fn)

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if is_first_run():
        print("\n  ⚙️  Primera ejecución detectada.")
        print("  Abre http://localhost:5000 para crear tu cuenta.\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
