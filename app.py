import urllib.parse
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="MyLinks - Cloud Hub",
    layout="centered",
    initial_sidebar_state="collapsed",
)

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase: Client = init_supabase()

if "user" not in st.session_state:
    st.session_state.user = None

# --- OTP AUTH ---
if not st.session_state.user:
    st.title("🔐 MyLinks - Secure Login")
    st.markdown("Enter your email to sign in or automatically create an account via OTP.")

    if "otp_sent" not in st.session_state:
        st.session_state.otp_sent = False

    if not st.session_state.otp_sent:
        with st.form("request_otp_form"):
            email = st.text_input("Email Address")
            if st.form_submit_button("Send Login Code"):
                if email:
                    try:
                        supabase.auth.sign_in_with_otp({"email": email})
                        st.session_state.pending_email = email
                        st.session_state.otp_sent = True
                        st.success("Check your email for the 6-digit login code!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to send code: {e}")
                else:
                    st.error("Please enter an email address.")
    else:
        st.info(f"Verification code sent to: **{st.session_state.pending_email}**")
        with st.form("verify_otp_form"):
            token = st.text_input("Enter 6-Digit Code")
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Verify & Log In", type="primary"):
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
                        st.error(f"Invalid or expired code. Details: {e}")
            with col2:
                if st.form_submit_button("Use Different Email"):
                    st.session_state.otp_sent = False
                    st.rerun()

else:
    user = st.session_state.user
    user_uuid = user.id

    # --- HEADER ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🌐 MyLinks Hub")
    with col2:
        if st.button("🚪 Log Out"):
            supabase.auth.sign_out()
            st.session_state.user = None
            st.rerun()

    st.divider()

    # --- URL RESOLVER ---
    def resolve_input(url_or_app: str, search_site: str) -> str:
        cleaned = url_or_app.strip()
        if cleaned.lower().startswith(
            ("http://", "https://", "mailto:", "tel:", "spotify:", "zoommtg:")
        ):
            return cleaned
        if "." in cleaned and " " not in cleaned:
            return f"https://{cleaned}"

        encoded = urllib.parse.quote(cleaned)
        if search_site:
            site = search_site.strip()
            if not site.startswith("http"):
                site = f"https://{site}"
            return f"{site}?q={encoded}"

        return f"https://www.google.com/search?q={encoded}"

    # --- LOAD DATA ---
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
    shortcuts = {}
    for row in rows:
        cat = row["category"] or "General"
        shortcuts.setdefault(cat, []).append(row)

    categories = list(shortcuts.keys()) or ["General"]
    tabs = st.tabs(categories)

    # --- INLINE MENU CSS ---
    st.markdown(
        """
        <style>
            .link-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                width: 100%;
                gap: 12px;
                margin-bottom: 12px;
            }
            .link-card {
                flex: 1;
                display: flex;
                flex-direction: column;
            }
            .desc {
                font-size: 0.72em;
                color: gray;
                text-align: left;
                margin-top: 4px;
            }
            .menu-btn {
                background:none;
                border:none;
                font-size:22px;
                cursor:pointer;
                padding:0;
                margin:0;
            }
            .menu-popup {
                display:none;
                position:absolute;
                background:#222;
                padding:10px;
                border-radius:8px;
                border:1px solid #444;
                z-index:9999;
                color:white;
            }
            .menu-popup button {
                width:100%;
                margin-top:6px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- ACTION HANDLER ---
    params = st.query_params
    if "action" in params and "id" in params:
        action = params["action"]
        item_id = params["id"]

        if action == "delete":
            supabase.table("shortcuts").delete().eq("id", item_id).execute()
            st.success("Deleted!")
            st.query_params.clear()
            st.rerun()

        if action == "edit":
            st.session_state.edit_id = item_id
            st.query_params.clear()
            st.rerun()

    # --- RENDER TABS ---
    for i, cat in enumerate(categories):
        with tabs[i]:
            st.write("")

            # Add new item
            with st.expander("➕ Add New Item in this Category"):
                with st.form(f"add_{cat}", clear_on_submit=True):
                    name = st.text_input("Link Name")
                    search = st.text_input("Optional: Search Site URL")
                    url = st.text_input("Link URL or App")
                    new_cat = st.text_input("Category", value=cat)

                    if st.form_submit_button("Save Item", type="primary"):
                        if name and url:
                            supabase.table("shortcuts").insert({
                                "user_id": user_uuid,
                                "category": new_cat,
                                "name": name,
                                "search_site": search,
                                "url_or_keyword": url,
                            }).execute()
                            st.success("Added!")
                            st.rerun()
                        else:
                            st.error("Name and URL required.")

            # Items
            for link in shortcuts.get(cat, []):
                target = resolve_input(link["url_or_keyword"], link["search_site"])

                # --- INLINE ROW ---
                st.markdown('<div class="link-row">', unsafe_allow_html=True)

                # CARD
                st.markdown(
                    f"""
                    <div class="link-card">
                        <a href="{target}" target="_blank" style="text-decoration:none;">
                            <div style="
                                background-color: rgba(255,255,255,0.04);
                                border:1px solid rgba(150,150,150,0.2);
                                border-radius:12px;
                                padding:12px 16px;
                                text-align:center;
                                box-shadow:0 2px 4px rgba(0,0,0,0.02);
                            ">
                                <div style="font-size:1.05em; font-weight:600;">🔗 {link['name']}</div>
                            </div>
                        </a>
                        <div class="desc">{link['url_or_keyword']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # MENU BUTTON + POPUP
                menu_html = f"""
                <div>
                    <button class="menu-btn" id="btn_{link['id']}">⋮</button>
                    <div class="menu-popup" id="popup_{link['id']}">
                        <b>{link['name']}</b><br>
                        <a href="?action=edit&id={link['id']}">
                            <button>Edit</button>
                        </a>
                        <a href="?action=delete&id={link['id']}">
                            <button>Delete</button>
                        </a>
                    </div>
                </div>

                <script>
                document.getElementById("btn_{link['id']}").onclick = function() {{
                    const p = document.getElementById("popup_{link['id']}");
                    p.style.display = (p.style.display === "block") ? "none" : "block";
                }};
                </script>
                """

                st.markdown(menu_html, unsafe_allow_html=True)

                st.markdown('</div>', unsafe_allow_html=True)  # close row

            st.write("")
