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

    if not st.session_session_state.otp_sent:
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
    def resolve_input(url_or_app: str, search_site: str
