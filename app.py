import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import urllib.parse

# ==========================================
# 1. APP CONFIGURATION & THEME
# ==========================================
st.set_page_config(page_title="Modern Foam Center POS", page_icon="🟩", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAF8; }
    h1, h2, h3 { color: #006600; font-family: sans-serif; }
    .stButton>button { background-color: #008000; color: white; border-radius: 8px; border: none; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #005500; color: white; }
    .whatsapp-btn { background-color: #25D366; color: white; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: bold; margin-top: 10px; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SETUP (SUPABASE / POSTGRESQL)
# ==========================================
# Using st.secrets is the safe way for GitHub. The second URL is your fallback.
postgresql://postgres.bhtuuwiyncwifnxupgsl:SmwlmGPdChstQmwY@aws-1-ap-south-1.pooler.supabase.com:6543/postgres

def get_db_connection():
    return psycopg2.connect(DB_URL)

@st.cache_resource
def init_db():
    conn = get_db_connection()
    conn.autocommit = True # Safe mode for schema creation in Postgres
    c = conn.cursor()
    # Postgres uses SERIAL instead of AUTOINCREMENT
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (id SERIAL PRIMARY KEY, item_type TEXT, name TEXT, size TEXT, thickness TEXT, category TEXT, price INTEGER, cost_price INTEGER DEFAULT 0, quantity INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales (id SERIAL PRIMARY KEY, date TEXT, customer_phone TEXT, total_amount INTEGER, status TEXT DEFAULT 'Completed')''')
    c.execute('''CREATE TABLE IF NOT EXISTS sale_items (id SERIAL PRIMARY KEY, sale_id INTEGER, item_desc TEXT, price INTEGER, cost_price INTEGER DEFAULT 0, qty INTEGER, item_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, date TEXT, description TEXT, amount INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_orders (id SERIAL PRIMARY KEY, date TEXT, supplier TEXT, details TEXT, total_cost INTEGER, status TEXT DEFAULT 'Pending')''')
    conn.close()

init_db()

if 'cart' not in st.session_state: st.session_state.cart = []

def format_currency(amount): return f"PKR {amount:,.0f}"

# ==========================================
# 3. MAIN UI
# ==========================================
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Flag_of_Pakistan.svg/100px-Flag_of_Pakistan.svg.png", width=60)
st.title("🟩 Modern Foam Center")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🛒 POS & Returns", "📦 Inventory", "📝 Purchase Orders", "💸 Accounts", "📊 Admin & Reports"])

# ------------------------------------------
# TAB 1: POS & RETURNS (WITH WHATSAPP)
# ------------------------------------------
with tab1:
    pos_mode = st.radio("Mode", ["New Sale", "Process Return"], horizontal=True)
    
    if pos_mode == "New Sale":
        st.header("New Cash Sale")
        conn = get_db_connection()
        df_inv = pd.read_sql_query("SELECT * FROM inventory WHERE quantity > 0", conn)
        conn.close()
        
        if df_inv.empty:
            st.warning("Inventory is empty.")
        else:
            options = []
            for _, row in df_inv.iterrows():
                desc = f"{row['name']} | {row['size']}" if row['item_type'] == 'Mattress' else row['name']
                options.append(f"ID:{row['id']} - {desc} - {format_currency(row['price'])}")
                
            selected_item_str = st.selectbox("Select Item", options)
            selected_id = int(selected_item_str.split("ID:")[1].split(" - ")[0])
            item_data = df_inv[df_inv['id'] == selected_id].iloc[0]
            
            col1, col2 = st.columns([3, 1])
            with col1: qty_to_buy = st.number_input("Quantity", min_value=1, max_value=int(item_data['quantity']), step=1)
            with col2:
                st.write("")
                st.write("")
                if st.button("Add to Bill"):
                    st.session_state.cart.append({
                        'id': item_data['id'], 'desc': item_data['name'], 
                        'price': item_data['price'], 'cost_price': item_data['cost_price'],
                        'qty': qty_to_buy, 'total': item_data['price'] * qty_to_buy
                    })
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
                # Postgres requires RETURNING id to get the ID back
                c.execute("INSERT INTO sales (date, customer_phone, total_amount) VALUES (%s, %s, %s) RETURNING id", (date_now, cust_phone, final_total))
                sale_id = c.fetchone()[0]
                
                receipt_items_text = ""
                for item in st.session_state.cart:
                    c.execute("INSERT INTO sale_items (sale_id, item_desc, price, cost_price, qty, item_id) VALUES (%s, %s, %s, %s, %s, %s)",
                              (sale_id, item['desc'], item['price'], item['cost_price'], item['qty'], item['id']))
                    c.execute("UPDATE inventory SET quantity = quantity - %s WHERE id = %s", (item['qty'], item['id']))
                    receipt_items_text += f"- {item['qty']}x {item['desc']}\n"
                    
                conn.commit()
                conn.close()
                st.session_state.cart = []
                
                # WHATSAPP RESTORED
                wa_text = f"*Modern Foam Center Receipt*\n\nItems:\n{receipt_items_text}\n"
                if discount_type != "None" and discount_value > 0:
                    wa_text += f"Subtotal: {format_currency(grand_total)}\n{discount_text}\n"
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
                        c.execute("UPDATE inventory SET quantity = quantity + %s WHERE id = %s", (row['qty'], row['item_id']))
                    c.execute("UPDATE sales SET status = 'Returned', total_amount = 0 WHERE id = %s", (sale_id_to_return,))
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
            with col_s1: size_choice = st.selectbox("Standard Size", ["78x72 (King)", "78x60 (Queen)", "78x42 (Single)", "Custom"])
            with col_s2: 
                if size_choice == "Custom": size = st.text_input("Type Custom Size (e.g. 72x36)", key="cust_size")
                else: size = size_choice

            thick = st.selectbox("Thickness", ["4 inch", "5 inch", "6 inch", "8 inch", "10 inch", "N/A"]) if type_val == "Mattress" else ""
            cat = st.selectbox("Category", ["Covered", "Uncovered"]) if type_val == "Mattress" else ""
            
            c1, c2, c3 = st.columns(3)
            with c1: cost = st.number_input("Cost Price", min_value=0)
            with c2: price = st.number_input("Selling Price", min_value=0)
            with c3: qty = st.number_input("Qty", min_value=0)
            
            if st.form_submit_button("Save"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO inventory (item_type, name, size, thickness, category, price, cost_price, quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (type_val, name, size, thick, cat, price, cost, qty))
                conn.commit()
                conn.close()
                st.success("Item Added!")
                st.rerun()

    conn = get_db_connection()
    st.dataframe(pd.read_sql_query("SELECT id, name, size, thickness, price, quantity FROM inventory ORDER BY id DESC", conn), hide_index=True, use_container_width=True)
    conn.close()

# ------------------------------------------
# TAB 3: PURCHASE ORDERS (UPDATED WITH INVENTORY SELECTOR)
# ------------------------------------------
with tab3:
    st.header("📝 Create Purchase Order")
    supplier = st.text_input("Supplier/Factory Name (e.g., Diamond Foam Factory)")
    
    # NEW: Fetch existing items to select from
    conn = get_db_connection()
    df_all_inv = pd.read_sql_query("SELECT name, size FROM inventory", conn)
    conn.close()
    
    inv_options = []
    for _, row in df_all_inv.iterrows():
        opt = f"{row['name']} - {row['size']}" if row['size'] else f"{row['name']}"
        inv_options.append(opt)
        
    selected_po_items = st.multiselect("Select items to restock from Inventory", list(set(inv_options)))
    
    # Combine selected items into the text area
    default_po_text = ""
    for item in selected_po_items:
        default_po_text += f"- 10x {item}\n"
        
    po_details = st.text_area("Order Details (Edit quantities as needed)", value=default_po_text, height=150)
    po_cost = st.number_input("Estimated Total Cost (PKR)", min_value=0)
    
    if st.button("Save Purchase Order"):
        conn = get_db_connection()
        c = conn.cursor()
        date_now = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO purchase_orders (date, supplier, details, total_cost) VALUES (%s, %s, %s, %s)", (date_now, supplier, po_details, po_cost))
        conn.commit()
        conn.close()
        st.success("Purchase Order Saved!")
        
    st.subheader("Past Purchase Orders")
    conn = get_db_connection()
    st.dataframe(pd.read_sql_query("SELECT * FROM purchase_orders ORDER BY id DESC", conn), use_container_width=True)
    conn.close()

# ------------------------------------------
# TAB 4: ACCOUNTS & TAB 5: ADMIN / CLOSING
# ------------------------------------------
with tab4:
    st.header("💸 Daily Expenses")
    desc = st.text_input("Expense Description (e.g. Electric Bill, Lunch)")
    amt = st.number_input("Amount (PKR)", min_value=0)
    if st.button("Record Expense") and desc:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO expenses (date, description, amount) VALUES (%s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), desc, amt))
        conn.commit()
        conn.close()
        st.success("Saved!")
    conn = get_db_connection()
    st.dataframe(pd.read_sql_query("SELECT * FROM expenses ORDER BY id DESC LIMIT 20", conn), use_container_width=True)
    conn.close()

with tab5:
    st.header("📊 Admin, P&L & Reports")
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    # Postgres uses COALESCE instead of IFNULL
    rev = pd.read_sql_query("SELECT COALESCE(SUM(total_amount), 0) as t FROM sales WHERE date LIKE %s AND status='Completed'", conn, params=(today_str+'%',)).iloc[0]['t']
    cogs = pd.read_sql_query("SELECT COALESCE(SUM(si.qty * si.cost_price), 0) as c FROM sale_items si JOIN sales s ON si.sale_id = s.id WHERE s.date LIKE %s AND s.status='Completed'", conn, params=(today_str+'%',)).iloc[0]['c']
    exp = pd.read_sql_query("SELECT COALESCE(SUM(amount), 0) as e FROM expenses WHERE date LIKE %s", conn, params=(today_str+'%',)).iloc[0]['e']
    
    net = rev - cogs - exp
    
    colA, colB, colC = st.columns(3)
    colA.metric("Today's Cash (Revenue)", format_currency(rev))
    colB.metric("Today's Expenses", format_currency(exp))
    colC.metric("Net Profit Today", format_currency(net))
    
    st.markdown("---")
    
    with st.expander("🛠️ Admin Controls (Password Required)"):
        pwd = st.text_input("Admin Password", type="password")
        if pwd == "admin123":
            st.success("Admin Access Granted.")
            
            st.subheader("Edit/Delete Today's Sales")
            df_todays_sales = pd.read_sql_query("SELECT * FROM sales WHERE date LIKE %s", conn, params=(today_str+'%',))
            st.dataframe(df_todays_sales)
            
            del_id = st.number_input("Enter Sale ID to permanently DELETE", min_value=0)
            if st.button("Delete Sale"):
                c = conn.cursor()
                c.execute("DELETE FROM sales WHERE id=%s", (del_id,))
                c.execute("DELETE FROM sale_items WHERE sale_id=%s", (del_id,))
                conn.commit()
                st.success("Sale Deleted.")
                st.rerun()
        elif pwd != "":
            st.error("Incorrect Password")
            
    conn.close()

