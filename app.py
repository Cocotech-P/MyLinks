import urllib.parse
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="MyLinks - Cloud Hub",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Mobile detection via viewport width query param or session state
def is_mobile():
    """Detect if viewing on mobile by checking query params or screen size hints"""
    return st.session_state.get("is_mobile", False)

# CSS for better mobile responsiveness
st.markdown("""
<style>
    /* Mobile-first responsive design */
    body {
        font-size: clamp(14px, 2.5vw, 16px);
    }
    
    /* Link card responsive sizing */
    .link-card {
        border-radius: 12px;
        padding: clamp(12px, 3vw, 16px);
        border: 1px solid rgba(150, 150, 150, 0.2);
        background-color: rgba(255, 255, 255, 0.04);
        margin-bottom: 10px;
        transition: all 0.2s ease;
    }
    
    .link-card:active {
        background-color: rgba(255, 255, 255, 0.08);
        transform: scale(0.98);
    }
    
    .link-card-name {
        font-size: clamp(1em, 2vw, 1.1em);
        font-weight: 600;
        word-break: break-word;
    }
    
    .link-card-desc {
        font-size: clamp(0.7em, 1.8vw, 0.85em);
        color: #888;
        margin-top: 6px;
        word-break: break-word;
    }
    
    /* Mobile-optimized buttons and forms */
    .stButton > button {
        min-height: 44px; /* Touch-friendly minimum */
        font-size: clamp(14px, 2vw, 16px);
        width: 100%;
    }
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        min-height: 44px;
        font-size: 16px; /* Prevent iOS zoom on input */
    }
    
    /* Streamlit form spacing */
    .stForm {
        padding: 0;
    }
    
    /* Tab styling for mobile */
    .stTabs [data-baseweb="tab-list"] {
        gap: clamp(4px, 1vw, 8px);
        flex-wrap: wrap;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: clamp(8px, 2vw, 12px) clamp(12px, 3vw, 16px);
        font-size: clamp(12px, 2vw, 14px);
        min-width: auto;
    }
    
    /* Popover sizing for mobile */
    .stPopover {
        max-width: 90vw !important;
    }
    
    /* Info box padding */
    .stInfo, .stSuccess, .stError {
        padding: clamp(12px, 3vw, 16px) !important;
        font-size: clamp(12px, 2vw, 14px);
    }
    
    /* Divider spacing */
    hr {
        margin: clamp(12px, 3vw, 20px) 0;
    }
    
    /* Header responsive */
    .header-title {
        font-size: clamp(24px, 5vw, 36px);
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase: Client = init_supabase()

if "user" not in st.session_state:
    st.session_state.user = None

if "editing_link_id" not in st.session_state:
    st.session_state.editing_link_id = None

# --- OTP AUTHENTICATION GATE ---
if not st.session_state.user:
    st.title("🔐 MyLinks")
    st.markdown("Secure link manager with OTP authentication")

    if "otp_sent" not in st.session_state:
        st.session_state.otp_sent = False

    if not st.session_state.otp_sent:
        with st.form("request_otp_form"):
            st.markdown("### Sign In")
            email = st.text_input("Email Address", placeholder="your@email.com")
            if st.form_submit_button("Send Login Code", type="primary", use_container_width=True):
                if email:
                    try:
                        supabase.auth.sign_in_with_otp({"email": email})
                        st.session_state.pending_email = email
                        st.session_state.otp_sent = True
                        st.success("✓ Check your email for the login code")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to send code: {e}")
                else:
                    st.error("Please enter an email address.")
    else:
        st.info(f"Verification code sent to **{st.session_state.pending_email}**")
        with st.form("verify_otp_form"):
            st.markdown("### Enter Your Code")
            token = st.text_input("6-Digit Code", placeholder="000000", max_chars=6)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Verify & Log In", type="primary", use_container_width=True):
                    try:
                        res = supabase.auth.verify_otp({
                            "email": st.session_state.pending_email,
                            "token": token,
                            "type": "email",
                        })
                        if res.user:
                            st.session_state.user = res.user
                            del st.session_state.otp_sent
                            del st.session_state.pending_email
                            st.rerun()
                    except Exception as e:
                        st.error(f"Invalid or expired code. Try again.")
            
            with col2:
                if st.form_submit_button("Different Email", use_container_width=True):
                    st.session_state.otp_sent = False
                    st.rerun()

else:
    user = st.session_state.user
    user_uuid = user.id

    # --- HEADER ---
    head_col1, head_col2 = st.columns([1, 1])
    with head_col1:
        st.markdown('<h1 class="header-title">🌐 MyLinks</h1>', unsafe_allow_html=True)
    with head_col2:
        if st.button("🚪 Log Out", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    st.divider()

    # --- INPUT RESOLUTION HELPER ---
    def resolve_input(url_or_app: str, search_site: str) -> str:
        cleaned = url_or_app.strip()
        if cleaned.lower().startswith(
            ("http://", "https://", "mailto:", "tel:", "spotify:", "zoommtg:")
        ):
            return cleaned
        if "." in cleaned and " " not in cleaned:
            return f"https://{cleaned}"

        encoded_query = urllib.parse.quote(cleaned)
        if search_site and search_site.strip():
            site_cleaned = search_site.strip()
            if not site_cleaned.startswith("http"):
                site_cleaned = f"https://{site_cleaned}"
            return f"{site_cleaned}?q={encoded_query}"

        return f"https://www.google.com/search?q={encoded_query}"

    # --- FETCH DATA FROM SUPABASE ---
    try:
        response = (
            supabase.table("shortcuts")
            .select("*")
            .eq("user_id", user_uuid)
            .order("created_at")
            .execute()
        )
        rows = response.data
    except Exception as e:
        st.error(f"Failed to load links: {e}")
        rows = []

    # --- GROUP BY CATEGORY ---
    user_shortcuts = {}
    for row in rows:
        cat = row["category"] or "General"
        if cat not in user_shortcuts:
            user_shortcuts[cat] = []
        user_shortcuts[cat].append({
            "id": row["id"],
            "name": row["name"],
            "search_site": row.get("search_site", ""),
            "url_or_keyword": row["url_or_keyword"],
            "category": cat,
        })

    all_categories = list(user_shortcuts.keys())
    if not all_categories:
        all_categories = ["General"]

    # --- CATEGORY TABS ---
    selected_cat = st.tabs(all_categories)

    for idx, category in enumerate(all_categories):
        with selected_cat[idx]:
            st.write("")

            # --- ADD NEW ITEM EXPANDER ---
            with st.expander("➕ Add New Item", expanded=False):
                with st.form(f"add_form_{category}", clear_on_submit=True):
                    new_name = st.text_input("Link Name", placeholder="e.g., Gmail, GitHub")
                    new_url = st.text_input("URL or App", placeholder="gmail.com or https://example.com")
                    new_search = st.text_input(
                        "Search Site (Optional)",
                        placeholder="e.g., google.com for search shortcuts"
                    )
                    new_kw = st.text_input("Description (Optional)", placeholder="What is this link for?")
                    new_cat = st.text_input("Category", value=category)

                    if st.form_submit_button("Save Item", type="primary", use_container_width=True):
                        if new_name and new_url and new_cat:
                            try:
                                supabase.table("shortcuts").insert({
                                    "user_id": user_uuid,
                                    "category": new_cat,
                                    "name": new_name,
                                    "search_site": new_search,
                                    "url_or_keyword": new_url,
                                }).execute()
                                st.success("✓ Added!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.error("Fill in Name, URL, and Category.")

            st.write("")

            # --- DISPLAY LINKS ---
            links = user_shortcuts.get(category, [])
            if not links:
                st.info("📭 No links yet. Add one to get started!")
            else:
                for link in links:
                    resolved_target = resolve_input(link["url_or_keyword"], link["search_site"])
                    
                    # Card layout - stacked on mobile, side-by-side on desktop
                    col_card, col_action = st.columns([0.85, 0.15]) if not is_mobile() else st.columns([1])
                    
                    with col_card:
                        st.markdown(
                            f"""
                            <a href="{resolved_target}" target="_blank" style="text-decoration: none;">
                                <div class="link-card">
                                    <div class="link-card-name">🔗 {link['name']}</div>
                                    {f'<div class="link-card-desc">{link["url_or_keyword"]}</div>' if link["url_or_keyword"] else ''}
                                </div>
                            </a>
                            """,
                            unsafe_allow_html=True,
                        )
                    
                    if not is_mobile():
                        with col_action:
                            if st.button("⋮", key=f"menu_{link['id']}", help="Edit or delete"):
                                st.session_state.editing_link_id = link['id']
                    else:
                        # On mobile, show edit/delete buttons below the card
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("✏️ Edit", key=f"edit_{link['id']}", use_container_width=True):
                                st.session_state.editing_link_id = link['id']
                        with btn_col2:
                            if st.button("🗑️ Delete", key=f"delete_{link['id']}", use_container_width=True):
                                st.session_state.editing_link_id = f"confirm_del_{link['id']}"

                    # --- EDIT MODAL ---
                    if st.session_state.editing_link_id == link['id']:
                        st.divider()
                        st.markdown(f"### Editing: {link['name']}")
                        with st.form(f"edit_form_{link['id']}"):
                            up_name = st.text_input("Link Name", value=link["name"])
                            up_url = st.text_input("URL or App", value=link["url_or_keyword"])
                            up_search = st.text_input("Search Site (Optional)", value=link["search_site"])
                            up_cat = st.text_input("Category", value=link["category"])

                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Save", type="primary", use_container_width=True):
                                    try:
                                        supabase.table("shortcuts").update({
                                            "name": up_name,
                                            "search_site": up_search,
                                            "url_or_keyword": up_url,
                                            "category": up_cat,
                                        }).eq("id", link["id"]).execute()
                                        st.success("✓ Updated!")
                                        st.session_state.editing_link_id = None
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Update failed: {e}")
                            
                            with col_cancel:
                                if st.form_submit_button("Cancel", use_container_width=True):
                                    st.session_state.editing_link_id = None
                                    st.rerun()

                    # --- DELETE CONFIRMATION ---
                    if st.session_state.editing_link_id == f"confirm_del_{link['id']}":
                        st.divider()
                        st.warning(f"⚠️ Delete '{link['name']}'? This cannot be undone.")
                        col_del1, col_del2 = st.columns(2)
                        with col_del1:
                            if st.button(
                                "🗑️ Confirm Delete",
                                key=f"confirm_del_btn_{link['id']}",
                                use_container_width=True
                            ):
                                try:
                                    supabase.table("shortcuts").delete().eq("id", link["id"]).execute()
                                    st.success("✓ Deleted!")
                                    st.session_state.editing_link_id = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                        
                        with col_del2:
                            if st.button("Cancel", key=f"cancel_del_{link['id']}", use_container_width=True):
                                st.session_state.editing_link_id = None
                                st.rerun()

            st.write("")
