from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pymysql
import re
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages


# ✅ Database connection setup
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='puppy@2005',
        database='pharmacy_db',
        cursorclass=pymysql.cursors.DictCursor
    )


# 🏠 Home Page (Low Stock Display)
@app.route('/')
def index():
    connection = get_db_connection()
    cursor = connection.cursor()
    # show medicines with numeric quantity <= 5 (handles "10 ml" style strings too)
    cursor.execute("SELECT id, name, qty FROM medicines WHERE qty <= 5")
    low_stock = cursor.fetchall()
    connection.close()
    return render_template('index.html', low_stock=low_stock)


# 💊 Add Medicine
@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():
    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        batch_no = request.form['batch_no']
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        hsn_code = request.form.get('hsn_code', '')
        cost_price = request.form.get('cost_price', '0')
        gst = request.form.get('gst', '0')
        company = request.form.get('company', '')

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO medicines (name, type, company, batch_no, quantity, expiry_date, hsn_code, cost_price, gst)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, type_, company, batch_no, quantity, expiry_date, hsn_code, cost_price, gst))
        connection.commit()
        connection.close()
        flash(f"✅ Medicine '{name}' added successfully!")
        return redirect('/view_medicine')
    return render_template('add_medicine.html')


# 📋 View Medicines
@app.route('/view_medicine')
def view_medicine():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()
    connection.close()
    return render_template('view_medicine.html', medicines=medicines)


# ✏️ Update Medicine (page)
@app.route('/update_medicine/<int:id>', methods=['GET', 'POST'])
def update_medicine(id):
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        name = request.form['name']
        type_ = request.form['type']
        batch_no = request.form['batch_no']
        quantity = request.form['quantity']
        expiry_date = request.form['expiry_date']
        cost_price = request.form.get('cost_price', '0')
        gst = request.form.get('gst', '0')
        company = request.form.get('company', '')

        cursor.execute("""
            UPDATE medicines
            SET name=%s, type=%s, company=%s, batch_no=%s, quantity=%s, expiry_date=%s, cost_price=%s, gst=%s
            WHERE id=%s
        """, (name, type_, company, batch_no, quantity, expiry_date, cost_price, gst, id))
        connection.commit()
        connection.close()
        flash(f"✅ Medicine '{name}' updated successfully!")
        return redirect('/view_medicine')

    cursor.execute("SELECT * FROM medicines WHERE id=%s", (id,))
    medicine = cursor.fetchone()
    connection.close()
    return render_template('update_medicine.html', medicine=medicine)


