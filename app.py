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

# --- OTP AUTHENTICATION GATE ---
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
                        st.error(f"Invalid or expired code. Please try again. Details: {e}")
            with col2:
                if st.form_submit_button("Use Different Email"):
                    st.session_state.otp_sent = False
                    st.rerun()

else:
    user = st.session_state.user
    user_uuid = user.id

    # --- TOP HEADER & LOGOUT ---
    head_col1, head_col2 = st.columns([3, 1])
    with head_col1:
        st.title("🌐 MyLinks Hub")
    with head_col2:
        if st.button("🚪 Log Out"):
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

    # Fetch Data from Supabase
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

    # Group by Category
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

    # --- MOBILE-FRIENDLY FLEXBOX CSS ---
    st.markdown(
        """
        <style>
            .link-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                width: 100%;
                gap: 12px;
                margin-bottom: 10px;
            }
            .link-card {
                flex: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }
            .desc-text {
                font-size: 0.72em;
                color: gray;
                text-align: left;
                margin-top: 4px;
            }
            .link-menu {
                flex-shrink: 0;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    for idx, category in enumerate(all_categories):
        with selected_cat[idx]:
            st.write("")

            # Add New Item Expander
            with st.expander("➕ Add New Item in this Category"):
                with st.form(f"add_form_{category}", clear_on_submit=True):
                    new_name = st.text_input("Link Name")
                    new_search = st.text_input("Optional: Search Site URL")
                    new_kw = st.text_input("Link Key Words / Description")
                    new_url = st.text_input("Link URL or App")
                    new_cat = st.text_input("Category", value=category)

                    if st.form_submit_button("Save Item", type="primary"):
                        if new_name and new_url and new_cat:
                            try:
                                supabase.table("shortcuts").insert({
                                    "user_id": user_uuid,
                                    "category": new_cat,
                                    "name": new_name,
                                    "search_site": new_search,
                                    "url_or_keyword": new_url,
                                }).execute()
                                st.success("Added successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving: {e}")
                        else:
                            st.error("Please fill required fields.")

            st.write("")

            links = user_shortcuts.get(category, [])
            if not links:
                st.info("No links found in this category.")
            else:
                for link in links:
                    resolved_target = resolve_input(
                        link["url_or_keyword"], link["search_site"]
                    )
                    description_text = link["url_or_keyword"]

                    # --- FLEXBOX ROW ---
                    st.markdown('<div class="link-row">', unsafe_allow_html=True)

                    # CARD + DESCRIPTION (same flex item)
                    st.markdown(
                        f"""
                        <div class="link-card">
                            <a href="{resolved_target}" target="_blank" style="text-decoration: none; display: block;">
                                <div style="
                                    background-color: rgba(255, 255, 255, 0.04);
                                    border: 1px solid rgba(150, 150, 150, 0.2);
                                    border-radius: 12px;
                                    padding: 12px 16px;
                                    text-align: center;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
                                ">
                                    <div style="font-size: 1.05em; font-weight: 600; color: inherit;">🔗 {link['name']}</div>
                                </div>
                            </a>
                            <div class="desc-text">{description_text}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # MENU
                    st.markdown('<div class="link-menu">', unsafe_allow_html=True)
                    with st.popover("⋮"):
                        st.write(f"**{link['name']}**")
                        action_choice = st.radio(
                            "Action", ["Edit", "Delete"], key=f"action_{link['id']}"
                        )

                        if action_choice == "Edit":
                            with st.form(f"edit_form_{link['id']}"):
                                up_name = st.text_input("Link Name", value=link["name"])
                                up_search = st.text_input("Search Site", value=link["search_site"])
                                up_url = st.text_input("URL or App", value=link["url_or_keyword"])
                                up_cat = st.text_input("Category", value=link["category"])

                                if st.form_submit_button("Save Changes"):
                                    try:
                                        supabase.table("shortcuts").update({
                                            "name": up_name,
                                            "search_site": up_search,
                                            "url_or_keyword": up_url,
                                            "category": up_cat,
                                        }).eq("id", link["id"]).execute()
                                        st.success("Updated!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Update failed: {e}")

                        elif action_choice == "Delete":
                            if st.button("Confirm Delete", key=f"confirm_del_{link['id']}"):
                                try:
                                    supabase.table("shortcuts").delete().eq("id", link["id"]).execute()
                                    st.success("Deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")

                    st.markdown('</div>', unsafe_allow_html=True)  # close menu
                    st.markdown('</div>', unsafe_allow_html
