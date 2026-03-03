import streamlit as st
import sqlite3
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
    div[data-baseweb="tab-list"] { background-color: #ffffff; border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .whatsapp-btn { background-color: #25D366; color: white; padding: 10px; text-align: center; border-radius: 8px; text-decoration: none; display: block; font-weight: bold; margin-top: 10px; }
    .whatsapp-btn:hover { background-color: #1DA851; color: white; text-decoration: none; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE SETUP & MIGRATION
# ==========================================
DB_NAME = "modern_foam.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Inventory Table
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type TEXT,
                    name TEXT,
                    size TEXT,
                    thickness TEXT,
                    category TEXT,
                    price INTEGER,
                    quantity INTEGER
                )''')
    # Sales Table
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    customer_phone TEXT,
                    total_amount INTEGER
                )''')
    # Sale Items Table
    c.execute('''CREATE TABLE IF NOT EXISTS sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER,
                    item_desc TEXT,
                    price INTEGER,
                    qty INTEGER
                )''')
    # Expenses Table (NEW)
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    description TEXT,
                    amount INTEGER
                )''')
    conn.commit()
    
    # --- AUTO-UPGRADE DATABASE (Adds Cost Price for P&L) ---
    try:
        c.execute("ALTER TABLE inventory ADD COLUMN cost_price INTEGER DEFAULT 0")
    except:
        pass # Column already exists
        
    try:
        c.execute("ALTER TABLE sale_items ADD COLUMN cost_price INTEGER DEFAULT 0")
    except:
        pass # Column already exists
        
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

if 'cart' not in st.session_state:
    st.session_state.cart = []

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def format_currency(amount):
    return f"PKR {amount:,.0f}"

def get_inventory_choices(include_out_of_stock=False):
    conn = get_db_connection()
    query = "SELECT * FROM inventory" if include_out_of_stock else "SELECT * FROM inventory WHERE quantity > 0"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    choices = []
    for _, row in df.iterrows():
        if row['item_type'] == 'Mattress':
            desc = f"{row['name']} | {row['size']} | {row['thickness']} | {row['category']}"
        else:
            size_text = f" | {row['size']}" if row['size'] else ""
            desc = f"{row['name']}{size_text}"
            
        display_desc = f"{desc} - {format_currency(row['price'])}"
        choices.append({
            'id': row['id'], 
            'desc_clean': desc,
            'display_desc': display_desc, 
            'price': row['price'], 
            'cost_price': row['cost_price'],
            'stock': row['quantity'],
            'raw_data': row
        })
    return choices

# ==========================================
# 4. MAIN UI & LOGIC
# ==========================================
st.title("🟩 Modern Foam Center")

tab1, tab2, tab3, tab4 = st.tabs(["🛒 Point of Sale", "📦 Inventory", "💸 Accounts (Expenses)", "📊 Closing & P&L"])

# ------------------------------------------
# TAB 1: POINT OF SALE
# ------------------------------------------
with tab1:
    st.header("New Cash Sale")
    
    inventory_items = get_inventory_choices(include_out_of_stock=False)
    if not inventory_items:
        st.warning("Inventory is empty or out of stock. Add items in the Inventory tab.")
    else:
        item_options = {item['display_desc']: item for item in inventory_items}
        selected_desc = st.selectbox("Select Item", options=list(item_options.keys()))
        selected_item = item_options[selected_desc]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            qty_to_buy = st.number_input("Quantity", min_value=1, max_value=selected_item['stock'], step=1)
        with col2:
            st.write("") 
            st.write("")
            if st.button("Add to Bill"):
                st.session_state.cart.append({
                    'id': selected_item['id'],
                    'desc': selected_item['desc_clean'], 
                    'price': selected_item['price'],
                    'cost_price': selected_item['cost_price'],
                    'qty': qty_to_buy,
                    'total': selected_item['price'] * qty_to_buy
                })
                st.success("Added!")
                st.rerun()

    if st.session_state.cart:
        st.markdown("---")
        st.subheader("Current Bill")
        
        cart_df = pd.DataFrame(st.session_state.cart)
        st.dataframe(cart_df[['desc', 'qty', 'price', 'total']], use_container_width=True)
        
        grand_total = sum(item['total'] for item in st.session_state.cart)
        
        st.write("### Apply Discount")
        discount_col1, discount_col2 = st.columns(2)
        with discount_col1:
            discount_type = st.selectbox("Discount Type", ["None", "Flat Amount (PKR)", "Percentage (%)"])
        with discount_col2:
            discount_value = 0 if discount_type == "None" else st.number_input("Enter Discount Value", min_value=0, step=100 if discount_type == "Flat Amount (PKR)" else 1)
        
        if discount_type == "Flat Amount (PKR)":
            final_total = max(0, grand_total - discount_value)
            discount_text = f"Discount applied: - PKR {discount_value:,.0f}"
        elif discount_type == "Percentage (%)":
            discount_amount = int(grand_total * (discount_value / 100.0))
            final_total = max(0, grand_total - discount_amount)
            discount_text = f"Discount applied: {discount_value}% (- PKR {discount_amount:,.0f})"
        else:
            final_total = grand_total
            discount_text = ""

        st.markdown(f"**Subtotal:** {format_currency(grand_total)}")
        if discount_type != "None":
            st.markdown(f"**{discount_text}**")
        st.markdown(f"<h3 style='color: #006600;'>Grand Total: {format_currency(final_total)}</h3>", unsafe_allow_html=True)
        
        customer_phone = st.text_input("Customer Phone (Optional, format: 923XXXXXXXXX)")
        
        if st.button("Complete Cash Sale"):
            conn = get_db_connection()
            c = conn.cursor()
            
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO sales (date, customer_phone, total_amount) VALUES (?, ?, ?)", 
                      (date_now, customer_phone, final_total))
            sale_id = c.lastrowid
            
            receipt_items_text = ""
            for item in st.session_state.cart:
                # Insert sale item including cost_price for accurate P&L
                c.execute("INSERT INTO sale_items (sale_id, item_desc, price, cost_price, qty) VALUES (?, ?, ?, ?, ?)",
                          (sale_id, item['desc'], item['price'], item['cost_price'], item['qty']))
                c.execute("UPDATE inventory SET quantity = quantity - ? WHERE id = ?", (item['qty'], item['id']))
                receipt_items_text += f"- {item['qty']}x {item['desc']}\n"
                
            conn.commit()
            conn.close()
            
            wa_text = f"*Modern Foam Center Receipt*\n\nItems:\n{receipt_items_text}\n"
            if discount_type != "None":
                wa_text += f"Subtotal: {format_currency(grand_total)}\n{discount_text}\n"
            wa_text += f"*Total: {format_currency(final_total)}*\nPayment: Cash\n\nThank you for your purchase!"
            
            encoded_text = urllib.parse.quote(wa_text)
            wa_link = f"https://wa.me/{customer_phone}?text={encoded_text}" if customer_phone else f"https://wa.me/?text={encoded_text}"
            
            st.success("Sale Completed Successfully!")
            st.markdown(f'<a href="{wa_link}" target="_blank" class="whatsapp-btn">📱 Send WhatsApp Receipt</a>', unsafe_allow_html=True)
            
            if st.button("Start Next Sale"):
                st.session_state.cart = []
                st.rerun()

# ------------------------------------------
# TAB 2: INVENTORY MANAGEMENT
# ------------------------------------------
with tab2:
    st.header("Manage Stock")
    
    # --- ADD NEW ITEM ---
    with st.expander("➕ Add New Item", expanded=False):
        item_type = st.radio("Item Type", ["Mattress", "Other Item (Pillows, Sheets, etc.)"], key="add_type")
        
        with st.form("add_inventory_form"):
            name = st.text_input("Brand / Item Name")
            size_choice = st.selectbox("Size", ["78x72 (King)", "78x60 (Queen)", "78x42 (Single)", "Standard", "Custom Size..."], key="add_size")
            size = st.text_input("Enter Custom Size (e.g., 72x36)") if size_choice == "Custom Size..." else size_choice
            
            if item_type == "Mattress":
                col2, col3 = st.columns(2)
                with col2:
                    thickness = st.selectbox("Thickness", ["4 inch", "5 inch", "6 inch", "8 inch", "10 inch", "Custom/Other"], key="add_thick")
                with col3:
                    category = st.selectbox("Category", ["Covered", "Uncovered"], key="add_cat") 
            else:
                thickness, category = "", ""
                
            col_cost, col_price, col_qty = st.columns(3)
            with col_cost:
                cost_price = st.number_input("Cost Price (PKR)", min_value=0, step=100)
            with col_price:
                price = st.number_input("Selling Price (PKR)", min_value=0, step=100)
            with col_qty:
                quantity = st.number_input("Quantity to Add", min_value=0, step=1)
                
            if st.form_submit_button("Save to Inventory"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('''INSERT INTO inventory (item_type, name, size, thickness, category, price, cost_price, quantity) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (item_type, name, size, thickness, category, price, cost_price, quantity))
                conn.commit()
                conn.close()
                st.success(f"Added {name} to inventory!")
                st.rerun()

    # --- EDIT EXISTING ITEM ---
    with st.expander("✏️ Edit Existing Item", expanded=False):
        all_items = get_inventory_choices(include_out_of_stock=True)
        if all_items:
            edit_options = {f"ID {item['id']}: {item['desc_clean']}": item for item in all_items}
            selected_edit_key = st.selectbox("Select Item to Edit", options=list(edit_options.keys()))
            item_to_edit = edit_options[selected_edit_key]['raw_data']
            
            with st.form("edit_inventory_form"):
                st.write(f"Editing: **{item_to_edit['name']}**")
                edit_name = st.text_input("Name", value=item_to_edit['name'])
                edit_size = st.text_input("Size", value=item_to_edit['size'])
                
                col_c, col_p, col_q = st.columns(3)
                with col_c:
                    edit_cost = st.number_input("Cost Price (PKR)", value=int(item_to_edit['cost_price']), step=100)
                with col_p:
                    edit_price = st.number_input("Selling Price (PKR)", value=int(item_to_edit['price']), step=100)
                with col_q:
                    edit_qty = st.number_input("Quantity", value=int(item_to_edit['quantity']), step=1)
                
                if st.form_submit_button("Update Item"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute('''UPDATE inventory 
                                 SET name = ?, size = ?, cost_price = ?, price = ?, quantity = ? 
                                 WHERE id = ?''', 
                              (edit_name, edit_size, edit_cost, edit_price, edit_qty, item_to_edit['id']))
                    conn.commit()
                    conn.close()
                    st.success("Item Updated Successfully!")
                    st.rerun()

    st.subheader("Current Stock")
    conn = get_db_connection()
    df_inv = pd.read_sql_query("SELECT id, item_type, name, size, thickness, category, cost_price, price as selling_price, quantity FROM inventory", conn)
    conn.close()
    st.dataframe(df_inv, hide_index=True, use_container_width=True)

# ------------------------------------------
# TAB 3: ACCOUNTS (EXPENSES)
# ------------------------------------------
with tab3:
    st.header("💸 Day-to-Day Accounts")
    
    with st.form("add_expense_form"):
        st.subheader("Record New Payment / Expense")
        col1, col2 = st.columns(2)
        with col1:
            exp_desc = st.text_input("Description (e.g., Shop Rent, Lunch, Electricity)")
        with col2:
            exp_amount = st.number_input("Amount (PKR)", min_value=1, step=100)
            
        if st.form_submit_button("Record Expense"):
            if exp_desc:
                conn = get_db_connection()
                c = conn.cursor()
                date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("INSERT INTO expenses (date, description, amount) VALUES (?, ?, ?)", (date_now, exp_desc, exp_amount))
                conn.commit()
                conn.close()
                st.success("Expense Recorded!")
                st.rerun()
            else:
                st.error("Please enter a description.")

    st.subheader("Recent Expenses")
    conn = get_db_connection()
    df_exp = pd.read_sql_query("SELECT date, description, amount FROM expenses ORDER BY date DESC LIMIT 50", conn)
    conn.close()
    st.dataframe(df_exp, hide_index=True, use_container_width=True)

# ------------------------------------------
# TAB 4: CLOSING & P&L
# ------------------------------------------
with tab4:
    st.header("📊 Financial Closing & P&L")
    
    closing_type = st.radio("Select Report Type", ["Daily Closing", "Monthly Closing"], horizontal=True)
    
    if closing_type == "Daily Closing":
        selected_date = st.date_input("Select Date", datetime.now().date())
        date_filter = selected_date.strftime("%Y-%m-%d")
        title_text = f"Closing for {date_filter}"
        like_query = f"{date_filter}%"
    else:
        current_month = datetime.now().strftime("%Y-%m")
        selected_month = st.text_input("Enter Month (YYYY-MM)", value=current_month)
        title_text = f"Closing for Month: {selected_month}"
        like_query = f"{selected_month}%"

    st.subheader(title_text)
    
    conn = get_db_connection()
    
    # 1. Total Sales Revenue
    revenue_query = f"SELECT IFNULL(SUM(total_amount), 0) as total FROM sales WHERE date LIKE '{like_query}'"
    total_revenue = pd.read_sql_query(revenue_query, conn).iloc[0]['total']
    
    # 2. Total COGS (Cost of Goods Sold)
    # COGS is sum of (qty * cost_price) for all items sold in this period
    cogs_query = f"""
        SELECT IFNULL(SUM(si.qty * si.cost_price), 0) as cogs
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.date LIKE '{like_query}'
    """
    total_cogs = pd.read_sql_query(cogs_query, conn).iloc[0]['cogs']
    
    # 3. Total Expenses
    exp_query = f"SELECT IFNULL(SUM(amount), 0) as exp FROM expenses WHERE date LIKE '{like_query}'"
    total_expenses = pd.read_sql_query(exp_query, conn).iloc[0]['exp']
    
    conn.close()
    
    # Calculations
    gross_profit = total_revenue - total_cogs
    net_profit = gross_profit - total_expenses
    
    # P&L Dashboard display
    col_r, col_c, col_g = st.columns(3)
    with col_r:
        st.markdown(f"<div class='metric-card'><h4>Total Sales (Revenue)</h4><h2 style='color:#008000;'>{format_currency(total_revenue)}</h2></div>", unsafe_allow_html=True)
    with col_c:
        st.markdown(f"<div class='metric-card'><h4>Cost of Goods Sold</h4><h2 style='color:#b30000;'>{format_currency(total_cogs)}</h2></div>", unsafe_allow_html=True)
    with col_g:
        st.markdown(f"<div class='metric-card'><h4>Gross Profit</h4><h2>{format_currency(gross_profit)}</h2></div>", unsafe_allow_html=True)
        
    st.write("")
    
    col_e, col_n = st.columns(2)
    with col_e:
        st.markdown(f"<div class='metric-card'><h4>Total Expenses</h4><h2 style='color:#b30000;'>{format_currency(total_expenses)}</h2></div>", unsafe_allow_html=True)
    with col_n:
        profit_color = "#008000" if net_profit >= 0 else "#b30000"
        st.markdown(f"<div class='metric-card'><h4>Net Profit (Final)</h4><h1 style='color:{profit_color};'>{format_currency(net_profit)}</h1></div>", unsafe_allow_html=True)