# ❌ Delete Medicine
@app.route('/delete_medicine/<int:id>')
def delete_medicine(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM medicines WHERE id=%s", (id,))
    connection.commit()
    connection.close()
    flash(f"✅ Medicine deleted successfully!")
    return redirect('/view_medicine')


# 🧍 Add Patient  (adds patient & records sale)
@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT name, cost_price, quantity FROM medicines")
    medicines = cursor.fetchall()
    connection.close()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        address = request.form.get('address', '')
        phone = request.form['phone']
        medicine_name = request.form['medicine_name']

        try:
            quantity = int(request.form['quantity'])
        except ValueError:
            flash("❌ Invalid quantity!")
            return redirect(request.url)

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT cost_price, quantity FROM medicines WHERE name=%s", (medicine_name,))
        med_data = cursor.fetchone()

        if not med_data:
            connection.close()
            flash("❌ Medicine not found!")
            return redirect(request.url)

        # Extract numeric quantity from VARCHAR (e.g. "10 ml" -> 10)
        qty_match = re.findall(r'\d+', str(med_data['quantity']))
        available_qty = int(qty_match[0]) if qty_match else 0

        if available_qty < quantity:
            connection.close()
            flash(f"❌ Only {available_qty} units of {medicine_name} available!")
            return redirect(request.url)

        price_per_unit = Decimal(str(med_data['cost_price']))
        total_price = price_per_unit * quantity

        # Insert patient
        cursor.execute("""
            INSERT INTO patients (name, age, gender, address, phone, medicine_name, quantity, total_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, age, gender, address, phone, medicine_name, str(quantity), str(total_price)))

        # Insert sale
        cursor.execute("""
            INSERT INTO sales (patient_name, medicine_name, quantity, total_price)
            VALUES (%s, %s, %s, %s)
        """, (name, medicine_name, str(quantity), str(total_price)))

        # Update medicine stock (preserve suffix if any)
        suffix_match = re.findall(r'\D+', str(med_data['quantity']))
        suffix = suffix_match[0].strip() if suffix_match else ''
        new_qty = available_qty - quantity
        cursor.execute("UPDATE medicines SET quantity=%s WHERE name=%s", (f"{new_qty} {suffix}".strip(), medicine_name))

        connection.commit()
        connection.close()
        flash(f"✅ Patient '{name}' added and {quantity} units of {medicine_name} sold!")
        return redirect('/view_patient')

    return render_template('add_patient.html', medicines=medicines)


# 🧾 View Patients
@app.route('/view_patient')
def view_patient():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM patients")
    patients = cursor.fetchall()
    connection.close()
    return render_template('view_patient.html', patients=patients)


# ✏️ Update Patient
@app.route('/update_patient/<int:id>', methods=['GET', 'POST'])
def update_patient(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM patients WHERE id=%s", (id,))
    patient = cursor.fetchone()
    cursor.execute("SELECT name FROM medicines")
    medicines = cursor.fetchall()

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        gender = request.form['gender']
        address = request.form['address']
        phone = request.form['phone']
        medicine_name = request.form['medicine_name']
        quantity = request.form['quantity']

        cursor.execute("""
            UPDATE patients 
            SET name=%s, age=%s, gender=%s, address=%s, phone=%s, medicine_name=%s, quantity=%s
            WHERE id=%s
        """, (name, age, gender, address, phone, medicine_name, quantity, id))

        connection.commit()
        connection.close()
        flash(f"✅ Patient '{name}' updated successfully!")
        return redirect('/view_patient')

    connection.close()
    return render_template('update_patient.html', patient=patient, medicines=medicines)


# ❌ Delete Patient
@app.route('/delete_patient/<int:id>')
def delete_patient(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM patients WHERE id=%s", (id,))
    connection.commit()
    connection.close()
    flash(f"✅ Patient deleted successfully!")
    return redirect('/view_patient')


# -------------------------
# API - Get single medicine by ID (used in Check Stock page)
# -------------------------
@app.route('/api/medicine/<int:id>')
def api_get_medicine(id):
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    cur.execute("SELECT * FROM medicines WHERE id=%s", (id,))
    med = cur.fetchone()

    conn.close()

    if not med:
        return jsonify({'error': 'Not found'}), 404

    return jsonify(med)


# 📦 Check Stock (supports dropdown by id and name search)
@app.route('/check_stock', methods=['GET'])
def check_stock():
    q = request.args.get('q', '').strip()       # name search (text box)
    q_id = request.args.get('q_id', '').strip() # optional id (if you want server-side select)

    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)

    # get all medicines list (id + name) for dropdown
    cur.execute("SELECT id, name FROM medicines ORDER BY name")
    all_meds = cur.fetchall()

    if q_id:
        # show specific medicine by id
        cur.execute("SELECT * FROM medicines WHERE id=%s", (q_id,))
        results = cur.fetchall()
        message = "Details for selected medicine"
    elif q:
        # search by name (partial)
        cur.execute("SELECT * FROM medicines WHERE name LIKE %s ORDER BY name", ('%' + q + '%',))
        results = cur.fetchall()
        message = f"Results for \"{q}\"" if results else f"No medicines found matching \"{q}\"."
    else:
        # default: low stock (<=10). If your quantity is numeric column, replace the REGEXP_REPLACE part with simple WHERE quantity <= 10
        cur.execute("SELECT * FROM medicines WHERE CAST(REGEXP_REPLACE(quantity, '[^0-9]', '') AS UNSIGNED) <= 10 ORDER BY quantity ASC")
        results = cur.fetchall()
        message = "Low stock medicines (quantity < 5)" if results else "All medicines are in stock."

    conn.close()
    return render_template('check_stock.html',
                           all_meds=all_meds,
                           results=results,
                           query=q,
                           query_id=q_id,
                           message=message)


# 💸 Sell Medicine (page)
@app.route('/sell_medicine', methods=['GET', 'POST'])
def sell_medicine():
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT name, cost_price, quantity FROM medicines")
    medicines = cursor.fetchall()
    connection.close()

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        medicine_name = request.form['medicine_name']

        try:
            quantity = int(request.form['quantity'])
            price_per_unit = float(request.form['price_per_unit'])
        except ValueError:
            flash("❌ Invalid quantity or price!")
            return redirect(request.url)

        total_price = price_per_unit * quantity

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT quantity FROM medicines WHERE name=%s", (medicine_name,))
        med_data = cursor.fetchone()

        if not med_data:
            connection.close()
            flash("❌ Medicine not found!")
            return redirect(request.url)

        qty_match = re.findall(r'\d+', med_data['quantity'])
        available_qty = int(qty_match[0]) if qty_match else 0

        if available_qty < quantity:
            connection.close()
            flash(f"❌ Only {available_qty} units of {medicine_name} available!")
            return redirect(request.url)

        # Insert sale
        cursor.execute("""
            INSERT INTO sales (patient_name, medicine_name, quantity, total_price)
            VALUES (%s, %s, %s, %s)
        """, (patient_name, medicine_name, str(quantity), total_price))

        # Update stock
        suffix_match = re.findall(r'\D+', med_data['quantity'])
        suffix = suffix_match[0].strip() if suffix_match else ''
        new_qty = available_qty - quantity
        cursor.execute("UPDATE medicines SET quantity=%s WHERE name=%s", (f"{new_qty} {suffix}".strip(), medicine_name))

        connection.commit()
        connection.close()
        flash(f"✅ {quantity} units of {medicine_name} sold to {patient_name}!")
        return redirect('/view_sales')

    return render_template('sell_medicine.html', medicines=medicines)


# 📊 View Sales
@app.route('/view_sales')
def view_sales():
    connection = get_db_connection()
    cursor = connection.cursor()
    selected_date = request.args.get('date')

    if selected_date:
        cursor.execute("SELECT * FROM sales WHERE DATE(sale_date) = %s ORDER BY sale_date DESC", (selected_date,))
    else:
        cursor.execute("SELECT * FROM sales ORDER BY sale_date DESC")

    sales = cursor.fetchall()
    connection.close()
    return render_template('view_sales.html', sales=sales)


# -------------------------
# API endpoints for Sales (used by JS modal)
# -------------------------
@app.route('/api/sale/<int:id>')
def api_get_sale(id):
    conn = get_db_connection()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT * FROM sales WHERE id=%s", (id,))
    sale = cur.fetchone()
    conn.close()
    if not sale:
        return jsonify({'error': 'not found'}), 404
    return jsonify(sale)


@app.route('/api/update_sale/<int:id>', methods=['POST'])
def api_update_sale(id):
    data = request.get_json(force=True)
    patient_name = data.get('patient_name')
    medicine_name = data.get('medicine_name')
    quantity = data.get('quantity')
    total_price = data.get('total_price')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sales 
        SET patient_name=%s, medicine_name=%s, quantity=%s, total_price=%s
        WHERE id=%s
    """, (patient_name, medicine_name, quantity, total_price, id))
    conn.commit()

    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT * FROM sales WHERE id=%s", (id,))
    updated = cur.fetchone()
    conn.close()
    return jsonify(updated)


@app.route('/api/delete_sale/<int:id>', methods=['POST'])
def api_delete_sale(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sales WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'}), 200


# ✏️ Update Sale (page fallback)
@app.route('/update_sale/<int:id>', methods=['GET', 'POST'])
def update_sale(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM sales WHERE id=%s", (id,))
    sale = cursor.fetchone()

    if request.method == 'POST':
        patient_name = request.form['patient_name']
        medicine_name = request.form['medicine_name']
        quantity = request.form['quantity']
        total_price = request.form['total_price']

        cursor.execute("""
            UPDATE sales 
            SET patient_name=%s, medicine_name=%s, quantity=%s, total_price=%s 
            WHERE id=%s
        """, (patient_name, medicine_name, quantity, total_price, id))

        connection.commit()
        connection.close()
        flash(f"✅ Sale record updated!")
        return redirect('/view_sales')

    connection.close()
    return render_template('update_sale.html', sale=sale)


# ❌ Delete Sale (fallback)
@app.route('/delete_sale/<int:id>')
def delete_sale(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM sales WHERE id=%s", (id,))
    connection.commit()
    connection.close()
    flash(f"✅ Sale deleted successfully!")
    return redirect('/view_sales')
    
    


if __name__ == '__main__':
    app.run(debug=True)
