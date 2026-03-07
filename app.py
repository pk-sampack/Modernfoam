import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import urllib.parse
import time
import streamlit.components.v1 as components

# ==========================================
# 1. APP CONFIGURATION & THEME
# ==========================================
st.set_page_config(page_title="Modern Foam Center POS", page_icon="🟩", layout="wide")

st.markdown("""
    <style>
    :root { color-scheme: light; }
    .stApp { background-color: #F8FAF8; }
    [data-testid="stAppViewContainer"] * { color: #222222 !important; }
    h1, h2, h3 { color: #006600 !important; font-family: sans-serif; }
    .stButton>button { background-color: #008000 !important; border-radius: 8px; border: none; font-weight: bold; width: 100%; }
    .stButton>button * { color: white !important; }
    .whatsapp-btn { background-color: #25D366 !important; color: white !important; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: bold; margin-top: 10px; }
    .metric-card { background-color: white !important; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
    </style>
""", unsafe_allow_html=True)

DB_URL = st.secrets.get("DATABASE_URL", "postgresql://postgres.bhtuuwiyncwifnxupgsl:SmwlmGPdChstQmwY@aws-1-ap-south-1.pooler.supabase.com:6543/postgres")

def get_db_connection():
    return psycopg2.connect(DB_URL)

@st.cache_resource
def init_db():
    conn = get_db_connection()
    conn.autocommit = True
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (id SERIAL PRIMARY KEY, item_type TEXT, name TEXT, size TEXT, thickness TEXT, category TEXT, price INTEGER, cost_price INTEGER DEFAULT 0, quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, date TEXT, customer_phone TEXT, total_amount INTEGER, status TEXT DEFAULT 'Completed')''')
    c.execute('''CREATE TABLE IF NOT EXISTS sale_items (id SERIAL PRIMARY KEY, sale_id INTEGER, item_desc TEXT, price INTEGER, cost_price INTEGER DEFAULT 0, qty INTEGER, item_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, date TEXT, description TEXT, amount INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_orders (id SERIAL PRIMARY KEY, date TEXT, supplier TEXT, details TEXT, total_cost INTEGER, status TEXT DEFAULT 'Pending')''')
    c.execute('''CREATE TABLE IF NOT EXISTS po_items (id SERIAL PRIMARY KEY, po_id INTEGER, item_id INTEGER, item_desc TEXT, qty_ordered INTEGER, qty_received INTEGER DEFAULT 0, cost_price INTEGER, sale_price INTEGER)''')
    conn.close()

init_db()

if 'cart' not in st.session_state: st.session_state.cart = []
if 'po_cart' not in st.session_state: st.session_state.po_cart = []

def format_currency(amount): return f"PKR {amount:,.0f}"

st.markdown("""
    <div style="text-align: center; padding-top: 10px; padding-bottom: 20px;">
        <img src="https://raw.githubusercontent.com/pk-sampack/Modernfoam/main/MODERN%20FOAM.png" width="120" style="margin-bottom: 10px;">
        <h1 style="color: #006600 !important; font-size: 2.2rem; margin-top: 0;">Modern Foam Center</h1>
    </div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🛒 POS & Returns", "📦 Inventory", "📝 Purchase Orders", "💸 Accounts", "📊 Admin & Reports"])

# ------------------------------------------
# TAB 1: POS & RETURNS
# ------------------------------------------
with tab1:
    pos_mode = st.radio("Mode", ["New Sale", "Process Return"], horizontal=True)
    if pos_mode == "New Sale":
        st.header("New Cash Sale")
        conn = get_db_connection()
        df_inv = pd.read_sql_query("SELECT * FROM inventory WHERE quantity > 0 ORDER BY name ASC", conn)
        conn.close()
        
        if df_inv.empty:
            st.warning("Inventory is empty.")
        else:
            options = []
            for _, row in df_inv.iterrows():
                if row['item_type'] == 'Mattress': desc = f"{row['name']} | {row['size']} | {row['thickness']}"
                else:
                    size_text = f" | {row['size']}" if row['size'] else ""
                    desc = f"{row['name']}{size_text}"
                options.append(f"ID:{row['id']} - {desc} - {format_currency(row['price'])}")
                
            selected_item_str = st.selectbox("Select Item", options)
            selected_id = int(selected_item_str.split("ID:")[1].split(" - ")[0])
            item_data = df_inv[df_inv['id'] == selected_id].iloc[0]
            
            if item_data['item_type'] == 'Mattress': cart_desc = f"{item_data['name']} | {item_data['size']} | {item_data['thickness']}"
            else: cart_desc = f"{item_data['name']} | {item_data['size']}" if item_data['size'] else item_data['name']
            
            col1, col2 = st.columns([3, 1])
            with col1: qty_to_buy = st.number_input("Quantity", min_value=1, max_value=int(item_data['quantity']), step=1)
            with col2:
                st.write(""); st.write("")
                if st.button("Add to Bill"):
                    st.session_state.cart.append({'id': item_data['id'], 'desc': cart_desc, 'price': item_data['price'], 'cost_price': item_data['cost_price'], 'qty': qty_to_buy, 'total': item_data['price'] * qty_to_buy})
                    st.rerun()

        if st.session_state.cart:
            st.markdown("---")
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df[['desc', 'qty', 'price', 'total']], use_container_width=True)
            grand_total = sum(item['total'] for item in st.session_state.cart)
            
            d_col1, d_col2 = st.columns(2)
            with d_col1: discount_type = st.selectbox("Discount Type", ["Percentage (%)", "Flat Amount (PKR)", "None"], index=0)
            with d_col2: discount_value = 0 if discount_type == "None" else st.number_input("Enter Discount", min_value=0)
            
            if discount_type == "Percentage (%)" and discount_value > 0:
                discount_amount = int(grand_total * (discount_value / 100.0))
                final_total = max(0, grand_total - discount_amount)
                discount_text = f"Discount applied: {discount_value}% (- PKR {discount_amount:,.0f})"
            elif discount_type == "Flat Amount (PKR)" and discount_value > 0:
                final_total = max(0, grand_total - discount_value)
                discount_text = f"Discount applied: - PKR {discount_value:,.0f}"
            else:
                final_total = grand_total
                discount_text = ""

            st.markdown(f"<h3 style='color:#006600;'>Grand Total: {format_currency(final_total)}</h3>", unsafe_allow_html=True)
            cust_phone = st.text_input("Customer Phone (Optional, format: 923XXXXXXXXX)")
            
            if st.button("Complete Cash Sale"):
                conn = get_db_connection()
                c = conn.cursor()
                date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO sales (date, customer_phone, total_amount) VALUES (%s, %s, %s) RETURNING id", (date_now, cust_phone, int(final_total)))
                sale_id = c.fetchone()[0]
                
                receipt_items_text = ""
                for item in st.session_state.cart:
                    c.execute("INSERT INTO sale_items (sale_id, item_desc, price, cost_price, qty, item_id) VALUES (%s, %s, %s, %s, %s, %s)", (int(sale_id), item['desc'], int(item['price']), int(item['cost_price']), int(item['qty']), int(item['id'])))
                    c.execute("UPDATE inventory SET quantity = quantity - %s WHERE id = %s", (int(item['qty']), int(item['id'])))
                    receipt_items_text += f"- {item['qty']}x {item['desc']}\n"
                    
                conn.commit()
                conn.close()
                st.session_state.cart = []
                
                wa_text = f"*Modern Foam Center Receipt*\n\nItems:\n{receipt_items_text}\n"
                if discount_type != "None" and discount_value > 0: wa_text += f"Subtotal: {format_currency(grand_total)}\n{discount_text}\n"
                wa_text += f"*Total: {format_currency(final_total)}*\nPayment: Cash\n\nThank you for your purchase!"
                encoded_text = urllib.parse.quote(wa_text)
                wa_link = f"https://wa.me/{cust_phone}?text={encoded_text}" if cust_phone else f"https://wa.me/?text={encoded_text}"
                
                st.success(f"Sale #{sale_id} Completed Successfully!")
                st.markdown(f'<a href="{wa_link}" target="_blank" class="whatsapp-btn">📱 Send WhatsApp / SMS Receipt</a>', unsafe_allow_html=True)
                if st.button("Start Next Sale"): st.rerun()

    elif pos_mode == "Process Return":
        st.header("🔄 Return Item")
        sale_id_to_return = st.number_input("Enter Sale ID to Return", min_value=1, step=1)
        if st.button("Find Sale"):
            conn = get_db_connection()
            df_sale = pd.read_sql_query(f"SELECT * FROM sale_items WHERE sale_id = {sale_id_to_return}", conn)
            conn.close()
            if not df_sale.empty:
                st.dataframe(df_sale)
                st.warning("Returning this sale will restock the items and deduct from today's cash.")
                if st.button("Confirm Return"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    for _, row in df_sale.iterrows():
                        c.execute("UPDATE inventory SET quantity = quantity + %s WHERE id = %s", (int(row['qty']), int(row['item_id'])))
                    c.execute("UPDATE sales SET status = 'Returned', total_amount = 0 WHERE id = %s", (int(sale_id_to_return),))
                    conn.commit()
                    conn.close()
                    st.success("Return Processed successfully!")
            else:
                st.error("Sale not found.")

# ------------------------------------------
# TAB 2: INVENTORY 
# ------------------------------------------
with tab2:
    st.header("📦 Inventory Management")
    with st.expander("➕ Add New Item"):
        with st.form("add_inv"):
            type_val = st.radio("Type", ["Mattress", "Other Item"])
            name = st.text_input("Name")
            col_s1, col_s2 = st.columns(2)
            with col_s1: size_choice = st.selectbox("Standard Size", ["78x72 (King)", "78x66 (Queen)",  "78x60 (Queen1)", "78x42 (Single)", "72x36 (U)", "22x22 (U)", "22x18 (U)", "18x18 (U)", "72x36 (Single TF)", "Custom"])
            with col_s2: 
                if size_choice == "Custom": size = st.text_input("Type Custom Size (e.g. 72x36)", key="cust_size")
                else: size = size_choice

            thick = st.selectbox("Thickness", ["0.5 inch","0.8 inch","1 inch","1.5 inch","2 inch","3 inch","4 inch", "5 inch", "6 inch", "8 inch", "10 inch", "N/A"]) if type_val == "Mattress" else ""
            cat = st.selectbox("Category", ["Covered", "Uncovered"]) if type_val == "Mattress" else ""
            c1, c2, c3 = st.columns(3)
            with c1: cost = st.number_input("Cost Price", min_value=0)
            with c2: price = st.number_input("Selling Price", min_value=0)
            with c3: qty = st.number_input("Qty", min_value=0)
            
            if st.form_submit_button("Save"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO inventory (item_type, name, size, thickness, category, price, cost_price, quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (type_val, name, size, thick, cat, int(price), int(cost), int(qty)))
                conn.commit()
                conn.close()
                st.success("Item Added!")
                st.rerun()

    conn = get_db_connection()
    st.dataframe(pd.read_sql_query("SELECT id, name, size, thickness, price, quantity FROM inventory ORDER BY id DESC", conn), hide_index=True, use_container_width=True)
    conn.close()

# ------------------------------------------
# TAB 3: ADVANCED PURCHASE ORDERS 
# ------------------------------------------
with tab3:
    st.header("📝 Purchase Order Management")
    po_action = st.radio("Action", ["➕ Create New PO", "📥 Receive PO Items", "⚙️ Manage POs (Edit/Delete)", "🖨️ Print PO"], horizontal=True)
    
    if po_action == "➕ Create New PO":
        supplier = st.text_input("Supplier/Factory Name (e.g., Diamond Foam Factory)")
        conn = get_db_connection()
        df_all_inv = pd.read_sql_query("SELECT * FROM inventory ORDER BY name ASC", conn)
        conn.close()
        
        # ADDED SAFETY NET: Checks if inventory is completely empty before trying to load dropdown
        if df_all_inv.empty:
            st.warning("⚠️ Your inventory is currently empty! Please go to the '📦 Inventory' tab or upload your CSV to add items before creating a Purchase Order.")
        else:
            st.subheader("Add Items to Order")
            inv_options = []
            for _, row in df_all_inv.iterrows():
                opt_str = f"ID:{row['id']} - {row['name']}"
                if row['size']: opt_str += f" | {row['size']}"
                if row['thickness']: opt_str += f" | {row['thickness']}"
                inv_options.append(opt_str)
                
            selected_po_item_str = st.selectbox("Select Item", inv_options)
            po_selected_id = int(selected_po_item_str.split("ID:")[1].split(" -")[0])
            po_item_data = df_all_inv[df_all_inv['id'] == po_selected_id].iloc[0]
            
            po_desc = f"{po_item_data['name']}"
            if po_item_data['size']: po_desc += f" | {po_item_data['size']}"
            if po_item_data['thickness']: po_desc += f" | {po_item_data['thickness']}"

            col_q, col_c, col_p = st.columns(3)
            with col_q: po_qty = st.number_input("Qty to Order", min_value=1, value=10)
            with col_c: po_cost = st.number_input("Factory Cost Price (Per Unit)", min_value=0, value=int(po_item_data['cost_price']))
            with col_p: po_sale = st.number_input("Target Sale Price (Per Unit)", min_value=0, value=int(po_item_data['price']))
            
            if st.button("Add to Order"):
                st.session_state.po_cart.append({'item_id': po_item_data['id'], 'desc': po_desc, 'qty': po_qty, 'cost': po_cost, 'sale': po_sale, 'total': po_qty * po_cost})
                st.rerun()

            if st.session_state.po_cart:
                st.markdown("---")
                po_cart_df = pd.DataFrame(st.session_state.po_cart)
                st.dataframe(po_cart_df[['desc', 'qty', 'cost', 'sale', 'total']], use_container_width=True)
                po_grand_total = sum(item['total'] for item in st.session_state.po_cart)
                st.subheader(f"Total Order Est. Cost: {format_currency(po_grand_total)}")
                
                if st.button("Submit Purchase Order"):
                    if not supplier: st.error("Please enter a supplier name.")
                    else:
                        conn = get_db_connection()
                        c = conn.cursor()
                        date_now = datetime.now().strftime("%Y-%m-%d")
                        c.execute("INSERT INTO purchase_orders (date, supplier, details, total_cost, status) VALUES (%s, %s, %s, %s, %s) RETURNING id", (date_now, supplier, "Structured PO", int(po_grand_total), "Pending"))
                        new_po_id = c.fetchone()[0]
                        for item in st.session_state.po_cart:
                            c.execute("INSERT INTO po_items (po_id, item_id, item_desc, qty_ordered, cost_price, sale_price) VALUES (%s, %s, %s, %s, %s, %s)", (int(new_po_id), int(item['item_id']), item['desc'], int(item['qty']), int(item['cost']), int(item['sale'])))
                        conn.commit()
                        conn.close()
                        st.session_state.po_cart = []
                        st.success(f"✅ Purchase Order #{new_po_id} Generated Successfully!")
                        time.sleep(1.5)
                        st.rerun()

    elif po_action == "📥 Receive PO Items":
        conn = get_db_connection()
        df_pending_pos = pd.read_sql_query("SELECT * FROM purchase_orders WHERE status != 'Completed' ORDER BY id DESC", conn)
        if df_pending_pos.empty: st.info("No pending purchase orders available to receive.")
        else:
            po_list = [f"PO #{row['id']} - {row['supplier']} ({row['status']})" for _, row in df_pending_pos.iterrows()]
            selected_recv_str = st.selectbox("Select Purchase Order to Receive", po_list)
            recv_po_id = int(selected_recv_str.split("PO #")[1].split(" -")[0])
            df_po_items = pd.read_sql_query(f"SELECT * FROM po_items WHERE po_id = {recv_po_id}", conn)
            
            if df_po_items.empty:
                st.warning("This is a legacy PO. Manual inventory updates are required.")
                if st.button("Mark Legacy PO as Completed"):
                    c = conn.cursor()
                    c.execute("UPDATE purchase_orders SET status = 'Completed' WHERE id = %s", (recv_po_id,))
                    conn.commit()
                    st.rerun()
            else:
                st.subheader("Items to Receive")
                with st.form("receive_po_form"):
                    receive_data = {}
                    for _, row in df_po_items.iterrows():
                        remaining = int(row['qty_ordered'] - row['qty_received'])
                        if remaining > 0:
                            st.write(f"**{row['item_desc']}** (Ordered: {row['qty_ordered']} | Received: {row['qty_received']})")
                            recv_qty = st.number_input(f"Receive Now", min_value=0, max_value=remaining, value=remaining, key=f"recv_{row['id']}")
                            receive_data[row['id']] = {'item_id': row['item_id'], 'qty_to_recv': recv_qty, 'cost': row['cost_price'], 'sale': row['sale_price']}
                            st.markdown("---")
                            
                    if st.form_submit_button("Process Received Items"):
                        c = conn.cursor()
                        total_received_updates = 0
                        for po_item_id, data in receive_data.items():
                            if data['qty_to_recv'] > 0:
                                total_received_updates += data['qty_to_recv']
                                c.execute("UPDATE po_items SET qty_received = qty_received + %s WHERE id = %s", (int(data['qty_to_recv']), int(po_item_id)))
                                c.execute("UPDATE inventory SET quantity = quantity + %s, cost_price = %s, price = %s WHERE id = %s", (int(data['qty_to_recv']), int(data['cost']), int(data['sale']), int(data['item_id'])))
                        
                        c.execute("SELECT SUM(qty_ordered), SUM(qty_received) FROM po_items WHERE po_id = %s", (recv_po_id,))
                        sums = c.fetchone()
                        if sums[0] == sums[1]: c.execute("UPDATE purchase_orders SET status = 'Completed' WHERE id = %s", (recv_po_id,))
                        elif total_received_updates > 0: c.execute("UPDATE purchase_orders SET status = 'Partially Received' WHERE id = %s", (recv_po_id,))
                        conn.commit()
                        st.success("✅ Inventory restocked and PO updated!")
                        time.sleep(1.5)
                        st.rerun()
        conn.close()

    elif po_action == "⚙️ Manage POs (Edit/Delete)":
        conn = get_db_connection()
        df_all_pos = pd.read_sql_query("SELECT * FROM purchase_orders ORDER BY id DESC", conn)
        if df_all_pos.empty: st.info("No purchase orders found in the system.")
        else:
            po_list = [f"PO #{row['id']} - {row['supplier']} ({row['status']})" for _, row in df_all_pos.iterrows()]
            selected_manage_str = st.selectbox("Select Purchase Order to Manage", po_list)
            manage_po_id = int(selected_manage_str.split("PO #")[1].split(" -")[0])
            
            po_data = df_all_pos[df_all_pos['id'] == manage_po_id].iloc[0]
            df_po_items = pd.read_sql_query(f"SELECT * FROM po_items WHERE po_id = {manage_po_id}", conn)
            
            st.markdown("---")
            col_supp, col_del = st.columns([3,1])
            with col_supp:
                new_supplier = st.text_input("Supplier Name", value=po_data['supplier'])
            with col_del:
                st.write("")
                st.write("")
                if st.button(f"🚨 Delete PO #{manage_po_id} Permanently"):
                    c = conn.cursor()
                    c.execute("DELETE FROM po_items WHERE po_id = %s", (manage_po_id,))
                    c.execute("DELETE FROM purchase_orders WHERE id = %s", (manage_po_id,))
                    conn.commit()
                    st.success(f"PO #{manage_po_id} Deleted.")
                    time.sleep(1.5)
                    st.rerun()

            if not df_po_items.empty:
                st.subheader("Edit Items")
                st.info("Note: You cannot lower the ordered quantity below what has already been received.")
                with st.form("edit_po_form"):
                    updated_items = {}
                    for _, row in df_po_items.iterrows():
                        st.markdown(f"**{row['item_desc']}** (Already Received: {row['qty_received']})")
                        c_qty, c_cost, c_sale = st.columns(3)
                        with c_qty: new_qty = st.number_input("Qty Ordered", min_value=int(row['qty_received']), value=int(row['qty_ordered']), key=f"eqty_{row['id']}")
                        with c_cost: new_cost = st.number_input("Unit Cost", min_value=0, value=int(row['cost_price']), key=f"ecost_{row['id']}")
                        with c_sale: new_sale = st.number_input("Sale Price", min_value=0, value=int(row['sale_price']), key=f"esale_{row['id']}")
                        updated_items[row['id']] = {'qty': new_qty, 'cost': new_cost, 'sale': new_sale}
                        
                    if st.form_submit_button("Save PO Changes"):
                        c = conn.cursor()
                        total_po_cost = 0
                        for item_id, vals in updated_items.items():
                            c.execute("UPDATE po_items SET qty_ordered=%s, cost_price=%s, sale_price=%s WHERE id=%s", (vals['qty'], vals['cost'], vals['sale'], item_id))
                            total_po_cost += (vals['qty'] * vals['cost'])
                        c.execute("UPDATE purchase_orders SET supplier=%s, total_cost=%s WHERE id=%s", (new_supplier, total_po_cost, manage_po_id))
                        conn.commit()
                        st.success("PO Updated Successfully!")
                        time.sleep(1.5)
                        st.rerun()
            else:
                st.warning("This is a legacy PO without structured items.")
                with st.form("legacy_edit"):
                    new_legacy_details = st.text_area("Details", value=po_data['details'])
                    new_legacy_cost = st.number_input("Total Cost", value=int(po_data['total_cost']))
                    if st.form_submit_button("Update Legacy PO"):
                        c = conn.cursor()
                        c.execute("UPDATE purchase_orders SET supplier=%s, details=%s, total_cost=%s WHERE id=%s", (new_supplier, new_legacy_details, new_legacy_cost, manage_po_id))
                        conn.commit()
                        st.success("Legacy PO Updated!")
                        time.sleep(1.5)
                        st.rerun()
        conn.close()

    elif po_action == "🖨️ Print PO":
        conn = get_db_connection()
        df_all_pos = pd.read_sql_query("SELECT * FROM purchase_orders ORDER BY id DESC", conn)
        
        if not df_all_pos.empty:
            po_print_list = [f"PO #{row['id']} - {row['supplier']} - {row['date']}" for _, row in df_all_pos.iterrows()]
            selected_print_str = st.selectbox("Select PO to Print", po_print_list)
            print_po_id = int(selected_print_str.split("PO #")[1].split(" -")[0])
            df_print_items = pd.read_sql_query(f"SELECT * FROM po_items WHERE po_id = {print_po_id}", conn)
            po_data = df_all_pos[df_all_pos['id'] == print_po_id].iloc[0]
            
            print_html = f"""
            <html>
            <head>
            <style>
                body {{ font-family: sans-serif; padding: 20px; color: black; background: white; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .header-box {{ text-align: center; margin-bottom: 20px; }}
                .info-box {{ margin-bottom: 20px; font-size: 15px; }}
                @media print {{ .no-print {{ display: none; }} body {{ padding: 0; }} }}
            </style>
            </head>
            <body>
                <button class="no-print" onclick="window.print()" style="background:#008000; color:white; padding:15px; border:none; border-radius:8px; cursor:pointer; width:100%; font-size:18px; font-weight:bold; margin-bottom:20px;">🖨️ Click Here to Print Order</button>
                <div class="header-box">
                    <h2 style="color: #006600; margin-bottom: 5px; font-size: 28px;">MODERN FOAM CENTER</h2>
                    <h3 style="margin-top: 0; color: #333; font-size: 20px;">PURCHASE ORDER</h3>
                </div>
                <div class="info-box">
                    <strong>PO Number:</strong> #{po_data['id']}<br>
                    <strong>Date:</strong> {po_data['date']}<br>
                    <strong>Supplier:</strong> {po_data['supplier']}<br>
                    <strong>Status:</strong> {po_data['status']}
                </div>
                <table>
                    <tr><th>Description</th><th>Qty Ordered</th><th>Unit Cost (PKR)</th><th>Total Cost (PKR)</th></tr>
            """
            
            if not df_print_items.empty:
                for _, item in df_print_items.iterrows():
                    row_total = int(item['qty_ordered'] * item['cost_price'])
                    print_html += f"<tr><td>{item['item_desc']}</td><td>{item['qty_ordered']}</td><td>{int(item['cost_price'])}</td><td>{row_total}</td></tr>"
            else:
                legacy_details = str(po_data['details']).replace('\n', '<br>')
                print_html += f"<tr><td colspan='4' style='line-height: 1.8;'>{legacy_details}</td></tr>"
                
            print_html += f"""
                </table>
                <h3 style="text-align: right; margin-top: 20px; font-size: 18px;">Total Estimated Cost: {format_currency(int(po_data['total_cost']))}</h3>
            </body>
            </html>
            """
            components.html(print_html, height=700, scrolling=True)
        conn.close()

# ------------------------------------------
# TAB 4: ACCOUNTS 
# ------------------------------------------
with tab4:
    st.header("💸 Daily Expenses")
    desc = st.text_input("Expense Description (e.g. Electric Bill, Lunch)")
    amt = st.number_input("Amount (PKR)", min_value=0)
    if st.button("Record Expense") and desc:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO expenses (date, description, amount) VALUES (%s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), desc, int(amt)))
        conn.commit()
        conn.close()
        st.success("Saved!")
    conn = get_db_connection()
    st.dataframe(pd.read_sql_query("SELECT * FROM expenses ORDER BY id DESC LIMIT 20", conn), use_container_width=True)
    conn.close()

# ------------------------------------------
# TAB 5: ADMIN / CLOSING & INVENTORY EDIT
# ------------------------------------------
with tab5:
    st.header("📊 Admin, P&L & Reports")
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    
    rev = pd.read_sql_query("SELECT COALESCE(SUM(total_amount), 0) as t FROM sales WHERE date LIKE %s AND status='Completed'", conn, params=(today_str+'%',)).iloc[0]['t']
    cogs = pd.read_sql_query("SELECT COALESCE(SUM(si.qty * si.cost_price), 0) as c FROM sale_items si JOIN sales s ON si.sale_id = s.id WHERE s.date LIKE %s AND s.status='Completed'", conn, params=(today_str+'%',)).iloc[0]['c']
    exp = pd.read_sql_query("SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE date LIKE %s", conn, params=(today_str+'%',)).iloc[0]['e']
    net = rev - cogs - exp
    
    val_query = pd.read_sql_query("SELECT COALESCE(SUM(quantity * cost_price), 0) as total_cost, COALESCE(SUM(quantity * price), 0) as total_retail FROM inventory WHERE quantity > 0", conn).iloc[0]
    total_stock_cost = val_query['total_cost']
    total_stock_retail = val_query['total_retail']
    
    colA, colB, colC = st.columns(3)
    colA.metric("Today's Cash (Revenue)", format_currency(int(rev)))
    colB.metric("Today's Expenses", format_currency(int(exp)))
    colC.metric("Net Profit Today", format_currency(int(net)))
    
    st.markdown("<br>", unsafe_allow_html=True)
    colD, colE = st.columns(2)
    colD.markdown(f"<div class='metric-card'><h4>📦 Total Inventory Value (At Cost)</h4><h2 style='color:#008000;'>{format_currency(int(total_stock_cost))}</h2></div>", unsafe_allow_html=True)
    colE.markdown(f"<div class='metric-card'><h4>🏷️ Total Inventory Value (At Retail)</h4><h2>{format_currency(int(total_stock_retail))}</h2></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.expander("🛠️ Admin Controls (Password Required)"):
        pwd = st.text_input("Admin Password", type="password")
        if pwd == "admin123":
            st.success("Admin Access Granted.")
            
            st.subheader("🗑️ Edit/Delete Today's Sales")
            df_todays_sales = pd.read_sql_query("SELECT * FROM sales WHERE date LIKE %s", conn, params=(today_str+'%',))
            st.dataframe(df_todays_sales)
            
            del_id = st.number_input("Enter Sale ID to permanently DELETE", min_value=0)
            if st.button("Delete Sale"):
                if del_id > 0:
                    c = conn.cursor()
                    c.execute("SELECT item_id, qty FROM sale_items WHERE sale_id=%s", (int(del_id),))
                    items_to_restock = c.fetchall()
                    if items_to_restock:
                        for row in items_to_restock: c.execute("UPDATE inventory SET quantity = quantity + %s WHERE id = %s", (int(row[1]), int(row[0])))
                        c.execute("DELETE FROM sale_items WHERE sale_id=%s", (int(del_id),))
                        c.execute("DELETE FROM sales WHERE id=%s", (int(del_id),))
                        conn.commit()
                        st.success(f"✅ Sale #{del_id} deleted and items restocked!")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error(f"⚠️ Sale #{del_id} not found. It may have already been deleted!")
                else: st.warning("Please enter a valid Sale ID.")
            
            st.markdown("---")
            
            st.subheader("📈 Bulk Price Adjustment")
            with st.form("bulk_price_form"):
                adj_target = st.selectbox("What do you want to update?", ["Both Cost & Selling Price", "Only Selling Price", "Only Cost Price"])
                adj_type = st.selectbox("Adjustment Type", ["Percentage (%)", "Fixed Amount (PKR)"])
                adj_value = st.number_input("Adjustment Value (Use negative numbers to decrease price)", value=0.0)
                
                if st.form_submit_button("Apply Bulk Update to All Items"):
                    if adj_value != 0:
                        c = conn.cursor()
                        cols_to_update = []
                        if adj_target in ["Both Cost & Selling Price", "Only Cost Price"]: cols_to_update.append("cost_price")
                        if adj_target in ["Both Cost & Selling Price", "Only Selling Price"]: cols_to_update.append("price")
                            
                        for col in cols_to_update:
                            if col == "price":
                                if adj_type == "Percentage (%)":
                                    query = f"UPDATE inventory SET {col} = GREATEST(0, CAST(ROUND(({col} + ({col} * %s / 100.0)) / 10.0) * 10 AS INTEGER))"
                                else:
                                    query = f"UPDATE inventory SET {col} = GREATEST(0, CAST(ROUND(({col} + %s) / 10.0) * 10 AS INTEGER))"
                            else:
                                if adj_type == "Percentage (%)":
                                    query = f"UPDATE inventory SET {col} = GREATEST(0, CAST({col} + ({col} * %s / 100.0) AS INTEGER))"
                                else:
                                    query = f"UPDATE inventory SET {col} = GREATEST(0, CAST({col} + %s AS INTEGER))"
                            
                            c.execute(query, (adj_value,))
                            
                        conn.commit()
                        st.success(f"✅ Successfully updated {adj_target}!")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.error("Please enter a value other than 0.")

            st.markdown("---")
            
            st.subheader("📁 CSV Bulk Export / Import")
            st.write("Download your entire inventory, make changes in Excel, and upload it back to update everything at once.")
            
            df_inv_export = pd.read_sql_query("SELECT * FROM inventory ORDER BY id ASC", conn)
            csv_data = df_inv_export.to_csv(index=False).encode('utf-8')
            st.download_button(label="⬇️ Download Inventory (CSV)", data=csv_data, file_name=f"modern_foam_inventory_{today_str}.csv", mime="text/csv")
            
            uploaded_file = st.file_uploader("⬆️ Upload Modified CSV to Update Inventory", type=["csv"])
            if uploaded_file is not None:
                if st.button("Process CSV Update"):
                    try:
                        df_upload = pd.read_csv(uploaded_file)
                        df_upload.fillna({'item_type': '', 'name': '', 'size': '', 'thickness': '', 'category': '', 'cost_price': 0, 'price': 0, 'quantity': 0}, inplace=True)
                        c = conn.cursor()
                        for _, row in df_upload.iterrows():
                            item_id = row.get('id')
                            if pd.notna(item_id) and str(item_id).strip() != "":
                                c.execute('''UPDATE inventory SET item_type=%s, name=%s, size=%s, thickness=%s, category=%s, price=%s, cost_price=%s, quantity=%s WHERE id=%s''', (str(row['item_type']), str(row['name']), str(row['size']), str(row['thickness']), str(row['category']), int(row['price']), int(row['cost_price']), int(row['quantity']), int(item_id)))
                            else:
                                c.execute('''INSERT INTO inventory (item_type, name, size, thickness, category, price, cost_price, quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (str(row['item_type']), str(row['name']), str(row['size']), str(row['thickness']), str(row['category']), int(row['price']), int(row['cost_price']), int(row['quantity'])))
                        conn.commit()
                        st.success("✅ Inventory successfully updated from CSV!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error processing CSV. Please ensure you haven't renamed any column headers. Detail: {e}")

            st.markdown("---")
            
            st.subheader("✏️ Edit or Delete Single Inventory Item")
            df_inv_admin = pd.read_sql_query("SELECT * FROM inventory ORDER BY id DESC", conn)
            
            if not df_inv_admin.empty:
                inv_edit_options = []
                for _, row in df_inv_admin.iterrows():
                    opt_str = f"ID: {row['id']} | {row['name']}"
                    if row['size']: opt_str += f" | {row['size']}"
                    if row['thickness']: opt_str += f" | {row['thickness']}"
                    inv_edit_options.append(opt_str)
                    
                selected_edit_str = st.selectbox("Select Item to Edit/Delete", inv_edit_options)
                selected_edit_id = int(selected_edit_str.split("ID: ")[1].split(" |")[0])
                item_to_edit = df_inv_admin[df_inv_admin['id'] == selected_edit_id].iloc[0]
                
                with st.form("edit_inventory_form"):
                    edit_name = st.text_input("Name", value=item_to_edit['name'])
                    edit_size = st.text_input("Size", value=item_to_edit['size'] if item_to_edit['size'] else "")
                    c_cost, c_price, c_qty = st.columns(3)
                    with c_cost: edit_cost = st.number_input("Cost Price", value=int(item_to_edit['cost_price']), min_value=0)
                    with c_price: edit_price = st.number_input("Selling Price", value=int(item_to_edit['price']), min_value=0)
                    with c_qty: edit_qty = st.number_input("Current Quantity", value=int(item_to_edit['quantity']), min_value=0)
                    
                    if st.form_submit_button("Update Item"):
                        c = conn.cursor()
                        c.execute('''UPDATE inventory SET name=%s, size=%s, cost_price=%s, price=%s, quantity=%s WHERE id=%s''', (edit_name, edit_size, int(edit_cost), int(edit_price), int(edit_qty), int(selected_edit_id)))
                        conn.commit()
                        st.success(f"✅ Item updated successfully!")
                        time.sleep(1.5)
                        st.rerun()
                        
                st.write("")
                if st.button(f"🚨 Delete '{item_to_edit['name']}' Permanently"):
                    c = conn.cursor()
                    c.execute("DELETE FROM inventory WHERE id=%s", (int(selected_edit_id),))
                    conn.commit()
                    st.success("✅ Item permanently deleted from inventory.")
                    time.sleep(1.5)
                    st.rerun()
            else: st.info("Inventory is currently empty.")
                
        elif pwd != "":
            st.error("Incorrect Password")
            
    conn.close()
